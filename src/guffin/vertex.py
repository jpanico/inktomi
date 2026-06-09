"""Roam Research normalized graph vertex types.

A :data:`Vertex` is the normalized (transcribed) form of a single
:class:`~guffin.roam.node.RoamNode`.

Normalization (transcription) means:

- Datomic-internal numeric entity ids (:attr:`~guffin.roam.node.RoamNode.id`) are
  eliminated.
- Raw :class:`~guffin.roam.primitives.IdObject` stubs in ``children`` and ``refs`` are
  resolved to stable ``:block/uid`` strings.
- The raw ``string`` / ``title`` field distinction is collapsed into a single ``text``
  field.
- Each node is classified into a :class:`VertexType`.
- The result is self-contained and portable — no Datomic dependencies remain.

Normalization is performed by :func:`~guffin.roam_tree_to_vertex_tree.transcribe` (for a full
:class:`~guffin.roam.tree.NodeTree`) or
:func:`~guffin.roam_tree_to_vertex_tree.transcribe_node` (for a single
:class:`~guffin.roam.node.RoamNode`).

Public symbols:

- :data:`VertexChildren` — normalized form of
  :attr:`~guffin.roam.node.RoamNode.children`: ordered child UIDs.
- :data:`VertexRefs` — normalized form of :attr:`~guffin.roam.node.RoamNode.refs`:
  referenced UIDs.
- :class:`VertexType` — string enum classifying each vertex by the shape of its source
  :class:`~guffin.roam.node.RoamNode`.
- :class:`PageVertex` — normalized (transcribed) form of a Roam Page node.
- :class:`HeadingVertex` — normalized (transcribed) form of a Roam Heading block node.
- :class:`TextContentVertex` — normalized (transcribed) form of a plain-text Roam Block
  node.
- :class:`ImageVertex` — normalized (transcribed) form of a Roam Firestore image block
  node.
- :data:`Vertex` — union of all four concrete vertex types.
- :data:`vertex_adapter` — Pydantic :class:`~pydantic.TypeAdapter` for validating a
  :data:`Vertex` from a raw dict.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from guffin.common.media_type import MediaType
from guffin.roam.primitives import HeadingLevel, Uid, Url

type VertexChildren = list[Uid]
"""Normalized form of :attr:`~guffin.roam.node.RoamNode.children`.

Raw :class:`~guffin.roam.primitives.IdObject` stubs are resolved to stable ``:block/uid``
strings and sorted by ``:block/order`` during transcription.
"""

type VertexRefs = list[Uid]
"""Normalized form of :attr:`~guffin.roam.node.RoamNode.refs`.

Raw :class:`~guffin.roam.primitives.IdObject` stubs are resolved to stable ``:block/uid``
strings during transcription.
"""


class VertexType(StrEnum):
    """Classification assigned to each vertex during transcription.

    Every :class:`~guffin.roam.node.RoamNode` is classified into exactly one
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
            :class:`~guffin.roam.primitives.IdObject` stubs. ``None`` when the
            source node has no children.
        refs: Referenced UIDs resolved from raw
            :class:`~guffin.roam.primitives.IdObject` stubs. ``None`` when the
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

    Produced when the source :class:`~guffin.roam.node.RoamNode` has
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

    Produced when the source :class:`~guffin.roam.node.RoamNode` has an
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

    Produced when the source :class:`~guffin.roam.node.RoamNode` has
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

    Produced when the source :class:`~guffin.roam.node.RoamNode` has a
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
subtype.  Use :class:`~guffin.vertex_tree.VertexTree` to hold a validated collection of vertices.
"""

vertex_adapter: TypeAdapter[Vertex] = TypeAdapter(Annotated[Vertex, Field(discriminator="vertex_type")])
"""Pydantic :class:`~pydantic.TypeAdapter` for validating a raw dict into the correct :data:`Vertex` subtype.

Uses ``vertex_type`` as the discriminator field to select among :class:`PageVertex`,
:class:`HeadingVertex`, :class:`TextContentVertex`, and :class:`ImageVertex`.

Example::

    v = vertex_adapter.validate_python({"vertex_type": "guffin/page", "uid": "abc", "text": "My Page"})
    assert isinstance(v, PageVertex)
"""
