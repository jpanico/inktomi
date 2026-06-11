"""Shared Pandoc/panflute rendering utilities for :class:`~guffin.vertex_tree.VertexTree` → :class:`~panflute.Doc`.

Converts the normalized vertex tree produced by
:func:`~guffin.roam_tree_to_vertex_tree.transcribe` into a Panflute
:class:`~panflute.Doc` (the Pandoc object model), with inline Pandoc Markdown
properly parsed into structured panflute inline elements.

The resulting :class:`~panflute.Doc` is an output-format-neutral intermediate
representation; serializing it to a concrete target format is left to the
caller.

Inline parsing:

Text fields on :class:`~guffin.vertex.HeadingVertex` and
:class:`~guffin.vertex.TextContentVertex` contain normalized Pandoc Markdown
(e.g. ``**bold**``, ``*italic*``, `` `code` ``, ``[text]{.mark}``).
:func:`parse_inline_md` batches all unique text strings into a single
Pandoc parse call, returning a mapping from text string to the corresponding
list of panflute inline elements.  This avoids per-block subprocess overhead
while correctly handling all Pandoc Markdown inline syntax.

Rendering rules:

- :class:`~guffin.vertex.PageVertex` — when *title_in_header* is ``True``,
  title rendered as an H1 :class:`~panflute.Header` in the document body;
  when ``False``, title stored as the Pandoc document metadata ``title``.
  Children rendered at depth 1 in both cases.
- :class:`~guffin.vertex.HeadingVertex` — rendered as a
  :class:`~panflute.Header` at the vertex's recorded heading level.
- :class:`~guffin.vertex.TextContentVertex` — direct children of the page
  (depth 1) become :class:`~panflute.Para` blocks; deeper vertices are
  coalesced into :class:`~panflute.BulletList` items, with their own
  children rendered as nested :class:`~panflute.BulletList` blocks.
- :class:`~guffin.vertex.ImageVertex` — embedded as a :class:`~panflute.Image`
  element pointing at the local path from *image_files*; falls back to a
  :class:`~panflute.Link` when *image_files* has no entry for the vertex.

Public symbols:

- :func:`parse_inline_md` — batch-parse Pandoc Markdown inline text strings into
  panflute inline element lists via a single Pandoc call.
- :func:`build_child_blocks` — convert an ordered list of vertex UIDs to Pandoc
  block elements.
- :func:`vertex_tree_to_pandoc` — convert a
  :class:`~guffin.vertex_tree.VertexTree` to a Panflute :class:`~panflute.Doc`.
- :func:`pandoc_to_json` — serialize a Panflute :class:`~panflute.Doc` to a
  Pandoc JSON string, optionally writing it to a file for debugging.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so all its symbols are typed as Unknown by pyright.
# The four suppressed rules are triggered entirely by that Unknown propagation — disabling them
# here avoids dozens of cascading false-positive errors without relaxing any other strict checks.

from io import StringIO
import logging
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]

from pydantic import ConfigDict, validate_call

from guffin.vertex import (
    CalloutVertex,
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TextContentVertex,
    Vertex,
    VertexChildren,
)
from guffin.vertex_tree import VertexTree, root_vertex
from guffin.roam.primitives import Uid

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inline Pandoc Markdown parsing
# ---------------------------------------------------------------------------


@validate_call
def parse_inline_md(texts: list[str]) -> dict[str, list[pf.Inline]]:
    """Batch-parse Pandoc Markdown inline text strings into panflute inline element lists.

    Joins all unique, non-empty strings with a random sentinel paragraph as
    separator, converts the combined document to Pandoc JSON in a single
    subprocess call, then maps each input string back to the inline elements
    from its corresponding paragraph block.

    Text strings that produce no paragraph block (e.g. bare ``---``, which
    Pandoc parses as a thematic break) are absent from the returned mapping;
    callers should fall back to ``[pf.Str(text)]`` for missing entries.

    Args:
        texts: Text strings to parse.  Duplicates and empty strings are
            silently deduplicated / ignored.

    Returns:
        Mapping from each unique non-empty input string to the list of
        panflute inline elements produced by parsing it as Pandoc Markdown.
    """
    unique: Final[list[str]] = list(dict.fromkeys(t for t in texts if t))
    if not unique:
        return {}

    # Random sentinel used as a paragraph separator between entries.
    # UUID hex makes collision with real content effectively impossible.
    sep: Final[str] = f"GUFFIN_SEP_{uuid.uuid4().hex}"
    combined: Final[str] = f"\n\n{sep}\n\n".join(unique)

    json_str: Final[str] = pypandoc.convert_text(combined, "json", format="markdown")
    doc: Final[pf.Doc] = pf.load(StringIO(json_str))

    result: Final[dict[str, list[pf.Inline]]] = {}
    text_idx: int = 0

    for block in doc.content:  # `block: pf.Block`
        if text_idx >= len(unique):
            break
        block_inlines: list[pf.Inline] = list(block.content) if hasattr(block, "content") else []
        # Sentinel paragraph → advance to the next text entry.
        if (
            isinstance(block, pf.Para)
            and len(block_inlines) == 1
            and isinstance(block_inlines[0], pf.Str)
            and block_inlines[0].text == sep
        ):
            text_idx += 1
            continue
        # First Para or Plain block for the current text → record its inlines.
        if isinstance(block, (pf.Para, pf.Plain)) and unique[text_idx] not in result:
            result[unique[text_idx]] = block_inlines

    return result


# ---------------------------------------------------------------------------
# Pandoc document building
# ---------------------------------------------------------------------------


def _build_list_item(
    vertex: TextContentVertex,
    uid_map: Mapping[Uid, Vertex],
    image_files: dict[Uid, Path],
    inline_map: dict[str, list[pf.Inline]],
    depth: int,
) -> pf.ListItem:
    """Build a Pandoc :class:`~panflute.ListItem` from a :class:`~guffin.vertex.TextContentVertex`.

    The item body is a :class:`~panflute.Plain` inline block.  If the vertex
    has children they are rendered recursively via :func:`build_child_blocks` and
    appended as nested :class:`~panflute.BulletList` blocks inside the item.

    Args:
        vertex: The text-content vertex to render as a list item.
        uid_map: Mapping from UID to :data:`~guffin.vertex.Vertex`.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
        depth: Tree depth of *vertex* (≥ 2 when this function is called).

    Returns:
        A :class:`~panflute.ListItem` wrapping the vertex text and any
        nested children.
    """
    inlines: Final[list[pf.Inline]] = inline_map.get(vertex.text, [pf.Str(vertex.text)])
    content: list[pf.Block] = [pf.Plain(*inlines)]
    if vertex.children:
        content.extend(build_child_blocks(vertex.children, uid_map, image_files, inline_map, depth + 1))
    return pf.ListItem(*content)


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def build_child_blocks(
    child_uids: VertexChildren,
    uid_map: Mapping[Uid, Vertex],
    image_files: dict[Uid, Path],
    inline_map: dict[str, list[pf.Inline]],
    depth: int,
) -> list[pf.Block]:
    """Build a list of Pandoc block elements from an ordered list of child UIDs.

    Consecutive :class:`~guffin.vertex.TextContentVertex` siblings at
    *depth* > 1 are coalesced into a single :class:`~panflute.BulletList`.
    Any non-text vertex (or text vertex at depth 1) flushes the pending list
    and is rendered via :func:`_vertex_to_blocks`.

    Unknown UIDs (not in *uid_map*) are skipped with a warning.

    Args:
        child_uids: Ordered list of child UIDs to render.
        uid_map: Mapping from UID to :data:`~guffin.vertex.Vertex`.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
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
        vertex: Vertex = uid_map[uid]
        if isinstance(vertex, TextContentVertex) and depth > 1:
            pending_items.append(_build_list_item(vertex, uid_map, image_files, inline_map, depth))
        else:
            if pending_items:
                result.append(pf.BulletList(*pending_items))
                pending_items.clear()
            result.extend(_vertex_to_blocks(vertex, uid_map, image_files, inline_map, depth))

    if pending_items:
        result.append(pf.BulletList(*pending_items))
        pending_items.clear()

    return result


