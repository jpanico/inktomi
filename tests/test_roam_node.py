"""Tests for the roam_node module."""

import yaml
import pytest
from typing import Final
from pydantic import ValidationError

from guffin.common.geometry import ImageSize
from guffin.roam.primitives import CALLOUT_RE, CalloutType, IdObject, RoamCallout, callout
from guffin.roam.node import (
    NodeType,
    RoamNode,
    image_size,
    node_type,
)

from conftest import FIXTURES_YAML_DIR, STUB_TIME, STUB_USER

_FIRESTORE_URL = (
    "https://firebasestorage.googleapis.com/v0/b/test.appspot.com" "/o/imgs%2Fphoto.jpeg?alt=media&token=abc123"
)
_IMAGE_STRING = f"![A flower]({_FIRESTORE_URL})"

_ALL_CALLOUT_TYPES: Final[list[str]] = [
    "INFO",
    "QUOTE",
    "EXAMPLE",
    "NOTE",
    "WARNING",
    "DANGER",
    "TIP",
    "SUMMARY",
    "SUCCESS",
    "QUESTION",
    "FAILURE",
    "BUG",
]


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


def _make_callout(uid: str = "callutuid", id: int = 105, callout_type: str = "INFO", suffix: str = "") -> RoamNode:
    """Return a minimal callout RoamNode with the given callout type."""
    return RoamNode(
        uid=uid,
        id=id,
        time=STUB_TIME,
        user=STUB_USER,
        string=f"[[>]] [[!{callout_type}]]{suffix}",
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

    def test_callout_value(self) -> None:
        """Test that NodeType.ROAM_CALLOUT_BLOCK has string value 'roam/callout-block'."""
        assert NodeType.ROAM_CALLOUT_BLOCK == "roam/callout-block"

    def test_exactly_six_members(self) -> None:
        """Test that NodeType has exactly six members."""
        assert set(NodeType) == {
            NodeType.ROAM_PAGE,
            NodeType.ROAM_PLAIN_BLOCK,
            NodeType.ROAM_EMBED_BLOCK,
            NodeType.ROAM_IMAGE_BLOCK,
            NodeType.ROAM_HEADING_BLOCK,
            NodeType.ROAM_CALLOUT_BLOCK,
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

    def test_callout_node_returns_callout(self) -> None:
        """Test that a block with a valid callout marker returns NodeType.ROAM_CALLOUT_BLOCK."""
        assert node_type(_make_callout()) is NodeType.ROAM_CALLOUT_BLOCK

    def test_callout_node_is_not_plain_block(self) -> None:
        """Test that a callout node does not return NodeType.ROAM_PLAIN_BLOCK."""
        assert node_type(_make_callout()) is not NodeType.ROAM_PLAIN_BLOCK

    def test_callout_with_suffix_content_returns_callout(self) -> None:
        """Test that a callout marker with trailing content still returns NodeType.ROAM_CALLOUT_BLOCK."""
        assert node_type(_make_callout(suffix=" some callout body")) is NodeType.ROAM_CALLOUT_BLOCK

    def test_all_callout_types_return_callout(self) -> None:
        """Test that each of the twelve valid callout types returns NodeType.ROAM_CALLOUT_BLOCK."""
        valid_types = [
            "INFO",
            "QUOTE",
            "EXAMPLE",
            "NOTE",
            "WARNING",
            "DANGER",
            "TIP",
            "SUMMARY",
            "SUCCESS",
            "QUESTION",
            "FAILURE",
            "BUG",
        ]
        for callout_type in valid_types:
            assert node_type(_make_callout(callout_type=callout_type)) is NodeType.ROAM_CALLOUT_BLOCK

    def test_result_is_str_enum(self) -> None:
        """Test that the returned value is a NodeType StrEnum member."""
        node = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="My Page", children=[])
        result = node_type(node)
        assert isinstance(result, NodeType)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# TestRoamNodeCalloutValidation
# ---------------------------------------------------------------------------


class TestRoamNodeCalloutValidation:
    """Tests for RoamNode validation of callout block strings."""

    def _make_block(self, string: str) -> RoamNode:
        return RoamNode(
            uid="callutuid",
            id=105,
            time=STUB_TIME,
            user=STUB_USER,
            string=string,
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )

    def test_valid_callout_string_accepted(self) -> None:
        """Test that a well-formed callout marker string is accepted."""
        node = self._make_block("[[>]] [[!INFO]]")
        assert node.string == "[[>]] [[!INFO]]"

    def test_valid_callout_with_body_accepted(self) -> None:
        """Test that a callout marker followed by body text is accepted."""
        node = self._make_block("[[>]] [[!WARNING]] Watch out!")
        assert node.string == "[[>]] [[!WARNING]] Watch out!"

    def test_invalid_callout_type_raises(self) -> None:
        """Test that an unrecognised callout type raises ValidationError."""
        with pytest.raises(ValidationError):
            self._make_block("[[>]] [[!INVALID]]")

    def test_missing_type_raises(self) -> None:
        """Test that '[[>]]' with no type marker raises ValidationError."""
        with pytest.raises(ValidationError):
            self._make_block("[[>]]")

    def test_bare_prefix_with_space_raises(self) -> None:
        """Test that '[[>]] ' with no type block raises ValidationError."""
        with pytest.raises(ValidationError):
            self._make_block("[[>]] some text without type")

    def test_lowercase_callout_type_raises(self) -> None:
        """Test that a lowercase callout type (e.g. 'info') raises ValidationError."""
        with pytest.raises(ValidationError):
            self._make_block("[[>]] [[!info]]")

    def test_partial_type_block_raises(self) -> None:
        """Test that a malformed type block like '[[!INFO' raises ValidationError."""
        with pytest.raises(ValidationError):
            self._make_block("[[>]] [[!INFO")

    def test_string_without_prefix_accepted(self) -> None:
        """Test that a plain block string with no '[[>]]' prefix is not affected."""
        node = self._make_block("just some text")
        assert node.string == "just some text"


# ---------------------------------------------------------------------------
# TestCalloutRE
# ---------------------------------------------------------------------------


class TestCalloutRE:
    """Tests for CALLOUT_RE — the full callout block string regex."""

    # --- full RE match ---

    def test_matches_marker_only(self) -> None:
        """Test that a bare callout marker with no title or body matches."""
        assert CALLOUT_RE.match("[[>]] [[!INFO]]") is not None

    def test_matches_marker_with_title(self) -> None:
        """Test that a callout marker followed by a title matches."""
        assert CALLOUT_RE.match("[[>]] [[!NOTE]] This is the title") is not None

    def test_matches_marker_with_title_and_body(self) -> None:
        """Test that a callout marker with a title and a single body line matches."""
        assert CALLOUT_RE.match("[[>]] [[!WARNING]] Title\nBody line") is not None

    def test_matches_marker_with_multiline_body(self) -> None:
        """Test that a callout marker with a title and multiple body lines matches."""
        assert CALLOUT_RE.match("[[>]] [[!INFO]] Title\nLine 1\nLine 2\nLine 3") is not None

    @pytest.mark.parametrize("callout_type", _ALL_CALLOUT_TYPES)
    def test_matches_all_twelve_types(self, callout_type: str) -> None:
        """Test that each of the twelve recognised callout type keywords matches."""
        assert CALLOUT_RE.match(f"[[>]] [[!{callout_type}]] Title") is not None

    def test_no_match_plain_string(self) -> None:
        """Test that a plain string without the callout prefix does not match."""
        assert CALLOUT_RE.match("Just some text") is None

    def test_no_match_empty_string(self) -> None:
        """Test that an empty string does not match."""
        assert CALLOUT_RE.match("") is None

    def test_no_match_prefix_only(self) -> None:
        """Test that the bare [[>]] prefix without a type block does not match."""
        assert CALLOUT_RE.match("[[>]]") is None

    def test_no_match_invalid_type(self) -> None:
        """Test that an unrecognised callout type keyword does not match."""
        assert CALLOUT_RE.match("[[>]] [[!INVALID]] title") is None

    def test_no_match_lowercase_type(self) -> None:
        """Test that a lowercase callout type keyword does not match."""
        assert CALLOUT_RE.match("[[>]] [[!info]] title") is None

    def test_no_match_missing_type_brackets(self) -> None:
        """Test that a malformed marker without the [[!...]] brackets does not match."""
        assert CALLOUT_RE.match("[[>]] !INFO title") is None

    # --- named capture groups ---

    def test_prefix_group(self) -> None:
        """Test that the prefix group captures '[[>]]'."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]] Title")
        assert m is not None
        assert m.group("prefix") == "[[>]]"

    def test_callout_type_group(self) -> None:
        """Test that the callout_type group captures the type keyword."""
        m = CALLOUT_RE.match("[[>]] [[!WARNING]] Title")
        assert m is not None
        assert m.group("callout_type") == "WARNING"

    @pytest.mark.parametrize("callout_type", _ALL_CALLOUT_TYPES)
    def test_callout_type_group_all_twelve(self, callout_type: str) -> None:
        """Test that callout_type captures each of the twelve recognised type keywords."""
        m = CALLOUT_RE.match(f"[[>]] [[!{callout_type}]] Title")
        assert m is not None
        assert m.group("callout_type") == callout_type

    def test_title_group_with_text(self) -> None:
        """Test that the title group captures all text on the first line after the marker."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]] This is the title")
        assert m is not None
        assert m.group("title") == "This is the title"

    def test_title_group_empty_when_marker_only(self) -> None:
        """Test that the title group is an empty string when nothing follows the marker."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]]")
        assert m is not None
        assert m.group("title") == ""

    def test_title_group_strips_leading_whitespace(self) -> None:
        r"""Test that leading whitespace between the marker and title text is consumed by \s*."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]]  Two spaces before title")
        assert m is not None
        assert m.group("title") == "Two spaces before title"

    def test_title_group_is_first_line_only(self) -> None:
        """Test that the title group stops at the first newline."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]] Only the first line\nNot in title")
        assert m is not None
        assert m.group("title") == "Only the first line"

    def test_body_group_none_when_no_newline(self) -> None:
        """Test that the body group is None when the string contains no newline."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]] Title only")
        assert m is not None
        assert m.group("body") is None

    def test_body_group_single_line(self) -> None:
        """Test that the body group captures a single line after the first newline."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]] Title\nBody text here")
        assert m is not None
        assert m.group("body") == "Body text here"

    def test_body_group_multiline(self) -> None:
        """Test that the body group captures all lines after the first newline, preserving embedded newlines."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]] Title\nLine 1\nLine 2\nLine 3")
        assert m is not None
        assert m.group("body") == "Line 1\nLine 2\nLine 3"

    def test_body_group_preserves_blank_lines(self) -> None:
        """Test that blank lines within the body are preserved by the DOTALL body group."""
        body = "- item one\n- item two\n\nA paragraph"
        m = CALLOUT_RE.match(f"[[>]] [[!NOTE]] Title\n{body}")
        assert m is not None
        assert m.group("body") == body


