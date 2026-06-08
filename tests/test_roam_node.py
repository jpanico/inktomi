"""Tests for the roam_node module."""

import pytest

from guffin.roam_node import (
    NodeType,
    RoamNode,
    node_type,
)
from guffin.roam_primitives import IdObject

from conftest import STUB_TIME, STUB_USER

_FIRESTORE_URL = (
    "https://firebasestorage.googleapis.com/v0/b/test.appspot.com" "/o/imgs%2Fphoto.jpeg?alt=media&token=abc123"
)
_IMAGE_STRING = f"![A flower]({_FIRESTORE_URL})"


def _make_image(uid: str = "imageuid1", id: int = 101, string: str = _IMAGE_STRING) -> RoamNode:
    """Return a minimal Firestore image-block RoamNode."""
    return RoamNode(
        uid=uid,
        id=id,
        time=STUB_TIME,
        user=STUB_USER,
        string=string,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_heading(uid: str = "headnguid", id: int = 102, string: str = "Section One", level: int = 2) -> RoamNode:
    """Return a minimal native-heading RoamNode."""
    return RoamNode(
        uid=uid,
        id=id,
        time=STUB_TIME,
        user=STUB_USER,
        string=string,
        heading=level,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_text(uid: str = "textuid01", id: int = 104, string: str = "Some plain text") -> RoamNode:
    """Return a minimal plain-text RoamNode."""
    return RoamNode(
        uid=uid,
        id=id,
        time=STUB_TIME,
        user=STUB_USER,
        string=string,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


# ---------------------------------------------------------------------------
# TestRoamNodeProps
# ---------------------------------------------------------------------------


class TestRoamNodeProps:
    """Tests for the RoamNode.props field (block properties / :block/props)."""

    def test_props_defaults_to_none(self) -> None:
        """Test that props is None when not supplied."""
        node = RoamNode(
            uid="block0001",
            id=1,
            time=STUB_TIME,
            user=STUB_USER,
            string="stub",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node.props is None

    def test_props_accepts_string_values(self) -> None:
        """Test that props stores a string-valued block property map."""
        node = RoamNode(
            uid="block0001",
            id=1,
            time=STUB_TIME,
            user=STUB_USER,
            string="stub",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            props={"ah-level": "h4"},
        )
        assert node.props == {"ah-level": "h4"}

    def test_props_accepts_multiple_entries(self) -> None:
        """Test that props can hold multiple block property entries."""
        node = RoamNode(
            uid="block0001",
            id=1,
            time=STUB_TIME,
            user=STUB_USER,
            string="stub",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            props={"ah-level": "h5", ":some-other": "value"},
        )
        assert node.props is not None
        assert node.props["ah-level"] == "h5"
        assert node.props[":some-other"] == "value"

    def test_props_round_trips_through_model_validate(self) -> None:
        """Test that props survives a model_validate round-trip from a raw dict."""
        raw: dict[str, object] = {
            "uid": "block0001",
            "id": 1,
            "time": STUB_TIME,
            "user": {"id": 1},
            "string": "stub",
            "parents": [{"id": 99}],
            "page": {"id": 99},
            "props": {"ah-level": "h6"},
        }
        node = RoamNode.model_validate(raw)
        assert node.props == {"ah-level": "h6"}

    def test_props_none_round_trips_through_model_validate(self) -> None:
        """Test that a missing props key in raw dict produces props=None."""
        raw: dict[str, object] = {
            "uid": "block0001",
            "id": 1,
            "time": STUB_TIME,
            "user": {"id": 1},
            "string": "stub",
            "parents": [{"id": 99}],
            "page": {"id": 99},
        }
        node = RoamNode.model_validate(raw)
        assert node.props is None

    def test_node_with_props_is_frozen(self) -> None:
        """Test that a node with props set is immutable."""
        node = RoamNode(
            uid="block0001",
            id=1,
            time=STUB_TIME,
            user=STUB_USER,
            string="stub",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            props={"ah-level": "h4"},
        )
        with pytest.raises(Exception):
            node.props = None  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestNodeType
# ---------------------------------------------------------------------------


class TestNodeType:
    """Tests for the NodeType enum."""

    def test_page_value(self) -> None:
        """Test that NodeType.ROAM_PAGE has string value 'roam/page'."""
        assert NodeType.ROAM_PAGE == "roam/page"

    def test_block_value(self) -> None:
        """Test that NodeType.ROAM_PLAIN_BLOCK has string value 'roam/plain-block'."""
        assert NodeType.ROAM_PLAIN_BLOCK == "roam/plain-block"

    def test_embed_value(self) -> None:
        """Test that NodeType.ROAM_EMBED_BLOCK has string value 'roam/embed-block'."""
        assert NodeType.ROAM_EMBED_BLOCK == "roam/embed-block"

    def test_image_value(self) -> None:
        """Test that NodeType.ROAM_IMAGE_BLOCK has string value 'roam/image-block'."""
        assert NodeType.ROAM_IMAGE_BLOCK == "roam/image-block"

    def test_heading_value(self) -> None:
        """Test that NodeType.ROAM_HEADING_BLOCK has string value 'roam/heading-block'."""
        assert NodeType.ROAM_HEADING_BLOCK == "roam/heading-block"

    def test_exactly_five_members(self) -> None:
        """Test that NodeType has exactly five members."""
        assert set(NodeType) == {
            NodeType.ROAM_PAGE,
            NodeType.ROAM_PLAIN_BLOCK,
            NodeType.ROAM_EMBED_BLOCK,
            NodeType.ROAM_IMAGE_BLOCK,
            NodeType.ROAM_HEADING_BLOCK,
        }


# ---------------------------------------------------------------------------
# TestNodeTypeFunction
# ---------------------------------------------------------------------------


class TestNodeTypeFunction:
    """Tests for the node_type() function."""

    def test_page_node_returns_page(self) -> None:
        """Test that a node with title set returns NodeType.ROAM_PAGE."""
        node = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="My Page", children=[])
        assert node_type(node) is NodeType.ROAM_PAGE

    def test_block_node_returns_block(self) -> None:
        """Test that a node with string set returns NodeType.ROAM_PLAIN_BLOCK."""
        node = RoamNode(
            uid="block0001",
            id=2,
            time=STUB_TIME,
            user=STUB_USER,
            string="block text",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.ROAM_PLAIN_BLOCK

    def test_page_node_is_not_block(self) -> None:
        """Test that a page node does not return NodeType.ROAM_PLAIN_BLOCK."""
        node = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="My Page", children=[])
        assert node_type(node) is not NodeType.ROAM_PLAIN_BLOCK

    def test_block_node_is_not_page(self) -> None:
        """Test that a block node does not return NodeType.ROAM_PAGE."""
        node = RoamNode(
            uid="block0001",
            id=2,
            time=STUB_TIME,
            user=STUB_USER,
            string="block text",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is not NodeType.ROAM_PAGE

    def test_embed_node_returns_embed(self) -> None:
        """Test that a node with title 'embed' returns NodeType.ROAM_EMBED_BLOCK."""
        node = RoamNode(uid="embed0001", id=3, time=STUB_TIME, user=STUB_USER, title="embed")
        assert node_type(node) is NodeType.ROAM_EMBED_BLOCK

    def test_embed_node_is_not_page(self) -> None:
        """Test that an embed node does not return NodeType.ROAM_PAGE."""
        node = RoamNode(uid="embed0001", id=3, time=STUB_TIME, user=STUB_USER, title="embed")
        assert node_type(node) is not NodeType.ROAM_PAGE

    def test_image_node_returns_image(self) -> None:
        """Test that a bare Firestore image block returns NodeType.ROAM_IMAGE_BLOCK."""
        assert node_type(_make_image()) is NodeType.ROAM_IMAGE_BLOCK

    def test_image_node_is_not_block(self) -> None:
        """Test that an image node does not return NodeType.ROAM_PLAIN_BLOCK."""
        assert node_type(_make_image()) is not NodeType.ROAM_PLAIN_BLOCK

    def test_image_node_with_surrounding_whitespace_returns_image(self) -> None:
        """Test that leading/trailing whitespace around the image link is tolerated."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            time=STUB_TIME,
            user=STUB_USER,
            string=f"  {_IMAGE_STRING}  ",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.ROAM_IMAGE_BLOCK

    def test_image_node_with_empty_alt_text_returns_image(self) -> None:
        """Test that an image link with empty alt text returns NodeType.ROAM_IMAGE_BLOCK."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            time=STUB_TIME,
            user=STUB_USER,
            string=f"![]({_FIRESTORE_URL})",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.ROAM_IMAGE_BLOCK

    def test_text_before_image_returns_block(self) -> None:
        """Test that text before the image link yields NodeType.ROAM_PLAIN_BLOCK, not Image."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            time=STUB_TIME,
            user=STUB_USER,
            string=f"see: {_IMAGE_STRING}",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.ROAM_PLAIN_BLOCK

    def test_text_after_image_returns_block(self) -> None:
        """Test that text after the image link yields NodeType.ROAM_PLAIN_BLOCK, not Image."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            time=STUB_TIME,
            user=STUB_USER,
            string=f"{_IMAGE_STRING} caption",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.ROAM_PLAIN_BLOCK

    def test_two_image_links_returns_block(self) -> None:
        """Test that a string with two image links yields NodeType.ROAM_PLAIN_BLOCK, not Image."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            time=STUB_TIME,
            user=STUB_USER,
            string=_IMAGE_STRING * 2,
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.ROAM_PLAIN_BLOCK

    def test_relative_url_image_returns_block(self) -> None:
        """Test that a Markdown image with a relative URL yields NodeType.ROAM_PLAIN_BLOCK, not Image."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            time=STUB_TIME,
            user=STUB_USER,
            string="![alt](relative/path.jpg)",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.ROAM_PLAIN_BLOCK

    def test_heading_node_returns_heading(self) -> None:
        """Test that a native heading block (heading=2) returns NodeType.ROAM_HEADING_BLOCK."""
        assert node_type(_make_heading()) is NodeType.ROAM_HEADING_BLOCK

    def test_heading_node_is_not_block(self) -> None:
        """Test that a heading node does not return NodeType.ROAM_PLAIN_BLOCK."""
        assert node_type(_make_heading()) is not NodeType.ROAM_PLAIN_BLOCK

    def test_augmented_heading_returns_heading(self) -> None:
        """Test that a block with props['ah-level'] set returns NodeType.ROAM_HEADING_BLOCK."""
        node = RoamNode(
            uid="headnguid",
            id=102,
            time=STUB_TIME,
            user=STUB_USER,
            string="Deep Section",
            props={"ah-level": "h4"},
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.ROAM_HEADING_BLOCK

    def test_plain_text_block_is_not_heading(self) -> None:
        """Test that a plain text block does not return NodeType.ROAM_HEADING_BLOCK."""
        assert node_type(_make_text()) is not NodeType.ROAM_HEADING_BLOCK

    def test_result_is_str_enum(self) -> None:
        """Test that the returned value is a NodeType StrEnum member."""
        node = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="My Page", children=[])
        result = node_type(node)
        assert isinstance(result, NodeType)
        assert isinstance(result, str)