def _page_vertex_to_blocks(
    vertex: PageVertex,
    uid_map: Mapping[Uid, Vertex],
    image_files: dict[Uid, Path],
    inline_map: dict[str, list[pf.Inline]],
) -> list[pf.Block]:
    """Render a :class:`~guffin.vertex.PageVertex` to Pandoc block elements.

    Delegates to :func:`build_child_blocks` at depth 1.  The page title is
    handled separately by :func:`vertex_tree_to_pandoc`.

    Args:
        vertex: The page vertex to render.
        uid_map: Mapping from UID to :data:`~guffin.vertex.Vertex`.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.

    Returns:
        Block elements for the page's children, rendered at depth 1.
    """
    return build_child_blocks(vertex.children or [], uid_map, image_files, inline_map, 1)


def _heading_vertex_to_blocks(
    vertex: HeadingVertex,
    uid_map: Mapping[Uid, Vertex],
    image_files: dict[Uid, Path],
    inline_map: dict[str, list[pf.Inline]],
    depth: int,
) -> list[pf.Block]:
    """Render a :class:`~guffin.vertex.HeadingVertex` to Pandoc block elements.

    Produces one :class:`~panflute.Header` at the vertex's heading level,
    followed by the recursively rendered children.

    Args:
        vertex: The heading vertex to render.
        uid_map: Mapping from UID to :data:`~guffin.vertex.Vertex`.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
        depth: Tree depth of *vertex*.

    Returns:
        A :class:`~panflute.Header` block followed by any child blocks.
    """
    inlines: Final[list[pf.Inline]] = inline_map.get(vertex.text, [pf.Str(vertex.text)])
    blocks: list[pf.Block] = [pf.Header(*inlines, level=vertex.heading_level)]
    if vertex.children:
        blocks.extend(build_child_blocks(vertex.children, uid_map, image_files, inline_map, depth + 1))
    return blocks


