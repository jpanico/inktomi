"""Shared tree-loading pipeline for Roam Research CLI commands.

Public symbols:

- :func:`fetch_roam_trees` — fetch nodes for a :class:`~inktomi.roam_node_fetch_result.NodeFetchSpec`
  and return a :class:`~inktomi.roam_node_fetch_result.NodeFetchResult` paired with an optional
  :class:`~inktomi.graph.VertexTree`, ready for rendering or further processing.
"""

import logging
from typing import Final

import typer

from inktomi.graph import VertexTree
from inktomi.roam_local_api import ApiEndpoint
from inktomi.roam_node_fetch import FetchRoamNodes
from inktomi.roam_node_fetch_result import NodeFetchResult, NodeFetchSpec
from inktomi.roam_tree import NodeTree
from inktomi.roam_transcribe import transcribe

logger = logging.getLogger(__name__)


def fetch_roam_trees(
    fetch_spec: NodeFetchSpec,
    include_vertex_tree: bool,
    api_endpoint: ApiEndpoint,
) -> tuple[NodeFetchResult, VertexTree | None]:
    """Fetch Roam nodes for *fetch_spec* and build a validated node tree and vertex tree.

    Fetches :class:`~inktomi.roam_node.RoamNode` records for *fetch_spec* via
    *api_endpoint*, constructs a :class:`~inktomi.roam_tree.NodeTree`, and optionally
    transcribes it to a :class:`~inktomi.graph.VertexTree`.

    Exits the CLI with code 1 when the fetch raises an exception or when no nodes are found.

    Args:
        fetch_spec: The fetch specification carrying the anchor, include_refs flag, and
            include_node_tree flag.
        include_vertex_tree: When ``True``, transcribes the node tree to a
            :class:`~inktomi.graph.VertexTree` and returns it as the second element of
            the pair.  When ``False``, skips transcription and returns ``None`` instead.
        api_endpoint: Configured API endpoint used to fetch nodes.

    Returns:
        A ``(fetch_result, vertex_tree)`` pair ready for rendering or further processing.
        ``vertex_tree`` is ``None`` when *include_vertex_tree* is ``False``.
    """
    try:
        result: Final[NodeFetchResult] = FetchRoamNodes.fetch_roam_nodes(
            anchor=fetch_spec.anchor,
            api_endpoint=api_endpoint,
            include_refs=fetch_spec.include_refs,
            include_node_tree=fetch_spec.include_node_tree or include_vertex_tree,
        )
    except Exception:
        logger.exception("Error fetching %r", fetch_spec.anchor.qualifier)
        raise typer.Exit(code=1)

    if not include_vertex_tree:
        logger.debug("result=%r", result)
        return result, None

    assert (
        result.anchor_tree is not None
    ), "anchor_tree is None; fetch_spec has include_node_tree=False, which is unsupported here"
    anchor_tree: Final[NodeTree] = result.anchor_tree
    vertex_tree: Final[VertexTree] = transcribe(anchor_tree)
    logger.debug("node_tree=%r\n\nvertex_tree=%r", anchor_tree, vertex_tree)
    return result, vertex_tree
