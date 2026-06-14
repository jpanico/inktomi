"""VertexTree — normalized (transcribed) form of a NodeTree; traversal and filter helpers.

Public symbols:

- :class:`VertexTree` — normalized (transcribed) form of a
  :class:`~guffin.roam.tree.NodeTree`; a portable tree of :data:`~guffin.vertex.Vertex` instances.
- :meth:`VertexTree.dfs` — return a :class:`VertexTreeDFSIterator` for pre-order
  depth-first traversal.
- :class:`VertexTreeDFSIterator` — pre-order depth-first iterator over a
  :class:`VertexTree`.
- :func:`page_vertices` — return all :class:`~guffin.vertex.PageVertex` instances in a :class:`VertexTree`.
- :func:`heading_vertices` — return all :class:`~guffin.vertex.HeadingVertex` instances in a :class:`VertexTree`.
- :func:`text_content_vertices` — return all :class:`~guffin.vertex.TextContentVertex` instances in a
  :class:`VertexTree`.
- :func:`image_vertices` — return all :class:`~guffin.vertex.ImageVertex` instances in a :class:`VertexTree`.
- :func:`image_urls` — return all Cloud Firestore image URLs from a :class:`VertexTree`.
- :func:`root_vertex` — return the single root :data:`~guffin.vertex.Vertex` of a :class:`VertexTree`.
- :func:`map_vertices` — return a new :class:`VertexTree` with a mapping function applied to every vertex.
- :func:`enrich_image_original_sizes` — return a new :class:`VertexTree` with
  :attr:`~guffin.vertex.ImageVertex.original_image_size` populated from a UID→ImageSize map.
"""

import logging
from collections.abc import Callable, Iterator
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, validate_call

from guffin.common.geometry import ImageSize

logger = logging.getLogger(__name__)
from guffin.roam.primitives import Uid, Url
from guffin.vertex import (
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TextContentVertex,
    Vertex,
)


