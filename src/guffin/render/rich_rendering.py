"""Rich terminal-rendering utilities for Roam node trees, vertex trees, and raw Datalog result tables.

Public symbols:

- :data:`DEFAULT_NODE_PANEL_PROPS` — the property names rendered in a panel body by default.
- :func:`make_node_panel` — render a :class:`~guffin.roam.node.RoamNode` as a Rich
  :class:`~rich.panel.Panel`.
- :func:`build_rich_node_tree` — build a Rich :class:`~rich.tree.Tree` from a
  :class:`~guffin.roam.tree.NodeTree` using a depth-first traversal.
- :func:`build_rich_refs_box` — build a Rich :class:`~rich.panel.Panel` summarising the
  back-reference nodes in a :class:`~guffin.roam.tree.NodeTree`.
- :func:`make_vertex_panel` — render a :data:`~guffin.vertex.Vertex` as a Rich
  :class:`~rich.panel.Panel`.
- :func:`build_rich_vertex_tree` — build a Rich :class:`~rich.tree.Tree` from a
  :class:`~guffin.vertex_tree.VertexTree` using a depth-first traversal.
- :func:`build_rich_raw_table` — build a Rich :class:`~rich.table.Table` of raw
  Datalog pull-blocks from a :class:`~guffin.roam.node_fetch_result.NodeFetchResult`.
"""

import logging
import re
from typing import Final, TypeGuard

from pydantic import validate_call

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree as RichTree

from guffin.vertex import (
    HeadingVertex,
    PageVertex,
    TextContentVertex,
    Vertex,
)
from guffin.vertex_tree import VertexTree, VertexTreeDFSIterator
from guffin.roam.node import RoamNode
from guffin.roam.node_fetch_result import NodeFetchResult
from guffin.roam.tree import NodeTree, NodeTreeDFSIterator
from guffin.roam.primitives import Id, IdObject, IMAGE_LINK_RE, Uid

logger = logging.getLogger(__name__)

DEFAULT_NODE_PANEL_PROPS: Final[list[str]] = ["heading", "order", "children", "parents", "page"]
"""Property names rendered in the panel body by :func:`make_node_panel` when no explicit list is given.

``string``/``title`` and ``id`` are always shown in the panel title and are not
included here.  All other :class:`~guffin.roam.node.RoamNode` field names are
valid entries.
"""


def _format_node_prop(node: RoamNode, prop: str) -> str:
    """Return a ``name=value`` string for *prop* on *node*, for use in a panel body.

    Args:
        node: The node whose property is to be formatted.
        prop: A :class:`~guffin.roam.node.RoamNode` field name.

    Returns:
        A ``"name=value"`` string.  Unknown *prop* names produce ``"name=?"``.
    """
    match prop:
        case "order":
            return f"order={node.order}"
        case "children":
            val = f"[{', '.join(str(c.id) for c in node.children)}]" if node.children else "None"
            return f"children={val}"
        case "parents":
            val = f"[{', '.join(str(p.id) for p in node.parents)}]" if node.parents else "None"
            return f"parents={val}"
        case "page":
            val = str(node.page.id) if node.page is not None else "None"
            return f"page={val}"
        case "time":
            return f"time={node.time}"
        case "user":
            return f"user={node.user.id}"
        case "refs":
            val = f"[{', '.join(str(r.id) for r in node.refs)}]" if node.refs else "None"
            return f"refs={val}"
        case "open":
            return f"open={node.open}"
        case "sidebar":
            return f"sidebar={node.sidebar}"
        case "heading":
            return f"heading={node.heading}"
        case "attrs":
            return f"attrs={node.attrs}"
        case "props":
            return f"props={node.props}"
        case "lookup":
            val = f"[{', '.join(str(lk.id) for lk in node.lookup)}]" if node.lookup else "None"
            return f"lookup={val}"
        case "seen_by":
            val = f"[{', '.join(str(s.id) for s in node.seen_by)}]" if node.seen_by else "None"
            return f"seen_by={val}"
        case "uid":
            return f"uid={node.uid}"
        case "id":
            return f"id={node.id}"
        case "string":
            return f"string={node.string}"
        case "title":
            return f"title={node.title}"
        case _:
            return f"{prop}=?"


