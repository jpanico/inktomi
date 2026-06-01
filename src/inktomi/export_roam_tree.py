#!/usr/bin/env python3
"""CLI tool for exporting a Roam Research page or node subtree to CommonMark.

Fetches all descendant blocks identified by ``TARGET`` via the Roam Local API,
transcribes them into a :class:`~inktomi.graph.VertexTree`, renders
the tree to a CommonMark document via :func:`~inktomi.md_rendering.render`,
then writes the result in one of two modes controlled by ``--bundle/--no-bundle``:

- **Bundle mode** (default, ``--bundle``) — fetches any Cloud Firestore images
  referenced in the document and writes a self-contained
  ``<output_dir>/<target>.mdbundle/`` directory via
  :func:`~inktomi.roam_md_bundle.bundle_md_document`.  Pass ``--cache-dir``
  to avoid re-downloading unchanged assets across runs.
- **Plain mode** (``--no-bundle``) — writes the rendered CommonMark text
  directly to ``<output_dir>/<target>.md`` without fetching any images.

``TARGET`` is interpreted as a **node UID** if it matches
:data:`~inktomi.roam_primitives.UID_PATTERN` (exactly 9 alphanumeric/dash/underscore
characters, the fixed format used by Roam for all block and page UIDs); otherwise it is
treated as a **page title**.  A page whose title happens to be exactly 9
characters from that alphabet would be misidentified — this edge case is
considered negligible in practice.

Logging is colorized by level via :mod:`inktomi.logging_config` and
configurable via the ``LOG_LEVEL`` environment variable (default: ``INFO``).

Public symbols:

- :data:`app` — the :class:`~typer.Typer` application instance.
- :func:`main` — the CLI entry point; registered as the ``export-roam-tree``
  console script.

Example::

    export-roam-tree "Test Article" -p 3333 -g SCFH -t tok -o ~/docs
    export-roam-tree wdMgyBiP9 -p 3333 -g SCFH -t tok -o ~/docs
    export-roam-tree "Test Article" -p 3333 -g SCFH -t tok -o ~/docs --no-bundle
    export-roam-tree "Test Article"  # reads all options from env vars
"""

import logging
import pathlib
from typing import Annotated, Final

import typer

from inktomi.logging_config import configure_logging
from inktomi.roam_node_fetch_result import NodeFetchAnchor, NodeFetchResult, NodeFetchSpec
from inktomi.roam_tree_loader import fetch_roam_trees
from inktomi.graph import VertexTree
from inktomi.roam_local_api import ApiEndpoint
from inktomi.roam_md_bundle import bundle_md_document
from inktomi.roam_primitives import UID_PATTERN
from inktomi.md_rendering import render

configure_logging()
logger = logging.getLogger(__name__)

app = typer.Typer()


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
            help="Directory to write the exported CommonMark document into.",
        ),
    ],
    bundle: Annotated[
        bool,
        typer.Option(
            "--bundle/--no-bundle",
            help=(
                "When enabled (default), fetches Cloud Firestore images and writes a "
                ".mdbundle directory. When disabled, writes a plain .md file instead."
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
                "Skips re-downloading unchanged assets."
            ),
        ),
    ] = None,
) -> None:
    """Export a Roam Research page or node subtree to CommonMark.

    TARGET is interpreted as a node UID (fetches the subtree rooted there) if
    it matches ``^[A-Za-z0-9_-]{9}$``, otherwise as a page title (fetches all
    blocks on that page).  With ``--bundle`` (default) the output is written to
    OUTPUT_DIR/<target>.mdbundle/ with Cloud Firestore images downloaded
    alongside; with ``--no-bundle`` a plain .md file is written instead.
    """
    logger.debug(
        "target=%r, local_api_port=%r, graph_name=%r, api_bearer_token=%r, output_dir=%r, bundle=%r, cache_dir=%r",
        target,
        local_api_port,
        graph_name,
        api_bearer_token,
        output_dir,
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
    md_document: Final[str] = render(vertex_tree)

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
        output_path: Final[pathlib.Path] = output_dir / f"{target}.md"
        output_path.write_text(md_document)
        logger.info("Wrote CommonMark document to %s", output_path)


if __name__ == "__main__":
    app()