class VertexTree(BaseModel):
    """Normalized (transcribed) form of a :class:`~guffin.roam.tree.NodeTree`.

    Produced by :func:`~guffin.roam_tree_to_vertex_tree.transcribe`, which applies
    :func:`~guffin.roam_tree_to_vertex_tree.transcribe_standalone_node` to every node in the source
    :class:`~guffin.roam.tree.NodeTree` and collects the results here in the
    same insertion order.  The resulting collection is guaranteed to have exactly
    one :data:`~guffin.vertex.Vertex` per source :class:`~guffin.roam.node.RoamNode` and
    inherits the acyclic-tree structure of its origin.

    Attributes:
        vertices: Transcribed vertices, one per source
            :class:`~guffin.roam.node.RoamNode`, in insertion order.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    vertices: list[Annotated[Vertex, Field(discriminator="vertex_type")]] = Field(
        ..., description="Transcribed vertices, one per source RoamNode."
    )

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
    :attr:`~guffin.vertex._BaseVertex.children` list (which preserves the original
    :attr:`~guffin.roam.node.RoamNode.order` sort applied during transcription).
    The traversal is non-recursive internally (stack-based), so deep trees do not
    risk hitting Python's recursion limit.

    Usage::

        for vertex in VertexTreeDFSIterator(tree):
            ...

    Attributes:
        _uid_map: Mapping from :attr:`~guffin.vertex._BaseVertex.uid` to
            :data:`~guffin.vertex.Vertex`, built once at construction time.
        _stack: LIFO stack of vertices yet to be visited; initialized with the
            root vertex.
    """

    def __init__(self, tree: VertexTree) -> None:
        """Initialize the iterator from *tree*.

        Builds a uid-map over *tree.vertices* and seeds the stack with the
        single root vertex — the one whose uid does not appear in any other
        vertex's :attr:`~guffin.vertex._BaseVertex.children` list.

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
    """Return all :class:`~guffin.vertex.PageVertex` instances in *tree*, in insertion order."""
    return [v for v in tree.vertices if isinstance(v, PageVertex)]


@validate_call
def heading_vertices(tree: VertexTree) -> list[HeadingVertex]:
    """Return all :class:`~guffin.vertex.HeadingVertex` instances in *tree*, in insertion order."""
    return [v for v in tree.vertices if isinstance(v, HeadingVertex)]


@validate_call
def text_content_vertices(tree: VertexTree) -> list[TextContentVertex]:
    """Return all :class:`~guffin.vertex.TextContentVertex` instances in *tree*, in insertion order."""
    return [v for v in tree.vertices if isinstance(v, TextContentVertex)]


@validate_call
def image_vertices(tree: VertexTree) -> list[ImageVertex]:
    """Return all :class:`~guffin.vertex.ImageVertex` instances in *tree*, in insertion order."""
    return [v for v in tree.vertices if isinstance(v, ImageVertex)]


@validate_call
def image_urls(tree: VertexTree) -> list[Url]:
    """Return the Cloud Firestore URL of every :class:`~guffin.vertex.ImageVertex` in *tree*, in insertion order."""
    return [v.source for v in image_vertices(tree)]


@validate_call
def root_vertex(tree: VertexTree) -> Vertex:
    """Return the single root :data:`~guffin.vertex.Vertex` of *tree*.

    The root is the unique vertex whose :attr:`~guffin.vertex._BaseVertex.uid` does not
    appear in any other vertex's :attr:`~guffin.vertex._BaseVertex.children` list.

    Args:
        tree: The :class:`VertexTree` to inspect.

    Returns:
        The root :data:`~guffin.vertex.Vertex`.
    """
    child_uids: Final[set[Uid]] = {uid for v in tree.vertices if v.children for uid in v.children}
    return next(v for v in tree.vertices if v.uid not in child_uids)


@validate_call
def map_vertices(tree: VertexTree, func: Callable[[Vertex], Vertex]) -> VertexTree:
    """Return a new :class:`VertexTree` with *func* applied to every vertex.

    The original *tree* is not modified; immutability is preserved via
    :meth:`~pydantic.BaseModel.model_copy`.

    Args:
        tree: The source :class:`VertexTree`.
        func: A callable that maps each :data:`~guffin.vertex.Vertex` to a
            (possibly new) :data:`~guffin.vertex.Vertex`.

    Returns:
        A new :class:`VertexTree` whose vertices are ``[func(v) for v in tree.vertices]``.
    """
    return tree.model_copy(update={"vertices": [func(vtx) for vtx in tree.vertices]})


@validate_call
def enrich_image_original_sizes(tree: VertexTree, sizes: dict[Uid, ImageSize]) -> VertexTree:
    """Return a new :class:`VertexTree` with :attr:`~guffin.vertex.ImageVertex.original_image_size` populated.

    Each :class:`~guffin.vertex.ImageVertex` whose UID appears in *sizes* receives a
    copy with :attr:`~guffin.vertex.ImageVertex.original_image_size` set to the
    corresponding :class:`~guffin.common.geometry.ImageSize`.  All other vertices pass
    through unchanged.

    Args:
        tree: The source :class:`VertexTree`.
        sizes: Mapping from :class:`~guffin.vertex.ImageVertex` UID to its native pixel dimensions.

    Returns:
        A new :class:`VertexTree` with :attr:`~guffin.vertex.ImageVertex.original_image_size`
        populated for all UIDs present in *sizes*.
    """

    def _enrich(vtx: Vertex) -> Vertex:
        if isinstance(vtx, ImageVertex):
            if vtx.uid in sizes:
                return vtx.model_copy(update={"original_image_size": sizes[vtx.uid]})
            logger.warning("ImageVertex uid=%r absent from sizes map; original_image_size left unset", vtx.uid)
        return vtx

    return map_vertices(tree, _enrich)