def _text_content_vertex_to_blocks(
    vertex: TextContentVertex,
    uid_map: Mapping[Uid, Vertex],
    image_files: dict[Uid, Path],
    inline_map: dict[str, list[pf.Inline]],
    depth: int,
) -> list[pf.Block]:
    """Render a :class:`~guffin.vertex.TextContentVertex` to Pandoc block elements.

    At depth 1: one :class:`~panflute.Para` followed by the recursively rendered
    children.  At depth > 1: a single-item :class:`~panflute.BulletList` (sibling
    grouping at list depth is handled by :func:`build_child_blocks`).

    Args:
        vertex: The text-content vertex to render.
        uid_map: Mapping from UID to :data:`~guffin.vertex.Vertex`.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
        depth: Tree depth of *vertex* (1 = direct page child).

    Returns:
        A :class:`~panflute.Para` with children at depth 1, or a
        single-item :class:`~panflute.BulletList` at depth > 1.
    """
    text_inlines: Final[list[pf.Inline]] = inline_map.get(vertex.text, [pf.Str(vertex.text)])
    if depth <= 1:
        para_blocks: list[pf.Block] = [pf.Para(*text_inlines)]
        if vertex.children:
            para_blocks.extend(build_child_blocks(vertex.children, uid_map, image_files, inline_map, depth + 1))
        return para_blocks
    else:
        return [pf.BulletList(_build_list_item(vertex, uid_map, image_files, inline_map, depth))]


def _image_vertex_to_blocks(
    vertex: ImageVertex,
    image_files: dict[Uid, Path],
    inline_map: dict[str, list[pf.Inline]],
) -> list[pf.Block]:
    """Render an :class:`~guffin.vertex.ImageVertex` to Pandoc block elements.

    Produces a :class:`~panflute.Para` containing a :class:`~panflute.Image`
    if the asset was fetched, or a :class:`~panflute.Link` fallback otherwise.

    Args:
        vertex: The image vertex to render.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.

    Returns:
        A :class:`~panflute.Para` wrapping either an embedded image or a
        hyperlink fallback.
    """
    img_path: Path | None = image_files.get(vertex.uid)
    if img_path is not None:
        alt: Final[list[pf.Inline]] = (
            inline_map.get(vertex.alt_text, [pf.Str(vertex.alt_text)]) if vertex.alt_text else []
        )
        img: Final[pf.Image] = pf.Image(*alt, url=str(img_path), title=vertex.file_name or "")
        return [pf.Para(img)]
    else:
        label_text: Final[str] = vertex.alt_text or vertex.file_name or str(vertex.source)
        label: Final[list[pf.Inline]] = inline_map.get(label_text, [pf.Str(label_text)])
        link: Final[pf.Link] = pf.Link(*label, url=str(vertex.source))
        logger.warning("Image uid=%r not fetched; rendering as link", vertex.uid)
        return [pf.Para(link)]


