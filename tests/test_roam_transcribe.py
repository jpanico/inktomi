"""Tests for the roam_transcribe module."""

import json

import pytest
import yaml
from pydantic import ValidationError

from guffin.graph import (
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TextContentVertex,
    Vertex,
    VertexType,
    vertex_adapter,
)
from guffin.roam_network import min_effective_heading_level
from guffin.roam_node import RoamNode
from guffin.roam_transcribe import (
    to_heading_vertex,
    to_image_vertex,
    to_page_vertex,
    to_text_content_vertex,
    transcribe,
    transcribe_node,
    vertex_type,
)
from guffin.roam_primitives import Id, IdObject

# A real Firestore URL whose path yields a predictable file_name and media_type:
#   file_name  = "photo.jpeg"
#   media_type = "image/jpeg"
_FIRESTORE_URL = (
    "https://firebasestorage.googleapis.com/v0/b/test.appspot.com" "/o/imgs%2Fphoto.jpeg?alt=media&token=abc123"
)
_IMAGE_STRING = f"![A flower]({_FIRESTORE_URL})"

from conftest import FIXTURES_JSON_DIR, FIXTURES_YAML_DIR, STUB_TIME, STUB_USER, article1_node_tree

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


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


def _make_heading(
    uid: str = "headuid01",
    id: int = 102,
    string: str = "Chapter One",
    heading: int = 2,
) -> RoamNode:
    """Return a minimal native-heading RoamNode."""
    return RoamNode(
        uid=uid,
        id=id,
        time=STUB_TIME,
        user=STUB_USER,
        string=string,
        heading=heading,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_ah_heading(
    uid: str = "ahheaduid",
    id: int = 103,
    string: str = "Deep Heading",
    level: str = "h4",
) -> RoamNode:
    """Return a minimal Augmented Headings RoamNode."""
    return RoamNode(
        uid=uid,
        id=id,
        time=STUB_TIME,
        user=STUB_USER,
        string=string,
        props={"ah-level": level},
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_text(
    uid: str = "textuid01",
    id: int = 104,
    string: str = "Some plain text",
) -> RoamNode:
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


def _id_map(*nodes: RoamNode) -> dict[Id, RoamNode]:
    """Build an id_map from a sequence of nodes."""
    return {n.id: n for n in nodes}


# ---------------------------------------------------------------------------
# TestVertexType
# ---------------------------------------------------------------------------


class TestVertexType:
    """Tests for vertex_type."""

    def test_page_node_returns_roam_page(self) -> None:
        """Test that a page node classifies as ROAM_PAGE."""
        assert vertex_type(_make_page()) is VertexType.ROAM_PAGE

    def test_image_node_returns_roam_image(self) -> None:
        """Test that an image block node classifies as ROAM_IMAGE."""
        assert vertex_type(_make_image()) is VertexType.ROAM_IMAGE

    def test_native_heading_node_returns_roam_heading(self) -> None:
        """Test that a native heading block node classifies as ROAM_HEADING."""
        assert vertex_type(_make_heading()) is VertexType.ROAM_HEADING

    def test_ah_level_heading_node_returns_roam_heading(self) -> None:
        """Test that an Augmented Headings block node classifies as ROAM_HEADING."""
        assert vertex_type(_make_ah_heading()) is VertexType.ROAM_HEADING

    def test_plain_text_node_returns_roam_text_content(self) -> None:
        """Test that a plain text block node classifies as ROAM_TEXT_CONTENT."""
        assert vertex_type(_make_text()) is VertexType.ROAM_TEXT_CONTENT

    def test_node_with_neither_title_nor_string_raises_validation_error(self) -> None:
        """Test that constructing a node missing both title and string raises ValidationError."""
        with pytest.raises(ValidationError):
            RoamNode(uid="badnode01", id=999, time=STUB_TIME, user=STUB_USER)

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None raises a ValidationError."""
        with pytest.raises(ValidationError):
            vertex_type(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestToPageVertex
# ---------------------------------------------------------------------------


class TestToPageVertex:
    """Tests for to_page_vertex."""

    def test_returns_roam_page_vertex_type(self) -> None:
        """Test that to_page_vertex produces a vertex with type ROAM_PAGE."""
        node = _make_page()
        assert to_page_vertex(node, _id_map(node)).vertex_type is VertexType.ROAM_PAGE

    def test_uid_preserved(self) -> None:
        """Test that the vertex uid matches the source node uid."""
        node = _make_page(uid="pageuid01")
        assert to_page_vertex(node, _id_map(node)).uid == "pageuid01"

    def test_title_equals_node_title(self) -> None:
        """Test that the vertex title equals the source node's title."""
        node = _make_page(title="Section 1")
        assert to_page_vertex(node, _id_map(node)).title == "Section 1"

    def test_children_none_when_no_children(self) -> None:
        """Test that children is None when the node has no children."""
        node = _make_page()
        assert to_page_vertex(node, _id_map(node)).children is None

    def test_children_resolved_and_ordered_by_order_field(self) -> None:
        """Test that children are resolved from id_map and sorted ascending by their order field."""
        child1 = RoamNode(
            uid="child0001",
            id=201,
            time=STUB_TIME,
            user=STUB_USER,
            string="c1",
            order=1,
            parents=[IdObject(id=100)],
            page=IdObject(id=100),
        )
        child2 = RoamNode(
            uid="child0002",
            id=202,
            time=STUB_TIME,
            user=STUB_USER,
            string="c2",
            order=0,
            parents=[IdObject(id=100)],
            page=IdObject(id=100),
        )
        page = RoamNode(
            uid="pageuid01",
            id=100,
            time=STUB_TIME,
            user=STUB_USER,
            title="My Page",
            children=[IdObject(id=201), IdObject(id=202)],
        )
        v = to_page_vertex(page, _id_map(page, child1, child2))
        assert v.children == ["child0002", "child0001"]

    def test_child_absent_from_id_map_is_silently_dropped(self) -> None:
        """Test that child stubs whose id is absent from id_map are dropped and children returns None."""
        page = RoamNode(
            uid="pageuid01",
            id=100,
            time=STUB_TIME,
            user=STUB_USER,
            title="My Page",
            children=[IdObject(id=999)],
        )
        assert to_page_vertex(page, _id_map(page)).children is None

    def test_refs_none_when_no_refs(self) -> None:
        """Test that refs is None when the node has no refs."""
        node = _make_page()
        assert to_page_vertex(node, _id_map(node)).refs is None

    def test_refs_resolved_to_uids(self) -> None:
        """Test that ref stubs are resolved to UIDs via id_map."""
        ref_node = _make_text(uid="refnode01", id=301)
        page = RoamNode(
            uid="pageuid01",
            id=100,
            time=STUB_TIME,
            user=STUB_USER,
            title="My Page",
            children=[],
            refs=[IdObject(id=301)],
        )
        v = to_page_vertex(page, _id_map(page, ref_node))
        assert v.refs == ["refnode01"]

    def test_missing_title_raises_value_error(self) -> None:
        """Test that a node without a title raises ValueError."""
        node = _make_text()
        with pytest.raises(ValueError, match="no 'title'"):
            to_page_vertex(node, _id_map(node))

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            to_page_vertex(None, _id_map())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestToImageVertex
# ---------------------------------------------------------------------------


class TestToImageVertex:
    """Tests for to_image_vertex."""

    def test_returns_roam_image_vertex_type(self) -> None:
        """Test that to_image_vertex produces a vertex with type ROAM_IMAGE."""
        node = _make_image()
        assert to_image_vertex(node, _id_map(node)).vertex_type is VertexType.ROAM_IMAGE

    def test_uid_preserved(self) -> None:
        """Test that the vertex uid matches the source node uid."""
        node = _make_image(uid="imageuid1")
        assert to_image_vertex(node, _id_map(node)).uid == "imageuid1"

    def test_source_host_is_firestore(self) -> None:
        """Test that the vertex source URL points to the Firestore host."""
        v = to_image_vertex(_make_image(), _id_map(_make_image()))
        assert v.source.host == "firebasestorage.googleapis.com"

    def test_alt_text_extracted_from_string(self) -> None:
        """Test that alt text is extracted and stripped from the Markdown image link."""
        node = _make_image(string=f"![My Photo]({_FIRESTORE_URL})")
        assert to_image_vertex(node, _id_map(node)).alt_text == "My Photo"

    def test_alt_text_stripped_of_whitespace(self) -> None:
        """Test that leading/trailing whitespace (including newlines) is stripped from alt text."""
        node = _make_image(string=f"![A flower\n        ]({_FIRESTORE_URL})")
        assert to_image_vertex(node, _id_map(node)).alt_text == "A flower"

    def test_alt_text_none_when_empty(self) -> None:
        """Test that empty alt text produces None rather than an empty string."""
        node = _make_image(string=f"![]({_FIRESTORE_URL})")
        assert to_image_vertex(node, _id_map(node)).alt_text is None

    def test_file_name_extracted_from_url(self) -> None:
        """Test that the filename is percent-decoded from the Firestore URL path."""
        assert to_image_vertex(_make_image(), _id_map(_make_image())).file_name == "photo.jpeg"

    def test_media_type_inferred_from_file_name(self) -> None:
        """Test that the IANA media type is inferred from the extracted filename extension."""
        assert to_image_vertex(_make_image(), _id_map(_make_image())).media_type == "image/jpeg"

    def test_children_none_when_no_children(self) -> None:
        """Test that children is None when the image node has no children."""
        node = _make_image()
        assert to_image_vertex(node, _id_map(node)).children is None

    def test_missing_string_raises_value_error(self) -> None:
        """Test that a node without a string raises ValueError."""
        node = _make_page()
        with pytest.raises(ValueError, match="no 'string'"):
            to_image_vertex(node, _id_map(node))

    def test_non_firestore_url_raises_value_error(self) -> None:
        """Test that a string with a non-Firestore https URL raises ValueError."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            time=STUB_TIME,
            user=STUB_USER,
            string="![alt](https://example.com/image.jpg)",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        with pytest.raises(ValueError, match="contains no Firestore URL"):
            to_image_vertex(node, _id_map(node))

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            to_image_vertex(None, _id_map())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestToHeadingVertex
# ---------------------------------------------------------------------------


class TestToHeadingVertex:
    """Tests for to_heading_vertex."""

    def test_returns_roam_heading_vertex_type(self) -> None:
        """Test that to_heading_vertex produces a vertex with type ROAM_HEADING."""
        node = _make_heading()
        assert to_heading_vertex(node, _id_map(node)).vertex_type is VertexType.ROAM_HEADING

    def test_uid_preserved(self) -> None:
        """Test that the vertex uid matches the source node uid."""
        node = _make_heading(uid="headuid01")
        assert to_heading_vertex(node, _id_map(node)).uid == "headuid01"

    def test_text_equals_string(self) -> None:
        """Test that the vertex text equals the node's block string."""
        node = _make_heading(string="Introduction")
        assert to_heading_vertex(node, _id_map(node)).text == "Introduction"

    def test_native_heading_levels_preserved(self) -> None:
        """Test that native heading levels 1–3 are preserved in the vertex."""
        for level in (1, 2, 3):
            node = _make_heading(heading=level)
            assert to_heading_vertex(node, _id_map(node)).heading == level

    def test_ah_level_heading_levels_resolved(self) -> None:
        """Test that Augmented Headings levels h4–h6 are resolved to integers 4–6."""
        for level_str, expected in (("h4", 4), ("h5", 5), ("h6", 6)):
            node = _make_ah_heading(level=level_str)
            assert to_heading_vertex(node, _id_map(node)).heading == expected

    def test_children_none_when_no_children(self) -> None:
        """Test that children is None when the heading node has no children."""
        node = _make_heading()
        assert to_heading_vertex(node, _id_map(node)).children is None

    def test_missing_string_raises_value_error(self) -> None:
        """Test that a node without a string raises ValueError."""
        node = _make_page()
        with pytest.raises(ValueError, match="no 'string'"):
            to_heading_vertex(node, _id_map(node))

    def test_no_heading_raises_value_error(self) -> None:
        """Test that a node with no effective heading level raises ValueError."""
        node = _make_text()
        with pytest.raises(ValueError, match="no effective heading level"):
            to_heading_vertex(node, _id_map(node))

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            to_heading_vertex(None, _id_map())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestToTextContentVertex
# ---------------------------------------------------------------------------


class TestToTextContentVertex:
    """Tests for to_text_content_vertex."""

    def test_returns_roam_text_content_vertex_type(self) -> None:
        """Test that to_text_content_vertex produces a vertex with type ROAM_TEXT_CONTENT."""
        node = _make_text()
        assert to_text_content_vertex(node, _id_map(node)).vertex_type is VertexType.ROAM_TEXT_CONTENT

    def test_uid_preserved(self) -> None:
        """Test that the vertex uid matches the source node uid."""
        node = _make_text(uid="textuid01")
        assert to_text_content_vertex(node, _id_map(node)).uid == "textuid01"

    def test_text_equals_string(self) -> None:
        """Test that the vertex text equals the node's block string."""
        node = _make_text(string="Hello, world!")
        assert to_text_content_vertex(node, _id_map(node)).text == "Hello, world!"

    def test_children_none_when_no_children(self) -> None:
        """Test that children is None when the node has no children."""
        node = _make_text()
        assert to_text_content_vertex(node, _id_map(node)).children is None

    def test_refs_none_when_no_refs(self) -> None:
        """Test that refs is None when the node has no refs."""
        node = _make_text()
        assert to_text_content_vertex(node, _id_map(node)).refs is None

    def test_missing_string_raises_value_error(self) -> None:
        """Test that a node without a string raises ValueError."""
        node = _make_page()
        with pytest.raises(ValueError, match="no 'string'"):
            to_text_content_vertex(node, _id_map(node))

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            to_text_content_vertex(None, _id_map())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestTranscribeNode
# ---------------------------------------------------------------------------


class TestTranscribeNode:
    """Integration tests for transcribe_node — verifies correct dispatch to each vertex builder."""

    def test_transcribes_page_node(self) -> None:
        """Test that a page node is transcribed to a ROAM_PAGE vertex with correct fields."""
        node = _make_page(title="My Page")
        v = transcribe_node(node, _id_map(node))
        assert isinstance(v, PageVertex)
        assert v.vertex_type is VertexType.ROAM_PAGE
        assert v.title == "My Page"

    def test_transcribes_image_node(self) -> None:
        """Test that an image block node is transcribed to a ROAM_IMAGE vertex with correct fields."""
        node = _make_image()
        v = transcribe_node(node, _id_map(node))
        assert isinstance(v, ImageVertex)
        assert v.vertex_type is VertexType.ROAM_IMAGE
        assert v.file_name == "photo.jpeg"
        assert v.media_type == "image/jpeg"

    def test_transcribes_heading_node(self) -> None:
        """Test that a heading block node is transcribed to a ROAM_HEADING vertex with correct fields."""
        node = _make_heading(string="Intro", heading=1)
        v = transcribe_node(node, _id_map(node))
        assert isinstance(v, HeadingVertex)
        assert v.vertex_type is VertexType.ROAM_HEADING
        assert v.text == "Intro"
        assert v.heading == 1

    def test_transcribes_text_content_node(self) -> None:
        """Test that a plain text block node is transcribed to a ROAM_TEXT_CONTENT vertex."""
        node = _make_text(string="Body text")
        v = transcribe_node(node, _id_map(node))
        assert isinstance(v, TextContentVertex)
        assert v.vertex_type is VertexType.ROAM_TEXT_CONTENT
        assert v.text == "Body text"

    def test_children_resolved_via_id_map(self) -> None:
        """Test that transcribe_node resolves children through the id_map."""
        child = RoamNode(
            uid="child0001",
            id=201,
            time=STUB_TIME,
            user=STUB_USER,
            string="child",
            order=0,
            parents=[IdObject(id=100)],
            page=IdObject(id=100),
        )
        page = RoamNode(
            uid="pageuid01",
            id=100,
            time=STUB_TIME,
            user=STUB_USER,
            title="Page",
            children=[IdObject(id=201)],
        )
        v = transcribe_node(page, _id_map(page, child))
        assert isinstance(v, PageVertex)
        assert v.children == ["child0001"]

    def test_node_with_neither_title_nor_string_raises_validation_error(self) -> None:
        """Test that constructing a node missing both title and string raises ValidationError."""
        with pytest.raises(ValidationError):
            RoamNode(uid="badnode01", id=999, time=STUB_TIME, user=STUB_USER)

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            transcribe_node(None, _id_map())  # type: ignore[arg-type]

    def test_transcribes_image_node_from_fixture(self) -> None:
        """Test transcription of a real-world image node loaded from the JSON fixture."""
        raw = json.loads((FIXTURES_JSON_DIR / "image_node.json").read_text())[0]
        node = RoamNode.model_validate(raw)
        v = transcribe_node(node, _id_map(node))
        assert isinstance(v, ImageVertex)
        assert v.vertex_type is VertexType.ROAM_IMAGE
        assert v.uid == "mPCzedeKx"
        assert v.source.host == "firebasestorage.googleapis.com"
        assert v.alt_text == "A flower"
        assert v.file_name == "-9owRBegJ8.jpeg.enc"


# ---------------------------------------------------------------------------
# TestTranscribeArticleFixture
# ---------------------------------------------------------------------------


class TestTranscribeArticleFixture:
    """End-to-end fixture test: transcribe the Test Article NodeNetwork and compare to the vertex fixture."""

    def test_transcribe_article_nodes_matches_vertex_fixture(self) -> None:
        """Test that transcribing test_article_1_nodes.yaml produces the vertices in test_article_1_vertices.yaml."""
        node_tree = article1_node_tree()
        nodes = list(node_tree.tree_network)
        id_map: dict[Id, RoamNode] = {n.id: n for n in nodes}
        min_level = min_effective_heading_level(node_tree.tree_network)
        heading_offset: int = (1 - min_level) if min_level is not None else 0

        actual_vertices: list[Vertex] = [transcribe_node(n, id_map, heading_offset) for n in nodes]

        raw_vertices: list[dict[str, object]] = yaml.safe_load(
            (FIXTURES_YAML_DIR / "test_article_1_vertices.yaml").read_text()
        )
        expected_vertices: list[Vertex] = [vertex_adapter.validate_python(r) for r in raw_vertices]

        # Serialize both sides to plain dicts (mode='json' converts HttpUrl → str,
        # StrEnum → str) and sort by uid so the comparison is order-independent.
        def _as_dict(v: Vertex) -> dict[str, object]:
            return v.model_dump(mode="json", exclude_none=True)

        actual_by_uid = {d["uid"]: d for d in (_as_dict(v) for v in actual_vertices)}
        expected_by_uid = {d["uid"]: d for d in (_as_dict(v) for v in expected_vertices)}

        assert actual_by_uid == expected_by_uid

    def test_article_node_tree_transcribes_to_vertex_tree(self) -> None:
        """Transcribing the Test Article NodeTree via transcribe() produces the expected VertexTree."""
        node_tree = article1_node_tree()

        vertex_tree = transcribe(node_tree)

        raw_vertices: list[dict[str, object]] = yaml.safe_load(
            (FIXTURES_YAML_DIR / "test_article_1_vertices.yaml").read_text()
        )
        expected: list[Vertex] = [vertex_adapter.validate_python(r) for r in raw_vertices]

        def _serialise(v: Vertex) -> dict[str, object]:
            return v.model_dump(mode="json", exclude_none=True)

        assert [_serialise(v) for v in vertex_tree.vertices] == [_serialise(v) for v in expected]