@validate_call
def make_node_panel(node: RoamNode, props: list[str] = DEFAULT_NODE_PANEL_PROPS) -> Panel:
    """Render *node* as a Rich Panel for display in a terminal tree.

    The panel title always shows the block string or page title with the node
    ``id`` in parentheses.  The title text is determined as follows:

    - If the block string contains a Cloud Firestore image link matching
      :data:`~guffin.roam.primitives.IMAGE_LINK_RE`, the title reads
      ``IMAGE [<alt>](FIRESTORE_URL)``.
    - Otherwise, if ``"heading"`` is in *props* and the node has a heading level,
      an ``H{n}:`` prefix is prepended.
    - Otherwise the raw block string or page title is used as-is.

    The panel body shows the remaining properties named in *props* as a single
    formatted line of ``name=value`` pairs; ``heading`` is excluded from the body
    because it is represented by the title prefix.

    Args:
        node: The node to render.
        props: Ordered list of :class:`~guffin.roam.node.RoamNode` field names
            to include.  Controls both the ``H{n}:`` title prefix (shown only when
            ``"heading"`` is present) and the body pairs (``heading`` itself is
            never written to the body).  Defaults to :data:`DEFAULT_NODE_PANEL_PROPS`.

    Returns:
        A :class:`~rich.panel.Panel` with a labelled title and metadata body.
    """
    logger.debug("node=%r, props=%r", node, props)
    text: Final[str] = node.string or node.title or f"(uid={node.uid})"
    if node.string is not None and (m := IMAGE_LINK_RE.search(node.string)):
        title: str = f"[bold #00aa00]IMAGE [{m.group('alt')}](<firestore_url>) ({node.id})[/bold #00aa00]"
    elif node.heading is not None and "heading" in props:
        title = f"[bold #00aa00]H{node.heading}: {text} ({node.id})[/bold #00aa00]"
    else:
        title = f"[bold #00aa00]{text} ({node.id})[/bold #00aa00]"
    content: Final[str] = "  ".join(_format_node_prop(node, p) for p in props if p != "heading")
    return Panel(Text(content), title=title, expand=False)


@validate_call
def build_rich_node_tree(tree: NodeTree, props: list[str] = DEFAULT_NODE_PANEL_PROPS) -> RichTree:
    """Build a Rich tree from *tree* using a depth-first traversal.

    Iterates *tree* in pre-order depth-first order via
    :meth:`~guffin.roam.tree.NodeTree.dfs`, attaching each node as a Rich
    panel under its parent in the rendered tree.

    Args:
        tree: The :class:`~guffin.roam.tree.NodeTree` to render.
        props: Ordered list of :class:`~guffin.roam.node.RoamNode` field names
            to include in each panel body.  Defaults to :data:`DEFAULT_NODE_PANEL_PROPS`.

    Returns:
        A :class:`~rich.tree.Tree` rooted at the single root node of *tree*.
    """
    logger.debug("tree=%r, props=%r", tree, props)
    child_to_parent: Final[dict[Id, Id]] = {c.id: n.id for n in tree.tree_network if n.children for c in n.children}
    rich_node_map: Final[dict[Id, RichTree]] = {}
    dfs_iter: Final[NodeTreeDFSIterator] = tree.dfs()
    root_node: Final[RoamNode] = next(dfs_iter)
    root_rich: Final[RichTree] = RichTree(make_node_panel(root_node, props))
    rich_node_map[root_node.id] = root_rich
    for node in dfs_iter:
        parent_rich: RichTree = rich_node_map[child_to_parent[node.id]]
        rich_node_map[node.id] = parent_rich.add(make_node_panel(node, props))
    return root_rich