def _callout_vertex_to_blocks(
    vertex: CalloutVertex,
    uid_map: Mapping[Uid, Vertex],
    image_files: dict[Uid, Path],
    inline_map: dict[str, list[pf.Inline]],
    depth: int,
) -> list[pf.Block]:
    """Render a :class:`~guffin.vertex.CalloutVertex` to Pandoc block elements.

    Produces a :class:`~panflute.Div` with classes ``["callout",
    "callout-{type}"]`` where *type* is the lowercased
    :class:`~guffin.vertex.CalloutVertex.CalloutType` value (one of the
    twelve recognised keywords: ``info``, ``note``, ``quote``, ``example``,
    ``summary``, ``question``, ``tip``, ``success``, ``warning``,
    ``danger``, ``failure``, ``bug``).  When a title is present, the first
    child is a ``callout-title`` :class:`~panflute.Div` whose content is a
    :class:`~panflute.Para` with the parsed inline elements.  The body
    (if any) is re-parsed as block-level Markdown and appended as sibling
    blocks inside the outer :class:`~panflute.Div`.  Child vertex blocks
    follow at the end.

    Output-format-specific transformation is applied by a Lua filter in
    the respective rendering module (GFM blockquote alert syntax or Typst
    ``gentle-clues`` callout boxes).

    Args:
        vertex: The callout vertex to render.
        uid_map: Mapping from UID to :data:`~guffin.vertex.Vertex`.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
        depth: Tree depth of *vertex*.

    Returns:
        A single-element list containing the :class:`~panflute.Div`.
    """
    callout_type: Final[str] = vertex.callout_type.value.lower()
    callout_blocks: list[pf.Block] = []
    if vertex.title:
        title_inlines: Final[list[pf.Inline]] = inline_map.get(vertex.title, [pf.Str(vertex.title)])
        callout_blocks.append(pf.Div(pf.Para(*title_inlines), classes=["callout-title"]))
    if vertex.body:
        # Insert blank lines at block-type boundaries except between consecutive
        # list items (which would create a loose list with unwanted inter-item spacing).
        body_lines: Final[list[str]] = vertex.body.splitlines()
        joined_lines: list[str] = []
        for i, line in enumerate(body_lines):
            if i > 0:
                prev_is_list: bool = body_lines[i - 1].startswith(("- ", "* ", "+ "))
                curr_is_list: bool = line.startswith(("- ", "* ", "+ "))
                if not (prev_is_list and curr_is_list):
                    joined_lines.append("")
            joined_lines.append(line)
        body_json: Final[str] = pypandoc.convert_text(  # type: ignore[no-untyped-call]
            "\n".join(joined_lines), "json", format="markdown"
        )
        body_doc: Final[pf.Doc] = pf.load(StringIO(body_json))
        callout_blocks.extend(list(body_doc.content))
    if vertex.children:
        callout_blocks.extend(build_child_blocks(vertex.children, uid_map, image_files, inline_map, depth + 1))
    return [pf.Div(*callout_blocks, classes=["callout", f"callout-{callout_type}"])]


def _vertex_to_blocks(
    vertex: Vertex,
    uid_map: Mapping[Uid, Vertex],
    image_files: dict[Uid, Path],
    inline_map: dict[str, list[pf.Inline]],
    depth: int,
) -> list[pf.Block]:
    """Dispatch a single :data:`~guffin.vertex.Vertex` to its type-specific rendering function.

    Args:
        vertex: The vertex to convert.
        uid_map: Mapping from UID to :data:`~guffin.vertex.Vertex`.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
        depth: Tree depth of *vertex* (0 = root, 1 = direct page child, …).

    Returns:
        A list of :class:`~panflute.Block` elements representing *vertex*
        and its subtree.
    """
    match vertex:
        case PageVertex():
            return _page_vertex_to_blocks(vertex, uid_map, image_files, inline_map)
        case HeadingVertex():
            return _heading_vertex_to_blocks(vertex, uid_map, image_files, inline_map, depth)
        case TextContentVertex():
            return _text_content_vertex_to_blocks(vertex, uid_map, image_files, inline_map, depth)
        case ImageVertex():
            return _image_vertex_to_blocks(vertex, image_files, inline_map)
        case CalloutVertex():
            return _callout_vertex_to_blocks(vertex, uid_map, image_files, inline_map, depth)


