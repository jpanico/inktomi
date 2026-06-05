"""Render a :class:`~guffin.graph.VertexTree` to a PDF via the Pandoc object model.

Converts the normalized vertex tree produced by
:func:`~guffin.roam_transcribe.transcribe` into a Panflute
:class:`~panflute.Doc` via :func:`~guffin.pandoc_rendering.vertex_tree_to_pandoc`,
then exports the document to PDF by serializing the Doc to Pandoc JSON and
invoking Pandoc via :mod:`pypandoc`.

Cloud Firestore image assets are fetched via
:func:`~guffin.pandoc_rendering.fetch_images`, written to a temporary
directory, and embedded in the PDF as local-path
:class:`~panflute.Image` elements.  An optional *cache_dir* avoids
re-downloading unchanged assets across runs.

Public symbols:

- :func:`render` — fetch image assets, build the Pandoc object model,
  and write a PDF file.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so all its symbols are typed as Unknown by pyright.
# The four suppressed rules are triggered entirely by that Unknown propagation — disabling them
# here avoids dozens of cascading false-positive errors without relaxing any other strict checks.

from io import StringIO
import logging
import tempfile
from pathlib import Path
from typing import Final

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]

from guffin.filenames import normalize_for_posix
from guffin.graph import VertexTree
from guffin.pandoc_rendering import fetch_images, vertex_tree_to_pandoc
from guffin.roam_local_api import ApiEndpoint

logger = logging.getLogger(__name__)


def render(
    vertex_tree: VertexTree,
    filename_stem: str,
    output_dir: Path,
    api_endpoint: ApiEndpoint,
    cache_dir: Path | None = None,
) -> None:
    """Render *vertex_tree* to a PDF file inside *output_dir*.

    Derives the output filename from *filename_stem* via
    :func:`~guffin.filenames.normalize_for_posix`, creating
    ``<output_dir>/<normalized_filename_stem>.pdf``.  Fetches all Cloud
    Firestore image assets into a temporary directory via
    :func:`~guffin.pandoc_rendering.fetch_images`, builds a Panflute
    :class:`~panflute.Doc` via
    :func:`~guffin.pandoc_rendering.vertex_tree_to_pandoc`, serializes it
    to Pandoc JSON, and invokes Pandoc (with the Typst PDF engine) via
    :mod:`pypandoc` to produce the PDF.  The temporary image directory is
    removed after Pandoc completes.

    Pandoc and Typst must be installed and on ``PATH``.

    Args:
        vertex_tree: The normalized vertex tree to render.
        filename_stem: String used to derive the output filename (e.g. a Roam
            page title or node UID); POSIX-normalized before use.
        output_dir: Directory in which the ``.pdf`` file is written; created
            if it does not already exist.
        api_endpoint: Roam Local API endpoint used to fetch image assets.
        cache_dir: Optional directory for caching downloaded image assets
            across runs.  Uses a SHA-256 hash of the Cloud Firestore URL as
            the cache key.

    Raises:
        RuntimeError: If Pandoc or Typst is not found, or if the Pandoc
            conversion fails.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path: Final[Path] = output_dir / f"{normalize_for_posix(filename_stem)}.pdf"

    with tempfile.TemporaryDirectory() as tmp:
        image_files = fetch_images(vertex_tree, api_endpoint, Path(tmp), cache_dir)
        doc: Final[pf.Doc] = vertex_tree_to_pandoc(vertex_tree, image_files)
        buf: Final[StringIO] = StringIO()
        pf.dump(doc, output_stream=buf)  # type: ignore[no-untyped-call]
        json_str: Final[str] = buf.getvalue()
        logger.debug("pandoc JSON length=%d bytes, output_path=%s", len(json_str), output_path)

        pypandoc.convert_text(  # type: ignore[no-untyped-call]
            json_str, "pdf", format="json", outputfile=str(output_path), extra_args=["--pdf-engine=typst"]
        )

    logger.info("Wrote PDF to %s", output_path)
