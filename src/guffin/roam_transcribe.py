"""Transcribe `RoamNode` to `Vertex`.

Public symbols:

- :data:`SHOULD_NORMALIZE_HEADING_LEVELS` — whether heading levels should be
  normalized during transcription.
- :func:`vertex_type` — classify a :class:`~guffin.roam_node.RoamNode` into a
  :class:`~guffin.graph.VertexType`.
- :func:`to_page_vertex` — build a :class:`~guffin.graph.PageVertex` from a
  page node.
- :func:`to_image_vertex` — build an :class:`~guffin.graph.ImageVertex` from a
  Firestore image block node.
- :func:`to_heading_vertex` — build a :class:`~guffin.graph.HeadingVertex` from
  a heading block node.
- :func:`to_text_content_vertex` — build a
  :class:`~guffin.graph.TextContentVertex` from a plain text block node.
- :func:`transcribe_node` — transcribe a :class:`~guffin.roam_node.RoamNode` into
  the appropriate :data:`~guffin.graph.Vertex` subtype.
- :func:`transcribe` — transcribe all nodes in a :class:`~guffin.roam_tree.NodeTree`
  into a :class:`~guffin.graph.VertexTree`.
"""

import logging
import re
from typing import Final
from urllib.parse import unquote, urlparse

from pydantic import TypeAdapter, validate_call

from guffin.graph import (
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TextContentVertex,
    Vertex,
    VertexChildren,
    VertexRefs,
    VertexTree,
    VertexType,
)
from guffin.roam_md_to_pandoc_md import to_pandoc_md
from guffin.roam_network import min_effective_heading_level
from guffin.roam_node import NodeType, RoamNode, effective_heading_level, node_type
from guffin.roam_tree import NodeTree
from guffin.media_type import MediaType
from guffin.roam_primitives import IMAGE_LINK_RE, HeadingLevel, Id, Url

logger = logging.getLogger(__name__)

SHOULD_NORMALIZE_HEADING_LEVELS: Final[bool] = True
"""Whether heading levels should be normalized during transcription."""

_url_adapter: TypeAdapter[Url] = TypeAdapter(Url)
"""Pydantic :class:`~pydantic.TypeAdapter` for validating and coercing URL strings to.

:data:`~guffin.roam_primitives.Url`.
"""


def _resolve_children(node: RoamNode, id_map: dict[Id, RoamNode]) -> VertexChildren | None:
    """Return an ordered list of child UIDs for *node*, or ``None`` if childless.

    Children are sorted by :attr:`~guffin.roam_node.RoamNode.order`.  Stubs
    whose id is absent from *id_map* are silently dropped.

    Args:
        node: The node whose children are to be resolved.
        id_map: Mapping from Datomic entity id to :class:`~guffin.roam_node.RoamNode`.

    Returns:
        Sorted list of child UIDs, or ``None`` when *node* has no children or
        all child stubs are unresolvable.
    """
    if not node.children:
        return None
    resolved: Final[list[RoamNode]] = sorted(
        [id_map[c.id] for c in node.children if c.id in id_map],
        key=lambda n: n.order if n.order is not None else 0,
    )
    uids: Final[VertexChildren] = [n.uid for n in resolved]
    return uids if uids else None


def _resolve_refs(node: RoamNode, id_map: dict[Id, RoamNode]) -> VertexRefs | None:
    """Return a list of referenced UIDs for *node*, or ``None`` if there are no refs.

    Stubs whose id is absent from *id_map* are silently dropped.

    Args:
        node: The node whose refs are to be resolved.
        id_map: Mapping from Datomic entity id to :class:`~guffin.roam_node.RoamNode`.

    Returns:
        List of referenced UIDs, or ``None`` when *node* has no refs or all ref
        stubs are unresolvable.
    """
    if not node.refs:
        return None
    resolved: Final[VertexRefs] = [id_map[r.id].uid for r in node.refs if r.id in id_map]
    return resolved if resolved else None


def _extract_firestore_url(string: str) -> str | None:
    """Return the Cloud Firestore storage URL embedded in *string*, or ``None`` if absent.

    Args:
        string: A raw block string that may contain a Roam markdown image link.

    Returns:
        The URL string captured from the first Firestore image link, or ``None``.
    """
    m: Final[re.Match[str] | None] = IMAGE_LINK_RE.search(string)
    return m.group("url") if m else None


def _extract_alt_text(string: str) -> str | None:
    """Return the alt text from the first Firestore image link in *string*, or ``None``.

    The captured alt text is stripped of leading and trailing whitespace.  Returns
    ``None`` when no Firestore image link is found or the alt text is empty after
    stripping.

    Args:
        string: A raw block string that may contain a Roam markdown image link.

    Returns:
        The stripped alt text string, or ``None``.
    """
    m: Final[re.Match[str] | None] = IMAGE_LINK_RE.search(string)
    if m is None:
        return None
    alt: Final[str] = m.group("alt").strip()
    return alt if alt else None


