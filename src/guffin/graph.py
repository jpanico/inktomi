"""Roam Research normalized graph vertex model.

A :data:`Vertex` is the normalized (transcribed) form of a single
:class:`~guffin.roam_node.RoamNode`.  A :class:`VertexTree` is the normalized
form of a :class:`~guffin.roam_tree.NodeTree`.

Normalization (transcription) means:

- Datomic-internal numeric entity ids (:attr:`~guffin.roam_node.RoamNode.id`) are
  eliminated.
- Raw :class:`~guffin.roam_primitives.IdObject` stubs in ``children`` and ``refs`` are
  resolved to stable ``:block/uid`` strings.
- The raw ``string`` / ``title`` field distinction is collapsed into a single ``text``
  field.
- Each node is classified into a :class:`VertexType`.
- The result is self-contained and portable — no Datomic dependencies remain.

Normalization is performed by :func:`~guffin.roam_transcribe.transcribe` (for a full
:class:`~guffin.roam_tree.NodeTree`) or
:func:`~guffin.roam_transcribe.transcribe_node` (for a single
:class:`~guffin.roam_node.RoamNode`).

Public symbols:

- :data:`VertexChildren` — normalized form of
  :attr:`~guffin.roam_node.RoamNode.children`: ordered child UIDs.
- :data:`VertexRefs` — normalized form of :attr:`~guffin.roam_node.RoamNode.refs`:
  referenced UIDs.
- :class:`VertexType` — string enum classifying each vertex by the shape of its source
  :class:`~guffin.roam_node.RoamNode`.
- :class:`PageVertex` — normalized (transcribed) form of a Roam Page node.
- :class:`HeadingVertex` — normalized (transcribed) form of a Roam Heading block node.
- :class:`TextContentVertex` — normalized (transcribed) form of a plain-text Roam Block
  node.
- :class:`ImageVertex` — normalized (transcribed) form of a Roam Firestore image block
  node.
- :data:`Vertex` — union of all four concrete vertex types.
- :data:`vertex_adapter` — Pydantic :class:`~pydantic.TypeAdapter` for validating a
  :data:`Vertex` from a raw dict.
- :class:`VertexTree` — normalized (transcribed) form of a
  :class:`~guffin.roam_tree.NodeTree`; a portable tree of :data:`Vertex` instances.
- :meth:`VertexTree.dfs` — return a :class:`VertexTreeDFSIterator` for pre-order
  depth-first traversal.
- :class:`VertexTreeDFSIterator` — pre-order depth-first iterator over a
  :class:`VertexTree`.
- :func:`page_vertices` — return all :class:`PageVertex` instances in a :class:`VertexTree`.
- :func:`heading_vertices` — return all :class:`HeadingVertex` instances in a :class:`VertexTree`.
- :func:`text_content_vertices` — return all :class:`TextContentVertex` instances in a :class:`VertexTree`.
- :func:`image_vertices` — return all :class:`ImageVertex` instances in a :class:`VertexTree`.
- :func:`image_urls` — return all Cloud Firestore image URLs from a :class:`VertexTree`.
- :func:`root_vertex` — return the single root :data:`Vertex` of a :class:`VertexTree`.
"""

from collections.abc import Iterator
from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, validate_call

from guffin.media_type import MediaType
from guffin.roam_primitives import HeadingLevel, Uid, Url

type VertexChildren = list[Uid]
"""Normalized form of :attr:`~guffin.roam_node.RoamNode.children`.

Raw :class:`~guffin.roam_primitives.IdObject` stubs are resolved to stable ``:block/uid``
strings and sorted by ``:block/order`` during transcription.
"""

type VertexRefs = list[Uid]
"""Normalized form of :attr:`~guffin.roam_node.RoamNode.refs`.

Raw :class:`~guffin.roam_primitives.IdObject` stubs are resolved to stable ``:block/uid``
strings during transcription.
"""