@validate_call
def build_rich_refs_box(tree: NodeTree, props: list[str] = DEFAULT_NODE_PANEL_PROPS) -> Panel | None:
    """Build a Rich :class:`~rich.panel.Panel` summarising the back-reference nodes in *tree*.

    For each node in :attr:`~guffin.roam.tree.NodeTree.refs_by_id`, renders a
    two-column grid row containing a :func:`make_node_panel` on the left and a
    *referenced by* panel listing the ids of tree nodes that cite it on the right.
    All rows are collected into a single ``refs`` panel.

    Returns ``None`` when :attr:`~guffin.roam.tree.NodeTree.refs_by_id` is empty.

    Args:
        tree: The :class:`~guffin.roam.tree.NodeTree` whose
            :attr:`~guffin.roam.tree.NodeTree.refs_by_id` and
            :attr:`~guffin.roam.tree.NodeTree.tree_network` are used.
        props: Ordered list of :class:`~guffin.roam.node.RoamNode` field names
            to include in each node panel body.  Defaults to :data:`DEFAULT_NODE_PANEL_PROPS`.

    Returns:
        A :class:`~rich.panel.Panel` titled ``refs`` grouping one row per referenced
        node, or ``None`` when *tree* has no refs.
    """
    if not tree.refs_by_id:
        return None
    referencing_ids_by_ref_id: Final[dict[Id, list[Id]]] = {
        ref_id: [n.id for n in tree.tree_network if n.refs is not None and any(r.id == ref_id for r in n.refs)]
        for ref_id in tree.refs_by_id
    }
    ref_rows: Final[list[Table]] = []
    for ref_node in tree.refs_by_id.values():
        back_ref_text: str = "  ".join(str(i) for i in referencing_ids_by_ref_id[ref_node.id])
        back_refs_panel: Panel = Panel(back_ref_text or "(none)", title="referenced by")
        row: Table = Table.grid(padding=(0, 1))
        row.add_column()
        row.add_column()
        row.add_row(make_node_panel(ref_node, props), back_refs_panel)
        ref_rows.append(row)
    return Panel(Group(*ref_rows), title="refs")


@validate_call
def make_vertex_panel(vertex: Vertex) -> Panel:
    """Render *vertex* as a Rich Panel for display in a terminal tree.

    The panel title shows a type-specific summary with the vertex ``uid`` in
    parentheses:

    - :class:`~guffin.vertex.PageVertex` — page title.
    - :class:`~guffin.vertex.HeadingVertex` — ``H{n}: <text>``.
    - :class:`~guffin.vertex.TextContentVertex` — block text as-is.
    - :class:`~guffin.vertex.ImageVertex` — ``IMAGE [<alt>](<firestore_url>)``.

    The panel body shows ``type``, ``children``, and ``refs``.

    Args:
        vertex: The :data:`~guffin.vertex.Vertex` to render.

    Returns:
        A :class:`~rich.panel.Panel` with a labelled title and metadata body.
    """
    logger.debug("vertex=%r", vertex)
    if isinstance(vertex, PageVertex):
        text: str = vertex.title
    elif isinstance(vertex, HeadingVertex):
        text = f"H{vertex.heading}: {vertex.text}"
    elif isinstance(vertex, TextContentVertex):
        text = vertex.text
    else:
        text = f"IMAGE [{vertex.alt_text or ''}](<firestore_url>)"
    title: Final[str] = f"[bold #00aa00]{text} ({vertex.uid})[/bold #00aa00]"
    children_str: Final[str] = f"[{', '.join(vertex.children)}]" if vertex.children else "None"
    refs_str: Final[str] = f"[{', '.join(vertex.refs)}]" if vertex.refs else "None"
    content: Final[str] = f"type={vertex.vertex_type.value}  children={children_str}  refs={refs_str}"
    return Panel(Text(content), title=title, expand=False)