# ---------------------------------------------------------------------------
# TestCallout
# ---------------------------------------------------------------------------


class TestCallout:
    """Tests for the callout() function."""

    # --- returns None ---

    def test_returns_none_for_empty_string(self) -> None:
        """Returns None for an empty string."""
        assert callout("") is None

    def test_returns_none_for_plain_text(self) -> None:
        """Returns None when block_string does not start with CALLOUT_PREFIX."""
        assert callout("Some plain text") is None

    def test_returns_none_for_image_link(self) -> None:
        """Returns None when block_string is a Firestore image link."""
        assert callout(_IMAGE_STRING) is None

    # --- returns RoamCallout ---

    def test_returns_roam_callout_instance(self) -> None:
        """Returns a RoamCallout instance for a valid callout string."""
        assert isinstance(callout("[[>]] [[!INFO]]"), RoamCallout)

    def test_callout_type_field(self) -> None:
        """callout_type matches the marker keyword as a CalloutType member."""
        result = callout("[[>]] [[!WARNING]]")
        assert result is not None
        assert result.callout_type is CalloutType.WARNING

    @pytest.mark.parametrize("ct", _ALL_CALLOUT_TYPES)
    def test_all_twelve_callout_types(self, ct: str) -> None:
        """All twelve callout type keywords are parsed to the correct CalloutType member."""
        result = callout(f"[[>]] [[!{ct}]]")
        assert result is not None
        assert result.callout_type is CalloutType(ct)

    def test_title_with_text(self) -> None:
        """Title captures the text on the first line after the marker."""
        result = callout("[[>]] [[!INFO]] This is the title")
        assert result is not None
        assert result.title == "This is the title"

    def test_title_empty_when_marker_only(self) -> None:
        """Title is an empty string when nothing follows the marker."""
        result = callout("[[>]] [[!INFO]]")
        assert result is not None
        assert result.title == ""

    def test_body_empty_when_no_newline(self) -> None:
        """Body is an empty string when the block string contains no newline."""
        result = callout("[[>]] [[!INFO]] Title only")
        assert result is not None
        assert result.body == ""

    def test_body_single_line(self) -> None:
        """Body captures the single line after the first newline."""
        result = callout("[[>]] [[!INFO]] Title\nBody line")
        assert result is not None
        assert result.body == "Body line"

    def test_body_multiline(self) -> None:
        """Body captures all lines after the first newline, preserving embedded newlines."""
        result = callout("[[>]] [[!INFO]] Title\nLine 1\nLine 2\nLine 3")
        assert result is not None
        assert result.body == "Line 1\nLine 2\nLine 3"

    # --- error cases ---

    def test_raises_value_error_for_malformed_marker(self) -> None:
        """Raises ValueError when block_string starts with CALLOUT_PREFIX but has a malformed marker."""
        with pytest.raises(ValueError, match="does not match callout pattern"):
            callout("[[>]] [[!INVALID]]")

    def test_raises_validation_error_for_null_input(self) -> None:
        """Raises ValidationError when None is passed."""
        with pytest.raises(ValidationError):
            callout(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestImageSize
# ---------------------------------------------------------------------------


class TestImageSize:
    """Tests for the image_size() function."""

    def test_returns_none_for_non_image_node(self) -> None:
        """Test that image_size returns None for any non-ROAM_IMAGE_BLOCK node."""
        assert image_size(_make_text()) is None

    def test_returns_empty_image_size_when_no_image_size_prop(self) -> None:
        """Test that image_size returns ImageSize() when the node has no image-size prop."""
        assert image_size(_make_image()) == ImageSize()

    def test_returns_dimensions_from_fixture(self) -> None:
        """Test that image_size extracts width and height from the Article 1 fixture node zZG-BfWvs.

        zZG-BfWvs has ``image-size: {<url>: {width: 257, height: null}}``, so the expected
        result is ``ImageSize(width=257, height=None)``.
        """
        raw: list[dict[str, object]] = yaml.safe_load((FIXTURES_YAML_DIR / "test_article_1_nodes.yaml").read_text())
        nodes: list[RoamNode] = [RoamNode.model_validate(r) for r in raw]
        fixture_node: RoamNode = next(n for n in nodes if n.uid == "zZG-BfWvs")
        assert image_size(fixture_node) == ImageSize(width=257, height=None)

    def test_raises_validation_error_for_invalid_image_size_prop(self) -> None:
        """Test that image_size raises ValidationError when image-size prop has an invalid structure.

        The expected structure is ``dict[str, dict[str, int | None]]``; passing a plain
        string value triggers ``_IMAGE_SIZE_PROP_ADAPTER.validate_python`` to raise
        ``ValidationError``.
        """
        node = RoamNode(
            uid="imageuid1",
            id=101,
            time=STUB_TIME,
            user=STUB_USER,
            string=_IMAGE_STRING,
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            props={"image-size": "not-a-dict"},
        )
        with pytest.raises(ValidationError):
            image_size(node)