class VertexType(StrEnum):
    """Classification assigned to each vertex during transcription.

    Every :class:`~guffin.roam_node.RoamNode` is classified into exactly one
    ``VertexType`` based on the shape of its raw fields.  The values are
    string-valued so they serialize cleanly to/from JSON without extra conversion.

    Values:
        GUFFIN_PAGE: Normalized form of a Roam *Page* node — ``:node/title`` is
            present; ``:block/string`` is absent.
        GUFFIN_TEXT_CONTENT: Normalized form of a Roam *Block* node that has no
            ``heading`` property — i.e. normal body text.
        GUFFIN_HEADING: Normalized form of a Roam *Block* node that carries a
            ``heading`` property (value 1, 2, or 3).
        GUFFIN_IMAGE: Normalized form of a Roam *Block* node whose
            ``:block/string`` embeds a Cloud Firestore URL pointing to a
            Roam-managed image upload.
    """

    GUFFIN_PAGE = "guffin/page"
    GUFFIN_TEXT_CONTENT = "guffin/text-content"
    GUFFIN_HEADING = "guffin/heading"
    GUFFIN_IMAGE = "guffin/image"


class _BaseVertex[VT: VertexType](BaseModel):
    """Shared fields inherited by all four concrete vertex types.

    Not instantiated directly — use :class:`PageVertex`, :class:`HeadingVertex`,
    :class:`TextContentVertex`, or :class:`ImageVertex`.

    Type Parameters:
        VT: The :class:`VertexType` literal for the concrete subtype (e.g.
            ``Literal[VertexType.GUFFIN_PAGE]``).

    Attributes:
        vertex_type: Discriminator field identifying the concrete subtype.
            Narrowed to a :class:`~typing.Literal` in each subclass.
        uid: Nine-character stable ``:block/uid`` identifier. Required.
        children: Ordered child UIDs resolved from raw
            :class:`~guffin.roam_primitives.IdObject` stubs. ``None`` when the
            source node has no children.
        refs: Referenced UIDs resolved from raw
            :class:`~guffin.roam_primitives.IdObject` stubs. ``None`` when the
            source node has no refs.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    vertex_type: VT
    uid: Uid = Field(..., description="Nine-character stable block/page identifier.")
    children: VertexChildren | None = Field(
        default=None, description="Ordered child UIDs resolved from raw IdObject stubs."
    )
    refs: VertexRefs | None = Field(default=None, description="Referenced UIDs resolved from raw IdObject stubs.")


class PageVertex(_BaseVertex[Literal[VertexType.GUFFIN_PAGE]]):
    """Normalized (transcribed) form of a Roam Page node.

    Produced when the source :class:`~guffin.roam_node.RoamNode` has
    ``:node/title`` set (i.e. ``node.title is not None``).  The ``title`` field
    is collapsed into :attr:`text`.

    Attributes:
        vertex_type: Always :attr:`~VertexType.GUFFIN_PAGE`.
            Serialized as ``'vertex-type'``.
        title: Page title from the source node's ``title`` field.
    """

    vertex_type: Literal[VertexType.GUFFIN_PAGE] = Field(
        default=VertexType.GUFFIN_PAGE,
        serialization_alias="vertex-type",
        description="Always VertexType.GUFFIN_PAGE (serialized as 'vertex-type').",
    )
    title: str = Field(..., description="Page title from the source node's title field.")


class HeadingVertex(_BaseVertex[Literal[VertexType.GUFFIN_HEADING]]):
    """Normalized (transcribed) form of a Roam Heading block node.

    Produced when the source :class:`~guffin.roam_node.RoamNode` has an
    effective heading level — either a native ``heading`` value (1–3) or an
    Augmented Headings ``props['ah-level']`` value (h4–h6).

    Attributes:
        vertex_type: Always :attr:`~VertexType.GUFFIN_HEADING`.
            Serialized as ``'vertex-type'``.
        text: Block string from the source node's ``string`` field.
        heading: Effective heading level in the range 1–6.
    """

    vertex_type: Literal[VertexType.GUFFIN_HEADING] = Field(
        default=VertexType.GUFFIN_HEADING,
        serialization_alias="vertex-type",
        description="Always VertexType.GUFFIN_HEADING (serialized as 'vertex-type').",
    )
    text: str = Field(..., description="Block string from the source node's string field.")
    heading: HeadingLevel = Field(..., description="Effective heading level (1–6).")


class TextContentVertex(_BaseVertex[Literal[VertexType.GUFFIN_TEXT_CONTENT]]):
    """Normalized (transcribed) form of a plain-text Roam Block node.

    Produced when the source :class:`~guffin.roam_node.RoamNode` has
    ``:block/string`` set with no heading property and no embedded Firestore URL.

    Attributes:
        vertex_type: Always :attr:`~VertexType.GUFFIN_TEXT_CONTENT`.
            Serialized as ``'vertex-type'``.
        text: Block string from the source node's ``string`` field.
    """

    vertex_type: Literal[VertexType.GUFFIN_TEXT_CONTENT] = Field(
        default=VertexType.GUFFIN_TEXT_CONTENT,
        serialization_alias="vertex-type",
        description="Always VertexType.GUFFIN_TEXT_CONTENT (serialized as 'vertex-type').",
    )
    text: str = Field(..., description="Block string from the source node's string field.")


class ImageVertex(_BaseVertex[Literal[VertexType.GUFFIN_IMAGE]]):
    """Normalized (transcribed) form of a Roam Cloud Firestore image block node.

    Produced when the source :class:`~guffin.roam_node.RoamNode` has a
    ``:block/string`` that embeds a Cloud Firestore storage URL.

    Attributes:
        vertex_type: Always :attr:`~VertexType.GUFFIN_IMAGE`.
            Serialized as ``'vertex-type'``.
        source: Cloud Firestore storage URL for the image file.
        alt_text: Alt text extracted from the Markdown image link
            (``![<alt_text>](<url>)``), stripped of leading/trailing whitespace.
            ``None`` when the alt text is absent or empty.
            Serialized as ``'alt-text'``.
        file_name: Original filename decoded from *source*. ``None`` if the
            filename cannot be extracted.
        media_type: IANA media type inferred from *file_name*'s extension.
            ``None`` if the type cannot be determined.
            Serialized as ``'media-type'``.
    """

    vertex_type: Literal[VertexType.GUFFIN_IMAGE] = Field(
        default=VertexType.GUFFIN_IMAGE,
        serialization_alias="vertex-type",
        description="Always VertexType.GUFFIN_IMAGE (serialized as 'vertex-type').",
    )
    source: Url = Field(..., description="Cloud Firestore storage URL for the image file.")
    alt_text: str | None = Field(
        default=None,
        serialization_alias="alt-text",
        description="Alt text from the Markdown image link, stripped. None when absent or empty.",
    )
    file_name: str | None = Field(default=None, description="Original filename decoded from source.")
    media_type: MediaType | None = Field(
        default=None,
        serialization_alias="media-type",
        description="IANA media type inferred from file_name's extension (serialized as 'media-type').",
    )


type Vertex = PageVertex | HeadingVertex | TextContentVertex | ImageVertex
"""Union of all four concrete, normalized vertex types.