@validate_call
def build_rich_vertex_tree(vertex_tree: VertexTree) -> RichTree:
    """Build a Rich tree from *vertex_tree* using a depth-first traversal.

    Locates the root vertex (the one not referenced as a child by any other
    vertex), then performs an iterative pre-order DFS, attaching each vertex
    as a Rich panel under its parent in the rendered tree.

    Args:
        vertex_tree: The :class:`~guffin.vertex_tree.VertexTree` to render.

    Returns:
        A :class:`~rich.tree.Tree` rooted at the single root vertex of
        *vertex_tree*.
    """
    logger.debug("vertex_tree=%r", vertex_tree)
    child_to_parent: Final[dict[Uid, Uid]] = {
        child_uid: v.uid for v in vertex_tree.vertices if v.children for child_uid in v.children
    }
    rich_map: Final[dict[Uid, RichTree]] = {}
    dfs_iter: Final[VertexTreeDFSIterator] = vertex_tree.dfs()
    root: Final[Vertex] = next(dfs_iter)
    root_rich: Final[RichTree] = RichTree(make_vertex_panel(root))
    rich_map[root.uid] = root_rich
    for vertex in dfs_iter:
        parent_rich: RichTree = rich_map[child_to_parent[vertex.uid]]
        rich_map[vertex.uid] = parent_rich.add(make_vertex_panel(vertex))
    return root_rich


# ---------------------------------------------------------------------------
# Raw-results table
# ---------------------------------------------------------------------------


def _is_id_ref_dict(val: object) -> TypeGuard[dict[str, object]]:
    """Return True iff *val* is a single-entry ``{"id": <value>}`` dict."""
    if not isinstance(val, dict):
        return False
    return len(val) == 1 and "id" in val  # type: ignore[arg-type]


def _is_obj_list(val: object) -> TypeGuard[list[object]]:
    """Return True iff *val* is a list."""
    return isinstance(val, list)


_RAW_RESULTS_EXCLUDED_ATTRS: Final[frozenset[str]] = frozenset(
    {
        "open",
        "prevent-clean",
        "sidebar",
        "time",
        "user",
        "view-type",
    }
)
"""Pull-block attribute keys suppressed from the raw-results Rich table."""

_RAW_RESULTS_COL_ORDER: Final[tuple[str, ...]] = (
    "id",
    "uid",
    "string",
    "title",
    "children",
    "order",
    "parents",
    "page",
    "heading",
    "props",
)
"""Preferred left-to-right column order for the raw-results Rich table.

Columns whose key appears in this tuple are placed first, in the order listed.
All remaining (unrecognized) columns follow, sorted alphabetically.
"""

_RAW_RESULTS_COL_HEADERS: Final[dict[str, str]] = {
    "heading": "H",
    "order": "ord",
}
"""Override display headers for the raw-results Rich table (key → header label).

Keys absent from this dict use the raw attribute name as the header.
"""

_RAW_RESULTS_COL_STYLES: Final[dict[str, str]] = {
    # identity
    "id": "bold yellow",
    "uid": "bold yellow",
    # text content
    "string": "bold green",
    "title": "bold green",
    # structure / relationships
    "children": "bold cyan",
    "order": "bold cyan",
    "parents": "bold cyan",
    "page": "bold cyan",
    "refs": "bold cyan",
    # display
    "heading": "bold magenta",
    # extended attributes
    "props": "bold blue",
}
"""Rich header styles for the raw-results table, keyed by raw attribute name.

Columns absent from this dict fall back to ``"bold white"``.
"""

_RAW_RESULTS_COL_STYLE_DEFAULT: Final[str] = "bold white"
"""Fallback Rich header style for columns not listed in :data:`_RAW_RESULTS_COL_STYLES`."""

_RAW_RESULTS_COL_TRUNCATE: Final[dict[str, int]] = {
    "string": 30,
}
"""Maximum display length (in characters) for specific columns in the raw-results table.

Cell values longer than the limit are silently truncated to that many characters.
"""

