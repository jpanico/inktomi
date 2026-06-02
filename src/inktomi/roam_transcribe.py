"""Roam Research node transcription to normalized graph vertices.

Public symbols:

- :func:`is_image_node` — return ``True`` when a node's string is exactly one
  Markdown image link and nothing else.
- :func:`vertex_type` — classify a :class:`~inktomi.roam_node.RoamNode` into a
  :class:`~inktomi.graph.VertexType`.
- :func:`to_page_vertex` — build a :class:`~inktomi.graph.PageVertex` from a
  page node.
- :func:`to_image_vertex` — build an :class:`~inktomi.graph.ImageVertex` from a
  Firestore image block node.
- :func:`to_heading_vertex` — build a :class:`~inktomi.graph.HeadingVertex` from
  a heading block node.
- :func:`to_text_content_vertex` — build a
  :class:`~inktomi.graph.TextContentVertex` from a plain text block node.
- :func:`transcribe_node` — transcribe a :class:`~inktomi.roam_node.RoamNode` into
  the appropriate :data:`~inktomi.graph.Vertex` subtype.
- :func:`transcribe` — transcribe all nodes in a :class:`~inktomi.roam_tree.NodeTree`
  into a :class:`~inktomi.graph.VertexTree`.
"""

import logging
import mimetypes
import re
from typing import Final
from urllib.parse import unquote, urlparse

from pydantic import TypeAdapter, validate_call