Use :data:`vertex_adapter` to validate a raw dict into the appropriate concrete
subtype.  Use :class:`VertexTree` to hold a validated collection of vertices.
"""

type _AnnotatedVertex = Annotated[Vertex, Field(discriminator="vertex_type")]
"""Internal alias: :data:`Vertex` union with ``vertex_type`` discriminator attached.

Shared by :data:`vertex_adapter` and :class:`VertexTree` to avoid repeating the
full union + discriminator annotation in both places.
"""

vertex_adapter: TypeAdapter[Vertex] = TypeAdapter(_AnnotatedVertex)
"""Pydantic :class:`~pydantic.TypeAdapter` for validating a raw dict into the correct :data:`Vertex` subtype.

Uses ``vertex_type`` as the discriminator field to select among :class:`PageVertex`,
:class:`HeadingVertex`, :class:`TextContentVertex`, and :class:`ImageVertex`.

Example::

    v = vertex_adapter.validate_python({"vertex_type": "guffin/page", "uid": "abc", "text": "My Page"})
    assert isinstance(v, PageVertex)
"""


class VertexTree(BaseModel):
    """Normalized (transcribed) form of a :class:`~guffin.roam_tree.NodeTree`.

    Produced by :func:`~guffin.roam_transcribe.transcribe`, which applies
    :func:`~guffin.roam_transcribe.transcribe_node` to every node in the source
    :class:`~guffin.roam_tree.NodeTree` and collects the results here in the
    same insertion order.  The resulting collection is guaranteed to have exactly
    one :data:`Vertex` per source :class:`~guffin.roam_node.RoamNode` and
    inherits the acyclic-tree structure of its origin.

    Attributes:
        vertices: Transcribed vertices, one per source
            :class:`~guffin.roam_node.RoamNode`, in insertion order.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    vertices: list[_AnnotatedVertex] = Field(..., description="Transcribed vertices, one per source RoamNode.")

    def dfs(self) -> VertexTreeDFSIterator:
        """Return a pre-order depth-first iterator over this tree.

        Returns:
            A :class:`VertexTreeDFSIterator` seeded at the root of this tree.
        """
        return VertexTreeDFSIterator(self)