@validate_call
def vertex_tree_to_pandoc(
    vertex_tree: VertexTree,
    image_files: dict[Uid, Path],
    *,
    title_in_header: bool = False,
) -> pf.Doc:
    """Convert a :class:`~guffin.vertex_tree.VertexTree` to a Panflute :class:`~panflute.Doc`.

    Collects all text strings from the tree, parses their inline Pandoc Markdown
    in a single Pandoc call, then walks the tree to build Pandoc block
    elements.

    The *title_in_header* flag controls how a root
    :class:`~guffin.vertex.PageVertex` title is rendered:

    - ``False`` (default, PDF path) — title stored as the Pandoc metadata
      ``title`` field; children rendered as body blocks.
    - ``True`` (Markdown path) — title rendered as a level-1
      :class:`~panflute.Header` prepended to the body blocks; no metadata.

    Args:
        vertex_tree: The normalized vertex tree to convert.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            the local :class:`~pathlib.Path` of the fetched image file.
            Vertices absent from this mapping fall back to hyperlinks.
            Pass relative :class:`~pathlib.Path` values (e.g.
            ``Path(filename)``) when the output is Markdown, so that image
            references in the rendered document are relative rather than
            absolute.
        title_in_header: When ``True``, render a root
            :class:`~guffin.vertex.PageVertex` title as an H1 header instead
            of storing it in document metadata.  Defaults to ``False``.

    Returns:
        A :class:`~panflute.Doc` ready for serialization via
        :func:`panflute.dump` and subsequent Pandoc conversion.
    """
    uid_map: Final[dict[Uid, Vertex]] = {v.uid: v for v in vertex_tree.vertices}
    root: Final[Vertex] = root_vertex(vertex_tree)

    # Collect all text strings for batch inline parsing.
    texts: Final[list[str]] = []
    for vertex in vertex_tree.vertices:
        match vertex:
            case PageVertex(title=t):
                texts.append(t)
            case HeadingVertex(text=t):
                texts.append(t)
            case TextContentVertex(text=t):
                texts.append(t)
            case ImageVertex(alt_text=t) if t is not None:
                texts.append(t)
            case CalloutVertex(title=t) if t:
                texts.append(t)
            case _:
                pass
    inline_map: Final[dict[str, list[pf.Inline]]] = parse_inline_md(texts)

    metadata: dict[str, pf.MetaValue] = {}
    blocks: list[pf.Block] = []

    if isinstance(root, PageVertex):
        title_inlines: Final[list[pf.Inline]] = inline_map.get(root.title, [pf.Str(root.title)])
        if title_in_header:
            blocks.append(pf.Header(*title_inlines, level=1))
        else:
            metadata["title"] = pf.MetaInlines(*title_inlines)
        blocks.extend(build_child_blocks(root.children or [], uid_map, image_files, inline_map, depth=1))
    else:
        blocks.extend(_vertex_to_blocks(root, uid_map, image_files, inline_map, depth=0))

    return pf.Doc(*blocks, metadata=metadata)


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def pandoc_to_json(
    doc: pf.Doc,
    dump_pandoc_ast: bool = False,
    ast_dump_dir: Path | None = None,
    ast_dump_stem: str | None = None,
) -> str:
    """Serialize *doc* to a Pandoc JSON string.

    Dumps *doc* via :func:`panflute.dump` and returns the resulting JSON
    string.  When *dump_pandoc_ast* is ``True`` and both *ast_dump_dir* and
    *ast_dump_stem* are provided, the JSON is also written to
    ``<ast_dump_dir>/<ast_dump_stem>.pandoc.json`` before being returned —
    useful for inspecting the intermediate Pandoc AST without modifying the
    main rendering pipeline.

    Args:
        doc: The Panflute document to serialize.
        dump_pandoc_ast: When ``True``, write the JSON to disk alongside the
            primary output.  Requires *ast_dump_dir* and *ast_dump_stem*.
        ast_dump_dir: Directory in which to write the ``.pandoc.json`` file.
            Ignored when *dump_pandoc_ast* is ``False``.
        ast_dump_stem: POSIX-normalized filename stem (no extension) used to
            construct the dump filename.  Ignored when *dump_pandoc_ast* is
            ``False``.

    Returns:
        The Pandoc JSON representation of *doc*.
    """
    buf: Final[StringIO] = StringIO()
    pf.dump(doc, output_stream=buf)  # type: ignore[no-untyped-call]
    json_str: Final[str] = buf.getvalue()
    if dump_pandoc_ast and ast_dump_dir is not None and ast_dump_stem is not None:
        ast_dump_path: Final[Path] = ast_dump_dir / f"{ast_dump_stem}.pandoc.json"
        ast_dump_path.write_text(json_str, encoding="utf-8")
        logger.info("Wrote Pandoc AST to %s", ast_dump_path)
    return json_str