from inktomi.graph import (
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
from inktomi.roam_md_normalize import normalize
from inktomi.roam_node import RoamNode
from inktomi.roam_tree import NodeTree
from inktomi.roam_primitives import IMAGE_LINK_RE, HeadingLevel, Id, Url

logger = logging.getLogger(__name__)

_url_adapter: TypeAdapter[Url] = TypeAdapter(Url)
"""Pydantic :class:`~pydantic.TypeAdapter` for validating and coercing URL strings to.

:data:`~inktomi.roam_primitives.Url`.
"""


def _resolve_children(node: RoamNode, id_map: dict[Id, RoamNode]) -> VertexChildren | None:
    """Return an ordered list of child UIDs for *node*, or ``None`` if childless.

    Children are sorted by :attr:`~inktomi.roam_node.RoamNode.order`.  Stubs
    whose id is absent from *id_map* are silently dropped.

    Args:
        node: The node whose children are to be resolved.
        id_map: Mapping from Datomic entity id to :class:`~inktomi.roam_node.RoamNode`.

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
        id_map: Mapping from Datomic entity id to :class:`~inktomi.roam_node.RoamNode`.

    Returns:
        List of referenced UIDs, or ``None`` when *node* has no refs or all ref
        stubs are unresolvable.
    """
    if not node.refs:
        return None
    resolved: Final[VertexRefs] = [id_map[r.id].uid for r in node.refs if r.id in id_map]
    return resolved if resolved else None


def _effective_heading_level(node: RoamNode) -> HeadingLevel | None:
    """Return the effective heading level for *node*, or ``None`` if it is not a heading.

    Checks native heading first (``node.heading``, levels 1–3), then falls back
    to the Augmented Headings extension (``node.props['ah-level']``, levels 4–6).

    Args:
        node: The node to inspect.

    Returns:
        An integer heading level in the range 1–6, or ``None``.
    """
    if node.heading is not None:
        return node.heading
    if node.props is not None:
        ah_level = node.props.get("ah-level")
        if isinstance(ah_level, str) and len(ah_level) == 2 and ah_level[0] == "h":
            try:
                level = int(ah_level[1])
                if 1 <= level <= 6:
                    return level
            except ValueError:
                pass
    return None


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


def _infer_media_type(file_name: str) -> str | None:
    """Return the IANA media type inferred from *file_name*'s extension, or ``None``.

    Uses :func:`mimetypes.guess_type` from the standard library.

    Args:
        file_name: A filename string including extension (e.g. ``"photo.jpg"``).

    Returns:
        A media type string such as ``"image/jpeg"``, or ``None`` when the type
        cannot be determined.
    """
    guessed, _ = mimetypes.guess_type(file_name)
    return guessed


@validate_call
def is_image_node(node: RoamNode) -> bool:
    """Return ``True`` if *node* contains exactly one Markdown image link and nothing else.

    Checks that ``node.string``, after stripping leading and trailing whitespace,
    consists entirely of a single ``![<alt>](<url>)`` link.  Any surrounding text,
    additional links, or a ``None`` string all return ``False``.

    Args:
        node: The node to inspect.

    Returns:
        ``True`` if ``node.string`` is solely a single Markdown image link.

    Raises:
        ValidationError: If *node* is ``None`` or invalid.
    """
    if node.string is None:
        return False
    return bool(IMAGE_LINK_RE.fullmatch(node.string.strip()))


@validate_call
def vertex_type(node: RoamNode) -> VertexType:
    r"""Classify *node* into a :class:`~inktomi.graph.VertexType`.

    Handles both native Roam headings (levels 1–3 via ``node.heading``) and Augmented
    Headings extension levels (4–6 via ``node.props['ah-level']``).

    Classification order:

    1. ``node.title`` is set → :attr:`~inktomi.graph.VertexType.ROAM_PAGE`
    2. ``node.string`` contains a Firestore URL → :attr:`~inktomi.graph.VertexType.ROAM_IMAGE`
    3. Effective heading level is non-\ ``None`` → :attr:`~inktomi.graph.VertexType.ROAM_HEADING`
    4. Otherwise → :attr:`~inktomi.graph.VertexType.ROAM_TEXT_CONTENT`

    Args:
        node: The raw Roam node to classify.

    Returns:
        The :class:`~inktomi.graph.VertexType` for *node*.

    Raises:
        ValidationError: If *node* is ``None`` or invalid.
        ValueError: If *node* has neither a ``title`` nor a ``string`` field set.
    """
    logger.debug("node=%r", node)
    if node.title is not None:
        return VertexType.ROAM_PAGE
    string: Final[str | None] = node.string
    if string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has neither 'title' nor 'string'")
    if is_image_node(node):
        return VertexType.ROAM_IMAGE
    if _effective_heading_level(node) is not None:
        return VertexType.ROAM_HEADING
    return VertexType.ROAM_TEXT_CONTENT


@validate_call
def to_page_vertex(node: RoamNode, id_map: dict[Id, RoamNode]) -> PageVertex:
    """Build a :class:`~inktomi.graph.PageVertex` from *node*.

    Args:
        node: A page node with ``node.title`` set.
        id_map: Mapping from Datomic entity id to :class:`~inktomi.roam_node.RoamNode`,
            used to resolve child and ref stubs to UIDs.

    Returns:
        A :class:`~inktomi.graph.PageVertex`.

    Raises:
        ValidationError: If *node* or *id_map* is ``None`` or invalid.
        ValueError: If ``node.title`` is ``None``.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(id_map.keys()))
    if node.title is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'title'")
    return PageVertex(
        uid=node.uid,
        title=normalize(node.title),
        children=_resolve_children(node, id_map),
        refs=_resolve_refs(node, id_map),
    )


@validate_call
def to_image_vertex(node: RoamNode, id_map: dict[Id, RoamNode]) -> ImageVertex:
    """Build an :class:`~inktomi.graph.ImageVertex` from *node*.

    Args:
        node: A block node whose ``node.string`` embeds a Firestore image URL.
        id_map: Mapping from Datomic entity id to :class:`~inktomi.roam_node.RoamNode`,
            used to resolve child and ref stubs to UIDs.

    Returns:
        An :class:`~inktomi.graph.ImageVertex`.

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
    media_type: Final[str | None] = _infer_media_type(file_name) if file_name is not None else None
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
def to_heading_vertex(node: RoamNode, id_map: dict[Id, RoamNode]) -> HeadingVertex:
    """Build a :class:`~inktomi.graph.HeadingVertex` from *node*.

    Args:
        node: A block node with an effective heading level (native ``node.heading``
            or ``node.props['ah-level']``).
        id_map: Mapping from Datomic entity id to :class:`~inktomi.roam_node.RoamNode`,
            used to resolve child and ref stubs to UIDs.

    Returns:
        A :class:`~inktomi.graph.HeadingVertex`.

    Raises:
        ValidationError: If *node* or *id_map* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None`` or no effective heading level is found.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    heading: Final[HeadingLevel | None] = _effective_heading_level(node)
    if heading is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no effective heading level")
    return HeadingVertex(
        uid=node.uid,
        text=normalize(node.string),
        heading=heading,
        children=_resolve_children(node, id_map),
        refs=_resolve_refs(node, id_map),
    )


@validate_call
def to_text_content_vertex(node: RoamNode, id_map: dict[Id, RoamNode]) -> TextContentVertex:
    """Build a :class:`~inktomi.graph.TextContentVertex` from *node*.

    Args:
        node: A plain text block node with ``node.string`` set.
        id_map: Mapping from Datomic entity id to :class:`~inktomi.roam_node.RoamNode`,
            used to resolve child and ref stubs to UIDs.

    Returns:
        A :class:`~inktomi.graph.TextContentVertex`.

    Raises:
        ValidationError: If *node* or *id_map* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None``.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    return TextContentVertex(
        uid=node.uid,
        text=normalize(node.string),
        children=_resolve_children(node, id_map),
        refs=_resolve_refs(node, id_map),
    )


@validate_call
def transcribe_node(node: RoamNode, id_map: dict[Id, RoamNode]) -> Vertex:
    r"""Transcribe *node* into a normalized :class:`~inktomi.graph.Vertex`.

    Determines the :class:`~inktomi.graph.VertexType` via :func:`vertex_type`,
    resolves raw :class:`~inktomi.roam_primitives.IdObject` stubs in children and refs to
    stable UIDs via *id_map*, and handles both native Roam headings (levels 1–3 via
    ``node.heading``) and Augmented Headings extension levels (4–6 via
    ``node.props['ah-level']``).

    Args:
        node: The raw Roam node to transcribe.
        id_map: Mapping from Datomic entity id to :class:`~inktomi.roam_node.RoamNode`,
            used to resolve child and ref stubs to UIDs.  Stubs whose id is absent
            from *id_map* are silently dropped.

    Returns:
        A :class:`~inktomi.graph.Vertex` representing the normalized node.

    Raises:
        ValidationError: If *node* or *id_map* is ``None`` or invalid.
        ValueError: If *node* has neither a ``title`` nor a ``string`` field set.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(id_map.keys()))
    match vertex_type(node):
        case VertexType.ROAM_PAGE:
            return to_page_vertex(node, id_map)
        case VertexType.ROAM_IMAGE:
            return to_image_vertex(node, id_map)
        case VertexType.ROAM_HEADING:
            return to_heading_vertex(node, id_map)
        case VertexType.ROAM_TEXT_CONTENT:
            return to_text_content_vertex(node, id_map)


def transcribe(node_tree: NodeTree) -> VertexTree:
    """Transcribe every node in *node_tree* into a :class:`~inktomi.graph.VertexTree`.

    Builds an id-map from *node_tree.tree_network*, then applies :func:`transcribe_node`
    to each node in insertion order.

    Args:
        node_tree: A validated tree of raw Roam nodes.

    Returns:
        A :class:`~inktomi.graph.VertexTree` containing one
        :class:`~inktomi.graph.Vertex` per node in *node_tree.tree_network*.

    Raises:
        ValueError: If any node has neither a ``title`` nor a ``string`` field set.
    """
    id_map: Final[dict[Id, RoamNode]] = {n.id: n for n in node_tree.tree_network}
    return VertexTree(vertices=[transcribe_node(n, id_map) for n in node_tree.tree_network])
