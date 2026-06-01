"""Roam Research Datomic schema model types.

Public symbols:

- :class:`RoamNamespace` — enumeration of all Datomic attribute namespaces present
  in the Roam graph schema.
- :class:`RoamAttribute` — enumeration of all ``(namespace, attr_name)`` pairs
  in the Roam Datomic schema.
- :data:`RoamSchema` — a list of :class:`RoamAttribute` members representing the
  full schema of a live Roam graph.
"""

from enum import Enum, StrEnum


class RoamNamespace(StrEnum):
    """Enumeration of all Datomic attribute namespaces in the Roam graph schema.

    Each member's value is the namespace string as it appears in the Datomic schema
    (e.g. ``"block"``, ``"create"``, ``"user"``).  Because this is a :class:`StrEnum`,
    members compare equal to their string equivalents::

        assert RoamNamespace.BLOCK == "block"
    """

    ATTRS = "attrs"
    BLOCK = "block"
    CHILDREN = "children"
    CREATE = "create"
    EDIT = "edit"
    ENTITY = "entity"
    GRAPH = "graph"
    LOG = "log"
    NODE = "node"
    PAGE = "page"
    RESTRICTIONS = "restrictions"
    TOKEN = "token"
    USER = "user"
    VC = "vc"
    VERSION = "version"
    WINDOW = "window"


class RoamAttribute(Enum):
    """Enumeration of all ``(namespace, attr_name)`` pairs in the Roam Datomic schema.

    Each member's :attr:`value` is a ``tuple[RoamNamespace, str]``.  Typed accessors
    :attr:`namespace` and :attr:`attr_name` expose the two components without
    requiring callers to unpack :attr:`value` manually::

        assert RoamAttribute.BLOCK_UID.namespace is RoamNamespace.BLOCK
        assert RoamAttribute.BLOCK_UID.attr_name == "uid"
    """

    value: tuple[RoamNamespace, str]  # type: ignore[override]

    # attrs/
    ATTRS_LOOKUP = (RoamNamespace.ATTRS, "lookup")

    # block/
    BLOCK_CHILDREN = (RoamNamespace.BLOCK, "children")
    BLOCK_HEADING = (RoamNamespace.BLOCK, "heading")
    BLOCK_OPEN = (RoamNamespace.BLOCK, "open")
    BLOCK_ORDER = (RoamNamespace.BLOCK, "order")
    BLOCK_PAGE = (RoamNamespace.BLOCK, "page")
    BLOCK_PARENTS = (RoamNamespace.BLOCK, "parents")
    BLOCK_PROPS = (RoamNamespace.BLOCK, "props")
    BLOCK_REFS = (RoamNamespace.BLOCK, "refs")
    BLOCK_STRING = (RoamNamespace.BLOCK, "string")
    BLOCK_TEXT_ALIGN = (RoamNamespace.BLOCK, "text-align")
    BLOCK_UID = (RoamNamespace.BLOCK, "uid")

    # children/
    CHILDREN_VIEW_TYPE = (RoamNamespace.CHILDREN, "view-type")

    # create/
    CREATE_TIME = (RoamNamespace.CREATE, "time")
    CREATE_USER = (RoamNamespace.CREATE, "user")

    # edit/
    EDIT_SEEN_BY = (RoamNamespace.EDIT, "seen-by")
    EDIT_TIME = (RoamNamespace.EDIT, "time")
    EDIT_USER = (RoamNamespace.EDIT, "user")

    # entity/
    ENTITY_ATTRS = (RoamNamespace.ENTITY, "attrs")

    # graph/
    GRAPH_SETTINGS = (RoamNamespace.GRAPH, "settings")

    # log/
    LOG_ID = (RoamNamespace.LOG, "id")

    # node/
    NODE_TITLE = (RoamNamespace.NODE, "title")

    # page/
    PAGE_SIDEBAR = (RoamNamespace.PAGE, "sidebar")

    # restrictions/
    RESTRICTIONS_PREVENT_CLEAN = (RoamNamespace.RESTRICTIONS, "prevent-clean")

    # token/
    TOKEN_DESCRIPTION = (RoamNamespace.TOKEN, "description")

    # user/
    USER_DISPLAY_NAME = (RoamNamespace.USER, "display-name")
    USER_DISPLAY_PAGE = (RoamNamespace.USER, "display-page")
    USER_PHOTO_URL = (RoamNamespace.USER, "photo-url")
    USER_SETTINGS = (RoamNamespace.USER, "settings")
    USER_UID = (RoamNamespace.USER, "uid")

    # vc/
    VC_BLOCKS = (RoamNamespace.VC, "blocks")

    # version/
    VERSION_ID = (RoamNamespace.VERSION, "id")
    VERSION_NONCE = (RoamNamespace.VERSION, "nonce")
    VERSION_UPGRADED_NONCE = (RoamNamespace.VERSION, "upgraded-nonce")

    # window/
    WINDOW_ID = (RoamNamespace.WINDOW, "id")
    WINDOW_MENTIONS_STATE = (RoamNamespace.WINDOW, "mentions-state")

    def __init__(self, namespace: RoamNamespace, attr_name: str) -> None:
        """Bind typed accessors from the ``(namespace, attr_name)`` member value."""
        self.namespace: RoamNamespace = namespace
        self.attr_name: str = attr_name

    def __str__(self) -> str:
        """Return the Datomic attribute key, e.g. ``:block/uid``."""
        return f":{self.namespace}/{self.attr_name}"


type RoamSchema = list[RoamAttribute]
"""Roam Datomic schema as a list of :class:`RoamAttribute` members.

Each member corresponds to one row from the ``[:find ?namespace ?attr ...]``
schema query, e.g. :attr:`RoamAttribute.BLOCK_UID`.
"""