class VertexTreeDFSIterator(Iterator[Vertex]):
    """Pre-order depth-first iterator over a :class:`VertexTree`.

    Yields vertices starting from the single root, then recursively yields each
    child subtree in the order recorded in each vertex's
    :attr:`~_BaseVertex.children` list (which preserves the original
    :attr:`~guffin.roam_node.RoamNode.order` sort applied during transcription).
    The traversal is non-recursive internally (stack-based), so deep trees do not
    risk hitting Python's recursion limit.

    Usage::

        for vertex in VertexTreeDFSIterator(tree):
            ...

    Attributes:
        _uid_map: Mapping from :attr:`~_BaseVertex.uid` to :data:`Vertex`,
            built once at construction time.
        _stack: LIFO stack of vertices yet to be visited; initialized with the
            root vertex.
    """

    def __init__(self, tree: VertexTree) -> None:
        """Initialize the iterator from *tree*.

        Builds a uid-map over *tree.vertices* and seeds the stack with the
        single root vertex — the one whose uid does not appear in any other
        vertex's :attr:`~_BaseVertex.children` list.

        Args:
            tree: The :class:`VertexTree` to traverse.
        """
        self._uid_map: dict[Uid, Vertex] = {v.uid: v for v in tree.vertices}
        self._stack: list[Vertex] = [root_vertex(tree)]

    def __iter__(self) -> Iterator[Vertex]:
        """Return *self* (this object is its own iterator)."""
        return self

    def __next__(self) -> Vertex:
        """Return the next vertex in pre-order depth-first traversal.

        Raises:
            StopIteration: When all vertices have been yielded.
        """
        if not self._stack:
            raise StopIteration
        vertex: Vertex = self._stack.pop()
        if vertex.children:
            children: list[Vertex] = [self._uid_map[uid] for uid in vertex.children if uid in self._uid_map]
            self._stack.extend(reversed(children))
        return vertex


@validate_call
def page_vertices(tree: VertexTree) -> list[PageVertex]:
    """Return all :class:`PageVertex` instances in *tree*, in insertion order."""
    return [v for v in tree.vertices if isinstance(v, PageVertex)]


@validate_call
def heading_vertices(tree: VertexTree) -> list[HeadingVertex]:
    """Return all :class:`HeadingVertex` instances in *tree*, in insertion order."""
    return [v for v in tree.vertices if isinstance(v, HeadingVertex)]


@validate_call
def text_content_vertices(tree: VertexTree) -> list[TextContentVertex]:
    """Return all :class:`TextContentVertex` instances in *tree*, in insertion order."""
    return [v for v in tree.vertices if isinstance(v, TextContentVertex)]


@validate_call
def image_vertices(tree: VertexTree) -> list[ImageVertex]:
    """Return all :class:`ImageVertex` instances in *tree*, in insertion order."""
    return [v for v in tree.vertices if isinstance(v, ImageVertex)]


@validate_call
def image_urls(tree: VertexTree) -> list[Url]:
    """Return the Cloud Firestore URL of every :class:`ImageVertex` in *tree*, in insertion order."""
    return [v.source for v in image_vertices(tree)]


@validate_call
def root_vertex(tree: VertexTree) -> Vertex:
    """Return the single root :data:`Vertex` of *tree*.

    The root is the unique vertex whose :attr:`~_BaseVertex.uid` does not
    appear in any other vertex's :attr:`~_BaseVertex.children` list.

    Args:
        tree: The :class:`VertexTree` to inspect.

    Returns:
        The root :data:`Vertex`.
    """
    child_uids: Final[set[Uid]] = {uid for v in tree.vertices if v.children for uid in v.children}
    return next(v for v in tree.vertices if v.uid not in child_uids)