def _extract_file_name(firestore_url: str) -> str | None:
    """Return the original filename encoded in a Firestore URL, or ``None`` on failure.

    Firestore URLs encode the object path after ``/o/`` using percent-encoding.
    The filename is the last path segment after URL-decoding.

    Args:
        firestore_url: A ``https://firebasestorage.googleapis.com/...`` URL string.

    Returns:
        The decoded filename (e.g. ``"image.png"``), or ``None`` if extraction fails.
    """
    try:
        path = urlparse(firestore_url).path
        parts = path.split("/o/", maxsplit=1)
        if len(parts) == 2:
            return unquote(parts[1]).split("/")[-1]
    except Exception:
        pass
    return None


@validate_call
def vertex_type(node: RoamNode) -> VertexType:
    """Classify *node* into a :class:`~guffin.graph.VertexType`.

    Dispatches on :func:`~guffin.roam_node.node_type` for a direct
    :class:`~guffin.roam_node.NodeType` → :class:`~guffin.graph.VertexType` mapping.

    Args:
        node: The raw Roam node to classify.

    Returns:
        The :class:`~guffin.graph.VertexType` for *node*.

    Raises:
        NotImplementedError: If *node* is a :attr:`~guffin.roam_node.NodeType.ROAM_EMBED_BLOCK`.
        ValidationError: If *node* is ``None`` or invalid.
    """
    logger.debug("node=%r", node)
    match node_type(node):
        case NodeType.ROAM_PAGE:
            return VertexType.GUFFIN_PAGE
        case NodeType.ROAM_PLAIN_BLOCK:
            return VertexType.GUFFIN_TEXT_CONTENT
        case NodeType.ROAM_HEADING_BLOCK:
            return VertexType.GUFFIN_HEADING
        case NodeType.ROAM_IMAGE_BLOCK:
            return VertexType.GUFFIN_IMAGE
        case NodeType.ROAM_CALLOUT_BLOCK:
            return VertexType.GUFFIN_TEXT_CONTENT
        case NodeType.ROAM_EMBED_BLOCK:
            raise NotImplementedError(f"RoamNode uid={node.uid!r}: ROAM_EMBED_BLOCK transcription is not supported")


@validate_call
def to_page_vertex(node: RoamNode, id_map: dict[Id, RoamNode]) -> PageVertex:
    """Build a :class:`~guffin.graph.PageVertex` from *node*.

    Args:
        node: A page node with ``node.title`` set.
        id_map: Mapping from Datomic entity id to :class:`~guffin.roam_node.RoamNode`,
            used to resolve child and ref stubs to UIDs.

    Returns:
        A :class:`~guffin.graph.PageVertex`.

    Raises:
        ValidationError: If *node* or *id_map* is ``None`` or invalid.
        ValueError: If ``node.title`` is ``None``.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(id_map.keys()))
    if node.title is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'title'")
    return PageVertex(
        uid=node.uid,
        title=to_pandoc_md(node.title),
        children=_resolve_children(node, id_map),
        refs=_resolve_refs(node, id_map),
    )


@validate_call
def to_image_vertex(node: RoamNode, id_map: dict[Id, RoamNode]) -> ImageVertex:
    """Build an :class:`~guffin.graph.ImageVertex` from *node*.

    Args:
        node: A block node whose ``node.string`` embeds a Firestore image URL.
        id_map: Mapping from Datomic entity id to :class:`~guffin.roam_node.RoamNode`,
            used to resolve child and ref stubs to UIDs.

    Returns:
        An :class:`~guffin.graph.ImageVertex`.

    Raises:
        ValidationError: If *node* or *id_map* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None`` or contains no Firestore URL.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    firestore_url: Final[str | None] = _extract_firestore_url(node.string)
    if firestore_url is None:
        raise ValueError(f"RoamNode uid={node.uid!r} 'string' contains no Firestore URL")
    file_name: Final[str | None] = _extract_file_name(firestore_url)
    media_type: Final[MediaType | None] = MediaType.from_file_name(file_name) if file_name is not None else None
    return ImageVertex(
        uid=node.uid,
        source=_url_adapter.validate_python(firestore_url),
        alt_text=_extract_alt_text(node.string),
        file_name=file_name,
        media_type=media_type,
        children=_resolve_children(node, id_map),
        refs=_resolve_refs(node, id_map),
    )


