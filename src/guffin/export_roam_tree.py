#!/usr/bin/env python3
"""CLI tool for exporting a Roam Research page or node subtree.

Fetches all descendant blocks identified by ``TARGET`` via the Roam Local API,
transcribes them into a :class:`~guffin.graph.VertexTree`, and writes the
result in one of two output formats controlled by ``--format``:

- **Markdown** (default, ``--format markdown``) — renders the tree to
  CommonMark via :func:`~guffin.md_rendering.render`, then writes in one
  of two bundle modes:

  - **Bundle mode** (default, ``--bundle``) — fetches Cloud Firestore images
    and writes a self-contained ``<output_dir>/<target>.mdbundle/`` directory
    via :func:`~guffin.roam_md_bundle.bundle_md_document`.  Pass
    ``--cache-dir`` to avoid re-downloading unchanged assets across runs.
  - **Plain mode** (``--no-bundle``) — writes the CommonMark text directly
    to ``<output_dir>/<target>.md``.

- **PDF** (``--format pdf``) — builds a Pandoc object model directly from
  the :class:`~guffin.graph.VertexTree` via
  :func:`~guffin.pdf_rendering.render_pdf` and writes
  ``<output_dir>/<target>.pdf``.  The ``--bundle/--no-bundle`` and
  ``--cache-dir`` options do not apply and are ignored.  Requires Pandoc
  and a PDF engine (e.g. ``pdflatex``) to be installed.

``TARGET`` is interpreted as a **node UID** if it matches
:data:`~guffin.roam_primitives.UID_PATTERN` (exactly 9 alphanumeric/dash/underscore
characters, the fixed format used by Roam for all block and page UIDs); otherwise it is
treated as a **page title**.  A page whose title happens to be exactly 9
characters from that alphabet would be misidentified — this edge case is
considered negligible in practice.

Logging is colorized by level via :mod:`guffin.logging_config` and
configurable via the ``LOG_LEVEL`` environment variable (default: ``INFO``).

Public symbols:

- :class:`OutputFormat` — output format enum (``markdown``, ``pdf``).
- :data:`app` — the :class:`~typer.Typer` application instance.
- :func:`main` — the CLI entry point; registered as the ``export-roam-tree``
  console script.

Example::

    export-roam-tree "Test Article" -p 3333 -g SCFH -t tok -o ~/docs
    export-roam-tree "Test Article" -p 3333 -g SCFH -t tok -o ~/docs --format pdf
    export-roam-tree "Test Article" -p 3333 -g SCFH -t tok -o ~/docs --no-bundle
    export-roam-tree wdMgyBiP9 -p 3333 -g SCFH -t tok -o ~/docs
    export-roam-tree "Test Article"  # reads all options from env vars
"""

import enum
import logging
import pathlib
from typing import Annotated, Final

import typer

from guffin.graph import VertexTree
from guffin.logging_config import configure_logging
from guffin.md_rendering import render as render_md
from guffin.pdf_rendering import render as render_pdf
from guffin.roam_local_api import ApiEndpoint
from guffin.roam_md_bundle import bundle_md_document
from guffin.roam_node_fetch_result import NodeFetchAnchor, NodeFetchResult, NodeFetchSpec
from guffin.roam_primitives import UID_PATTERN
from guffin.roam_tree_loader import fetch_roam_trees

configure_logging()
logger = logging.getLogger(__name__)

app = typer.Typer()


class OutputFormat(enum.StrEnum):
    """Output format for the exported document.

    Values:
        MARKDOWN: Render to CommonMark; supports ``--bundle/--no-bundle``.
        PDF: Render directly to PDF via the Pandoc object model (Panflute);
            ``--bundle/--no-bundle`` and ``--cache-dir`` do not apply.
    """

    MARKDOWN = "markdown"
    PDF = "pdf"