_URL_RE: Final[re.Pattern[str]] = re.compile(r"https?://[^\s\"']+")
"""Regex that matches ``http://`` or ``https://`` URLs, stopping before whitespace or quotes."""


def _truncate_urls_in_cell(cell: str) -> str:
    """Replace each URL in *cell* with its first 15 characters followed by ``…``.

    URLs are detected by :data:`_URL_RE`.  Matches shorter than 15 characters
    are left unchanged.
    """

    def _shorten(m: re.Match[str]) -> str:
        url: Final[str] = m.group()
        return url[:15] + "…" if len(url) > 15 else url

    return _URL_RE.sub(_shorten, cell)


@validate_call
def build_rich_raw_table(fetch_result: NodeFetchResult) -> Table:
    """Build and return a Rich :class:`~rich.table.Table` of raw Datalog pull-blocks.

    Rows are sorted by ``id``; columns cover every attribute key present across
    all pull-blocks, excluding those in :data:`_RAW_RESULTS_EXCLUDED_ATTRS`, and
    ordered according to :data:`_RAW_RESULTS_COL_ORDER` (remaining keys follow
    alphabetically).  :class:`~guffin.roam.primitives.IdObject` values and
    single-entry ``{"id": …}`` ref dicts are rendered as plain integer ids; lists
    of such refs are rendered as a comma-separated id sequence.  Column headers
    are overridden per :data:`_RAW_RESULTS_COL_HEADERS`; cell values are
    truncated per :data:`_RAW_RESULTS_COL_TRUNCATE`; URLs inside ``props``
    cells are additionally shortened to 15 characters via
    :func:`_truncate_urls_in_cell`.

    Args:
        fetch_result: Fetch result whose :attr:`~guffin.roam.node_fetch_result.NodeFetchResult.raw_result`
            supplies the pull-block rows.

    Returns:
        A fully populated :class:`~rich.table.Table` ready for printing.
    """
    pull_blocks: Final[list[dict[str, object]]] = sorted(
        (row[0] for row in fetch_result.raw_result),
        key=lambda pb: v if isinstance(v := pb.get("id"), int) else 0,
    )
    col_rank: Final[dict[str, int]] = {k: i for i, k in enumerate(_RAW_RESULTS_COL_ORDER)}
    all_keys: Final[list[str]] = sorted(
        {key for pb in pull_blocks for key in pb} - _RAW_RESULTS_EXCLUDED_ATTRS,
        key=lambda k: (col_rank.get(k, len(_RAW_RESULTS_COL_ORDER)), k),
    )
    raw_table: Final[Table] = Table(show_lines=True)
    for key in all_keys:
        raw_table.add_column(
            _RAW_RESULTS_COL_HEADERS.get(key, key),
            header_style=_RAW_RESULTS_COL_STYLES.get(key, _RAW_RESULTS_COL_STYLE_DEFAULT),
            overflow="fold",
        )
    for pb in pull_blocks:
        row_vals: list[str] = []
        for key in all_keys:
            val: object = pb.get(key, "")
            cell: str
            if isinstance(val, IdObject):
                cell = str(val.id)
            elif _is_id_ref_dict(val):
                cell = str(val.get("id", ""))
            elif _is_obj_list(val):
                id_parts: list[str] = []
                is_id_list: bool = True
                for raw_el in val:
                    if isinstance(raw_el, IdObject):
                        id_parts.append(str(raw_el.id))
                    elif _is_id_ref_dict(raw_el):
                        id_parts.append(str(raw_el.get("id", "")))
                    else:
                        is_id_list = False
                        break
                cell = ", ".join(id_parts) if is_id_list else str(val)
            else:
                cell = str(val)
            if key == "props":
                cell = _truncate_urls_in_cell(cell)
            trunc: int | None = _RAW_RESULTS_COL_TRUNCATE.get(key)
            if trunc is not None:
                cell = cell[:trunc]
            row_vals.append(cell)
        raw_table.add_row(*row_vals)
    return raw_table