@validate_call
def to_heading_vertex(node: RoamNode, id_map: dict[Id, RoamNode], heading_offset: int = 0) -> HeadingVertex:
    """Build a :class:`~guffin.graph.HeadingVertex` from *node*.

    Args:
        node: A block node with an effective heading level (native ``node.heading``
            or ``node.props['ah-level']``).
        id_map: Mapping from Datomic entity id to :class:`~guffin.roam_node.RoamNode`,
            used to resolve child and ref stubs to UIDs.
        heading_offset: Integer offset added to the effective heading level before
            building the vertex.  Use ``1 − min_level`` to normalize the shallowest
            heading to level 1; defaults to ``0`` (no adjustment).

    Returns:
        A :class:`~guffin.graph.HeadingVertex`.

    Raises:
        ValidationError: If *node* or *id_map* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None`` or no effective heading level is found.
    """
    logger.debug("node=%r, id_map keys=%r, heading_offset=%d", node, list(id_map.keys()), heading_offset)
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    heading: Final[HeadingLevel | None] = effective_heading_level(node)
    if heading is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no effective heading level")
    return HeadingVertex(
        uid=node.uid,
        text=to_pandoc_md(node.string),
        heading=heading + heading_offset,
        children=_resolve_children(node, id_map),
        refs=_resolve_refs(node, id_map),
    )


@validate_call
def to_text_content_vertex(node: RoamNode, id_map: dict[Id, RoamNode]) -> TextContentVertex:
    """Build a :class:`~guffin.graph.TextContentVertex` from *node*.

    Args:
        node: A plain text block node with ``node.string`` set.
        id_map: Mapping from Datomic entity id to :class:`~guffin.roam_node.RoamNode`,
            used to resolve child and ref stubs to UIDs.

    Returns:
        A :class:`~guffin.graph.TextContentVertex`.

    Raises:
        ValidationError: If *node* or *id_map* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None``.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    return TextContentVertex(
        uid=node.uid,
        text=to_pandoc_md(node.string),
        children=_resolve_children(node, id_map),
        refs=_resolve_refs(node, id_map),
    )


@validate_call
def transcribe_node(node: RoamNode, id_map: dict[Id, RoamNode], heading_offset: int = 0) -> Vertex:
    r"""Transcribe *node* into a normalized :class:`~guffin.graph.Vertex`.

    Determines the :class:`~guffin.graph.VertexType` via :func:`vertex_type`,
    resolves raw :class:`~guffin.roam_primitives.IdObject` stubs in children and refs to
    stable UIDs via *id_map*, and handles both native Roam headings (levels 1–3 via
    ``node.heading``) and Augmented Headings extension levels (4–6 via
    ``node.props['ah-level']``).

    Args:
        node: The raw Roam node to transcribe.
        id_map: Mapping from Datomic entity id to :class:`~guffin.roam_node.RoamNode`,
            used to resolve child and ref stubs to UIDs.  Stubs whose id is absent
            from *id_map* are silently dropped.
        heading_offset: Integer offset forwarded to :func:`to_heading_vertex` when *node*
            is a heading block.  Defaults to ``0`` (no adjustment).

    Returns:
        A :class:`~guffin.graph.Vertex` representing the normalized node.

    Raises:
        ValidationError: If *node* or *id_map* is ``None`` or invalid.
        ValueError: If *node* has neither a ``title`` nor a ``string`` field set.
    """
    logger.debug("node=%r, id_map keys=%r, heading_offset=%d", node, list(id_map.keys()), heading_offset)
    match vertex_type(node):
        case VertexType.GUFFIN_PAGE:
            return to_page_vertex(node, id_map)
        case VertexType.GUFFIN_IMAGE:
            return to_image_vertex(node, id_map)
        case VertexType.GUFFIN_HEADING:
            return to_heading_vertex(node, id_map, heading_offset)
        case VertexType.GUFFIN_TEXT_CONTENT:
            return to_text_content_vertex(node, id_map)


@validate_call
def transcribe(node_tree: NodeTree) -> VertexTree:
    """Transcribe every node in *node_tree* into a :class:`~guffin.graph.VertexTree`.

    Builds an id-map from *node_tree.tree_network*, then applies :func:`transcribe_node`
    to each node in insertion order.  When :data:`SHOULD_NORMALIZE_HEADING_LEVELS` is
    ``True``, computes a *heading_offset* equal to ``1 − min effective heading level``
    across all nodes in the tree, so that the shallowest heading maps to level 1; when
    no heading nodes are present, or when :data:`SHOULD_NORMALIZE_HEADING_LEVELS` is
    ``False``, *heading_offset* is 0.

    Args:
        node_tree: A validated tree of raw Roam nodes.

    Returns:
        A :class:`~guffin.graph.VertexTree` containing one
        :class:`~guffin.graph.Vertex` per node in *node_tree.tree_network*.

    Raises:
        ValueError: If any node has neither a ``title`` nor a ``string`` field set.
    """
    id_map: Final[dict[Id, RoamNode]] = {n.id: n for n in node_tree.tree_network}
    min_level: Final[HeadingLevel | None] = (
        min_effective_heading_level(node_tree.tree_network) if SHOULD_NORMALIZE_HEADING_LEVELS else None
    )
    heading_offset: Final[int] = (1 - min_level) if min_level is not None else 0
    logger.debug("heading_offset=%d", heading_offset)
    return VertexTree(vertices=[transcribe_node(n, id_map, heading_offset) for n in node_tree.tree_network])
