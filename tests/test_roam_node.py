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


def _make_page(uid: str = "pageuid01", id: int = 100, title: str = "My Page") -> RoamNode:
    """Return a minimal page RoamNode."""
    return RoamNode(uid=uid, id=id, time=STUB_TIME, user=STUB_USER, title=title, children=[])


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
        """Test that NodeType.Page has string value 'Page'."""
        assert NodeType.Page == "Page"

    def test_block_value(self) -> None:
        """Test that NodeType.Block has string value 'Block'."""
        assert NodeType.Block == "Block"

    def test_embed_value(self) -> None:
        """Test that NodeType.Embed has string value 'Embed'."""
        assert NodeType.Embed == "Embed"

    def test_image_value(self) -> None:
        """Test that NodeType.Image has string value 'Image'."""
        assert NodeType.Image == "Image"

    def test_exactly_four_members(self) -> None:
        """Test that NodeType has exactly four members."""
        assert set(NodeType) == {NodeType.Page, NodeType.Block, NodeType.Embed, NodeType.Image}


# ---------------------------------------------------------------------------
# TestNodeTypeFunction
# ---------------------------------------------------------------------------


class TestNodeTypeFunction:
    """Tests for the node_type() function."""

    def test_page_node_returns_page(self) -> None:
        """Test that a node with title set returns NodeType.Page."""
        node = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="My Page", children=[])
        assert node_type(node) is NodeType.Page

    def test_block_node_returns_block(self) -> None:
        """Test that a node with string set returns NodeType.Block."""
        node = RoamNode(
            uid="block0001",
            id=2,
            time=STUB_TIME,
            user=STUB_USER,
            string="block text",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.Block

    def test_page_node_is_not_block(self) -> None:
        """Test that a page node does not return NodeType.Block."""
        node = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="My Page", children=[])
        assert node_type(node) is not NodeType.Block

    def test_block_node_is_not_page(self) -> None:
        """Test that a block node does not return NodeType.Page."""
        node = RoamNode(
            uid="block0001",
            id=2,
            time=STUB_TIME,
            user=STUB_USER,
            string="block text",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is not NodeType.Page

    def test_embed_node_returns_embed(self) -> None:
        """Test that a node with title 'embed' returns NodeType.Embed."""
        node = RoamNode(uid="embed0001", id=3, time=STUB_TIME, user=STUB_USER, title="embed")
        assert node_type(node) is NodeType.Embed

    def test_embed_node_is_not_page(self) -> None:
        """Test that an embed node does not return NodeType.Page."""
        node = RoamNode(uid="embed0001", id=3, time=STUB_TIME, user=STUB_USER, title="embed")
        assert node_type(node) is not NodeType.Page

    def test_image_node_returns_image(self) -> None:
        """Test that a bare Firestore image block returns NodeType.Image."""
        assert node_type(_make_image()) is NodeType.Image

    def test_image_node_is_not_block(self) -> None:
        """Test that an image node does not return NodeType.Block."""
        assert node_type(_make_image()) is not NodeType.Block

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
        assert node_type(node) is NodeType.Image

    def test_image_node_with_empty_alt_text_returns_image(self) -> None:
        """Test that an image link with empty alt text returns NodeType.Image."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            time=STUB_TIME,
            user=STUB_USER,
            string=f"![]({_FIRESTORE_URL})",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.Image

    def test_text_before_image_returns_block(self) -> None:
        """Test that text before the image link yields NodeType.Block, not Image."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            time=STUB_TIME,
            user=STUB_USER,
            string=f"see: {_IMAGE_STRING}",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.Block

    def test_text_after_image_returns_block(self) -> None:
        """Test that text after the image link yields NodeType.Block, not Image."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            time=STUB_TIME,
            user=STUB_USER,
            string=f"{_IMAGE_STRING} caption",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.Block

    def test_two_image_links_returns_block(self) -> None:
        """Test that a string with two image links yields NodeType.Block, not Image."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            time=STUB_TIME,
            user=STUB_USER,
            string=_IMAGE_STRING * 2,
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.Block

    def test_relative_url_image_returns_block(self) -> None:
        """Test that a Markdown image with a relative URL yields NodeType.Block, not Image."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            time=STUB_TIME,
            user=STUB_USER,
            string="![alt](relative/path.jpg)",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.Block

    def test_result_is_str_enum(self) -> None:
        """Test that the returned value is a NodeType StrEnum member."""
        node = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="My Page", children=[])
        result = node_type(node)
        assert isinstance(result, NodeType)
        assert isinstance(result, str)
