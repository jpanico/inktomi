"""Render a :class:`~guffin.graph.VertexTree` to a PDF via the Pandoc object model.

Converts the normalized vertex tree produced by
:func:`~guffin.roam_transcribe.transcribe` directly into a Panflute
:class:`~panflute.Doc` (the Pandoc object model), then exports the
document to PDF by serializing the Doc to Pandoc JSON and invoking
Pandoc via :mod:`pypandoc`.

This renderer is intentionally independent of
:mod:`~guffin.md_rendering` — it does **not** go through the
CommonMark rendering path.

Cloud Firestore image assets referenced by
:class:`~guffin.graph.ImageVertex` nodes are fetched via
:func:`~guffin.roam_asset_fetch.FetchRoamAsset.fetch` (the same path
used by the Markdown bundle mode), written to a temporary directory,
and embedded in the PDF as local-path :class:`~panflute.Image` elements.
An optional *cache_dir* avoids re-downloading unchanged assets across
runs.

Rendering rules:

- :class:`~guffin.graph.PageVertex` — page title stored as the Pandoc
  document metadata ``title`` (rendered as a title block in PDF); children
  rendered at depth 1.
- :class:`~guffin.graph.HeadingVertex` — rendered as a Pandoc
  :class:`~panflute.Header` at the vertex's recorded heading level.
- :class:`~guffin.graph.TextContentVertex` — direct children of the
  page (depth 1) become :class:`~panflute.Para` blocks; deeper vertices
  are coalesced into :class:`~panflute.BulletList` items, with their own
  children rendered as nested :class:`~panflute.BulletList` blocks.
- :class:`~guffin.graph.ImageVertex` — fetched from Cloud Firestore,
  written to a temp file, and embedded as a :class:`~panflute.Image`
  element.  Falls back to a :class:`~panflute.Link` if the fetch fails.

.. note::

    Text fields on :class:`~guffin.graph.HeadingVertex` and
    :class:`~guffin.graph.TextContentVertex` contain normalized
    CommonMark (inline Markdown such as ``**bold**`` or ``_italic_``).
    This renderer wraps text verbatim in :class:`~panflute.Str` inline
    elements, so inline formatting is **not** interpreted — it will
    appear literally in the PDF.  This is a known limitation for a
    future improvement.

Public symbols:

- :func:`build_blocks` — convert an ordered list of vertex UIDs to Pandoc block elements.
- :func:`vertex_tree_to_pandoc` — convert a :class:`~guffin.graph.VertexTree`
  to a Panflute :class:`~panflute.Doc`.
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
from collections.abc import Mapping
from typing import Final

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]

from guffin.filenames import normalize_for_posix
from guffin.graph import (
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TextContentVertex,
    Vertex,
    VertexChildren,
    VertexTree,
)
from guffin.roam_asset_fetch import fetch_and_cache_asset
from guffin.roam_local_api import ApiEndpoint
from guffin.roam_primitives import Uid

logger = logging.getLogger(__name__)


def _fetch_images(
    vertex_tree: VertexTree,
    api_endpoint: ApiEndpoint,
    image_dir: Path,
    cache_dir: Path | None = None,
) -> dict[Uid, Path]:
    """Fetch all :class:`~guffin.graph.ImageVertex` assets to *image_dir*.

    Delegates fetching and caching to
    :func:`~guffin.roam_asset_fetch.fetch_and_cache_asset`.  Each fetched
    asset is written to *image_dir* under its deterministic
    ``<sha256>.<ext>`` filename.  Vertices that fail to fetch are skipped
    with a warning and will fall back to a hyperlink in the PDF.

    Args:
        vertex_tree: The vertex tree whose image assets to fetch.
        api_endpoint: Roam Local API endpoint (URL + bearer token).
        image_dir: Directory where fetched image files are written.
        cache_dir: Optional directory for caching downloaded assets across
            runs; forwarded to :func:`~guffin.roam_asset_fetch.fetch_and_cache_asset`.

    Returns:
        A mapping from :class:`~guffin.graph.ImageVertex` UID to the
        local :class:`~pathlib.Path` of the fetched image file.  Vertices
        that could not be fetched are absent from the mapping.
    """
    image_files: dict[Uid, Path] = {}

    for vertex in vertex_tree.vertices:
        if not isinstance(vertex, ImageVertex):
            continue
        try:
            asset = fetch_and_cache_asset(vertex.source, api_endpoint, cache_dir)
            img_path: Path = image_dir / asset.file_name
            img_path.write_bytes(asset.contents)
            image_files[vertex.uid] = img_path
            logger.info("Fetched image uid=%r -> %s", vertex.uid, img_path.name)
        except Exception as e:
            logger.warning("Failed to fetch image uid=%r source=%s: %s", vertex.uid, vertex.source, e)

    return image_files


def _inlines(text: str) -> list[pf.Inline]:
    """Wrap *text* in a single-element :class:`~panflute.Str` inline list.

    Inline CommonMark formatting (bold, italic, links) present in *text* is
    **not** interpreted — the raw text is passed through verbatim as a
    :class:`~panflute.Str` element.

    Args:
        text: Plain or CommonMark-formatted text string.

    Returns:
        A one-element list containing ``panflute.Str(text)``.
    """
    return [pf.Str(text)]


def _build_list_item(
    vertex: TextContentVertex,
    uid_map: Mapping[Uid, Vertex],
    image_files: dict[Uid, Path],
    depth: int,
) -> pf.ListItem:
    """Build a Pandoc :class:`~panflute.ListItem` from a :class:`~guffin.graph.TextContentVertex`.

    The item body is a :class:`~panflute.Plain` inline block.  If the vertex
    has children they are rendered recursively via :func:`build_blocks` and
    appended as nested :class:`~panflute.BulletList` blocks inside the item.

    Args:
        vertex: The text-content vertex to render as a list item.
        uid_map: Mapping from UID to :data:`~guffin.graph.Vertex`.
        image_files: Mapping from :class:`~guffin.graph.ImageVertex` UID to
            local image file path.
        depth: Tree depth of *vertex* (≥ 2 when this function is called).

    Returns:
        A :class:`~panflute.ListItem` wrapping the vertex text and any
        nested children.
    """
    content: list[pf.Block] = [pf.Plain(*_inlines(vertex.text))]
    if vertex.children:
        content.extend(build_blocks(vertex.children, uid_map, image_files, depth + 1))
    return pf.ListItem(*content)


def build_blocks(
    child_uids: VertexChildren,
    uid_map: Mapping[Uid, Vertex],
    image_files: dict[Uid, Path],
    depth: int,
) -> list[pf.Block]:
    """Build a list of Pandoc block elements from an ordered list of child UIDs.

    Consecutive :class:`~guffin.graph.TextContentVertex` siblings at
    *depth* > 1 are coalesced into a single :class:`~panflute.BulletList`.
    Any non-text vertex (or text vertex at depth 1) flushes the pending list
    and is rendered via :func:`_vertex_to_blocks`.

    Unknown UIDs (not in *uid_map*) are skipped with a warning.

    Args:
        child_uids: Ordered list of child UIDs to render.
        uid_map: Mapping from UID to :data:`~guffin.graph.Vertex`.
        image_files: Mapping from :class:`~guffin.graph.ImageVertex` UID to
            local image file path.
        depth: Tree depth of the children (1 = direct children of the page root).

    Returns:
        A flat list of :class:`~panflute.Block` elements representing the
        rendered children, with consecutive list-depth text vertices grouped
        into :class:`~panflute.BulletList` blocks.
    """
    result: Final[list[pf.Block]] = []
    pending_items: Final[list[pf.ListItem]] = []

    for uid in child_uids:
        if uid not in uid_map:
            logger.warning("child uid=%r not found in uid_map; skipping", uid)
            continue
        vertex = uid_map[uid]
        if isinstance(vertex, TextContentVertex) and depth > 1:
            pending_items.append(_build_list_item(vertex, uid_map, image_files, depth))
        else:
            if pending_items:
                result.append(pf.BulletList(*pending_items))
                pending_items.clear()
            result.extend(_vertex_to_blocks(vertex, uid_map, image_files, depth))

    if pending_items:
        result.append(pf.BulletList(*pending_items))
        pending_items.clear()

    return result


def _vertex_to_blocks(
    vertex: Vertex,
    uid_map: Mapping[Uid, Vertex],
    image_files: dict[Uid, Path],
    depth: int,
) -> list[pf.Block]:
    """Convert a single :data:`~guffin.graph.Vertex` to Pandoc block elements.

    Dispatches on the concrete vertex type:

    - :class:`~guffin.graph.PageVertex`: renders children at depth 1 (title
      handled via metadata in :func:`vertex_tree_to_pandoc`).
    - :class:`~guffin.graph.HeadingVertex`: one :class:`~panflute.Header` at
      the vertex's heading level, followed by children at ``depth + 1``.
    - :class:`~guffin.graph.TextContentVertex` at depth 1: one
      :class:`~panflute.Para`, followed by children.
    - :class:`~guffin.graph.TextContentVertex` at depth > 1: wrapped in a
      single-item :class:`~panflute.BulletList` (normally reached only from
      :func:`build_blocks` which handles sibling grouping).
    - :class:`~guffin.graph.ImageVertex`: a :class:`~panflute.Para`
      containing a :class:`~panflute.Image` (local temp file path) if the
      asset was fetched, or a :class:`~panflute.Link` fallback otherwise.

    Args:
        vertex: The vertex to convert.
        uid_map: Mapping from UID to :data:`~guffin.graph.Vertex`.
        image_files: Mapping from :class:`~guffin.graph.ImageVertex` UID to
            local image file path.
        depth: Tree depth of *vertex* (0 = root, 1 = direct page child, …).

    Returns:
        A list of :class:`~panflute.Block` elements representing *vertex*
        and its subtree.
    """
    match vertex:
        case PageVertex():
            return build_blocks(vertex.children or [], uid_map, image_files, 1)
        case HeadingVertex():
            blocks: list[pf.Block] = [pf.Header(*_inlines(vertex.text), level=vertex.heading)]
            if vertex.children:
                blocks.extend(build_blocks(vertex.children, uid_map, image_files, depth + 1))
            return blocks
        case TextContentVertex():
            if depth <= 1:
                para_blocks: list[pf.Block] = [pf.Para(*_inlines(vertex.text))]
                if vertex.children:
                    para_blocks.extend(build_blocks(vertex.children, uid_map, image_files, depth + 1))
                return para_blocks
            else:
                return [pf.BulletList(_build_list_item(vertex, uid_map, image_files, depth))]
        case ImageVertex():
            img_path: Path | None = image_files.get(vertex.uid)
            if img_path is not None:
                alt: list[pf.Inline] = _inlines(vertex.alt_text or "")
                img: pf.Image = pf.Image(*alt, url=str(img_path), title=vertex.file_name or "")
                return [pf.Para(img)]
            else:
                # Fallback when the asset could not be fetched.
                label: list[pf.Inline] = _inlines(vertex.alt_text or vertex.file_name or str(vertex.source))
                link: pf.Link = pf.Link(*label, url=str(vertex.source))
                logger.warning("Image uid=%r not fetched; rendering as link", vertex.uid)
                return [pf.Para(link)]


def vertex_tree_to_pandoc(vertex_tree: VertexTree, image_files: dict[Uid, Path]) -> pf.Doc:
    """Convert a :class:`~guffin.graph.VertexTree` to a Panflute :class:`~panflute.Doc`.

    Locates the root vertex (the one not referenced as a child by any other
    vertex), builds the Pandoc block list via :func:`_vertex_to_blocks`, and
    stores the page title (when the root is a
    :class:`~guffin.graph.PageVertex`) as the ``title`` metadata entry so
    that PDF templates render it as a proper title block.

    Args:
        vertex_tree: The normalized vertex tree to convert.
        image_files: Mapping from :class:`~guffin.graph.ImageVertex` UID to
            local image file path, as returned by :func:`_fetch_images`.

    Returns:
        A :class:`~panflute.Doc` ready for serialization and PDF export.
    """
    uid_map: Final[dict[Uid, Vertex]] = {v.uid: v for v in vertex_tree.vertices}
    child_uids: Final[set[Uid]] = {uid for v in vertex_tree.vertices if v.children for uid in v.children}
    root: Final[Vertex] = next(v for v in vertex_tree.vertices if v.uid not in child_uids)

    blocks: Final[list[pf.Block]] = _vertex_to_blocks(root, uid_map, image_files, depth=0)

    metadata: dict[str, pf.MetaValue] = {}
    if isinstance(root, PageVertex):
        metadata["title"] = pf.MetaInlines(pf.Str(root.title))

    return pf.Doc(*blocks, metadata=metadata)


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
    Firestore image assets into a temporary directory, builds a Panflute
    :class:`~panflute.Doc` via :func:`vertex_tree_to_pandoc`, serializes it
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
        image_dir: Path = Path(tmp)
        image_files: dict[Uid, Path] = _fetch_images(vertex_tree, api_endpoint, image_dir, cache_dir)

        doc: Final[pf.Doc] = vertex_tree_to_pandoc(vertex_tree, image_files)
        buf: Final[StringIO] = StringIO()
        pf.dump(doc, output_stream=buf)  # type: ignore[no-untyped-call]
        json_str: Final[str] = buf.getvalue()
        logger.debug("pandoc JSON length=%d bytes, output_path=%s", len(json_str), output_path)

        pypandoc.convert_text(  # type: ignore[no-untyped-call]
            json_str, "pdf", format="json", outputfile=str(output_path), extra_args=["--pdf-engine=typst"]
        )

    logger.info("Wrote PDF to %s", output_path)
