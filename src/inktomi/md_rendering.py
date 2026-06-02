"""Render a :class:`~inktomi.graph.VertexTree` to a CommonMark document.

Converts the normalized vertex tree produced by
:func:`~inktomi.roam_transcribe.transcribe` into a CommonMark string suitable
for further processing or direct publication.

Rendering rules:

- :class:`~inktomi.graph.PageVertex` — rendered as an H1 heading
  (``# title``).
- :class:`~inktomi.graph.HeadingVertex` — rendered as a CommonMark
  heading at the vertex's recorded level (``#`` … ``######``).
- :class:`~inktomi.graph.TextContentVertex` — direct children of the
  page (depth 1) are rendered as paragraphs; deeper vertices are rendered as
  indented bullet-list items (``- text``, ``  - text``, …).
- :class:`~inktomi.graph.ImageVertex` — rendered as a CommonMark image
  link (``![alt](url)``).

Public symbols:

- :func:`render` — render a :class:`~inktomi.graph.VertexTree` to a
  CommonMark document string.
"""

import logging
from typing import Final

from inktomi.graph import (
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TextContentVertex,
    Vertex,
    VertexChildren,
    VertexTree,
)
from inktomi.roam_primitives import Uid

logger = logging.getLogger(__name__)


def render(vertex_tree: VertexTree) -> str:
    """Render *vertex_tree* to a CommonMark document string.

    The page title is rendered as an H1 heading.  Heading vertices become
    CommonMark ``#``-headings at their recorded level.  Text-content vertices
    that are direct children of the page (depth 1) are rendered as paragraphs;
    deeper text-content vertices are rendered as indented bullet-list items.
    Image vertices are rendered as CommonMark image links.

    Args:
        vertex_tree: The :class:`~inktomi.graph.VertexTree` to render.

    Returns:
        A CommonMark document string ending with a single trailing newline.
    """
    logger.debug("vertex_tree=%r", vertex_tree)
    uid_map: Final[dict[Uid, Vertex]] = {v.uid: v for v in vertex_tree.vertices}
    child_uids: Final[set[Uid]] = {uid for v in vertex_tree.vertices if v.children for uid in v.children}
    root: Final[Vertex] = next(v for v in vertex_tree.vertices if v.uid not in child_uids)
    out: Final[list[str]] = []
    _render_vertex(root, uid_map, depth=0, out=out)
    return "\n".join(out).rstrip("\n") + "\n"


def _render_children(children: VertexChildren, uid_map: dict[Uid, Vertex], depth: int, out: list[str]) -> None:
    """Render each child UID in *children* into *out* at *depth*.

    Unknown UIDs are skipped with a warning.

    Args:
        children: Ordered list of child UIDs to render.
        uid_map: Mapping from UID to :data:`~inktomi.graph.Vertex`.
        depth: Current tree depth (0 = page root).
        out: Accumulator list of output lines.
    """
    for uid in children:
        if uid not in uid_map:
            logger.warning("child uid=%r not found in uid_map; skipping", uid)
            continue
        _render_vertex(uid_map[uid], uid_map, depth, out)


def _render_vertex(vertex: Vertex, uid_map: dict[Uid, Vertex], depth: int, out: list[str]) -> None:
    """Render *vertex* and its subtree into *out* at *depth*.

    Dispatches to type-specific rendering logic via a ``match`` on the concrete
    vertex class, then recurses into children.

    Args:
        vertex: The :data:`~inktomi.graph.Vertex` to render.
        uid_map: Mapping from UID to :data:`~inktomi.graph.Vertex`.
        depth: Current tree depth (0 = page root, 1 = direct page child, …).
        out: Accumulator list of output lines.

    Raises:
        TypeError: If *vertex* is not one of the four known concrete
            :data:`~inktomi.graph.Vertex` subclasses.
    """
    logger.debug("vertex=%r, depth=%d", vertex, depth)
    match vertex:
        case PageVertex(title=title):
            out.append(f"# {title}")
            out.append("")
        case HeadingVertex(heading=heading, text=text):
            out.append(f"{'#' * heading} {text}")
            out.append("")
        case TextContentVertex(text=text):
            if depth == 1:
                out.append(text)
                out.append("")
            else:
                indent = "  " * (depth - 2)
                out.append(f"{indent}- {text}")
        case ImageVertex(source=source, alt_text=alt_text):
            alt = alt_text or ""
            out.append(f"![{alt}]({source})")
            out.append("")
        case _:
            raise TypeError(f"Unrecognized vertex type: {type(vertex).__name__!r} (uid={vertex.uid!r})")
    if vertex.children:
        _render_children(vertex.children, uid_map, depth + 1, out)