@app.command()
def main(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "Roam page title or node UID to export. "
                f"Treated as a node UID if it matches {UID_PATTERN}; "
                "otherwise treated as a page title."
            ),
        ),
    ],
    local_api_port: Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            envvar="ROAM_LOCAL_API_PORT",
            help="Port for Roam Local API",
        ),
    ],
    graph_name: Annotated[
        str,
        typer.Option(
            "--graph",
            "-g",
            envvar="ROAM_GRAPH_NAME",
            help="Name of the Roam graph",
        ),
    ],
    api_bearer_token: Annotated[
        str,
        typer.Option(
            "--token",
            "-t",
            envvar="ROAM_API_TOKEN",
            help="Bearer token for Roam Local API authentication",
        ),
    ],
    output_dir: Annotated[
        pathlib.Path,
        typer.Option(
            "--output-dir",
            "-o",
            envvar="ROAM_EXPORT_DIR",
            help="Directory to write the exported document into.",
        ),
    ],
    output_format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            "-f",
            help=(
                "Output format: 'markdown' (default) renders to CommonMark and supports "
                "--bundle/--no-bundle; 'pdf' builds a PDF directly from the vertex tree "
                "via Pandoc (requires Pandoc + a PDF engine on PATH)."
            ),
        ),
    ] = OutputFormat.MARKDOWN,
    bundle: Annotated[
        bool,
        typer.Option(
            "--bundle/--no-bundle",
            help=(
                "Markdown only. When enabled (default), fetches Cloud Firestore images "
                "and writes a .mdbundle directory. When disabled, writes a plain .md file. "
                "Ignored when --format pdf."
            ),
        ),
    ] = True,
    cache_dir: Annotated[
        pathlib.Path | None,
        typer.Option(
            "--cache-dir",
            "-c",
            envvar="ROAM_CACHE_DIR",
            help=(
                "Directory for caching downloaded Cloud Firestore assets across runs. "
                "Applies to both --format markdown (bundle mode) and --format pdf."
            ),
        ),
    ] = None,
) -> None:
    """Export a Roam Research page or node subtree to Markdown or PDF.

    TARGET is interpreted as a node UID (fetches the subtree rooted there) if
    it matches ``^[A-Za-z0-9_-]{9}$``, otherwise as a page title (fetches all
    blocks on that page).

    With ``--format markdown`` (default): ``--bundle`` writes a
    ``<target>.mdbundle/`` directory with images; ``--no-bundle`` writes a
    plain ``<target>.md`` file.

    With ``--format pdf``: writes ``<target>.pdf`` via Pandoc. The
    ``--bundle/--no-bundle`` and ``--cache-dir`` options are ignored.
    """
    logger.debug(
        "target=%r, local_api_port=%r, graph_name=%r, output_dir=%r, " "output_format=%r, bundle=%r, cache_dir=%r",
        target,
        local_api_port,
        graph_name,
        output_dir,
        output_format,
        bundle,
        cache_dir,
    )

    api_endpoint: Final[ApiEndpoint] = ApiEndpoint.from_parts(
        local_api_port=local_api_port,
        graph_name=graph_name,
        bearer_token=api_bearer_token,
    )

    trees: Final[tuple[NodeFetchResult, VertexTree | None]] = fetch_roam_trees(
        NodeFetchSpec(anchor=NodeFetchAnchor(qualifier=target), include_refs=True), True, api_endpoint
    )
    vertex_tree: Final[VertexTree | None] = trees[1]
    if vertex_tree is None:
        logger.error("vertex_tree is None; cannot export without a vertex tree")
        raise typer.Exit(code=1)

    if output_format is OutputFormat.PDF:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path: Final[pathlib.Path] = output_dir / f"{target}.pdf"
        try:
            render_pdf(vertex_tree, output_path, api_endpoint=api_endpoint, cache_dir=cache_dir)
        except Exception as e:
            logger.error("Error rendering PDF for %r: %s", target, e)
            raise typer.Exit(code=1)
    else:
        md_document: Final[str] = render_md(vertex_tree)
        if bundle:
            try:
                bundle_md_document(
                    md_text=md_document,
                    document_name=target,
                    output_dir=output_dir,
                    api_endpoint=api_endpoint,
                    cache_dir=cache_dir,
                )
            except Exception as e:
                logger.error("Error bundling %r: %s", target, e)
                raise typer.Exit(code=1)
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            md_path: Final[pathlib.Path] = output_dir / f"{target}.md"
            md_path.write_text(md_document)
            logger.info("Wrote CommonMark document to %s", md_path)


if __name__ == "__main__":
    app()
