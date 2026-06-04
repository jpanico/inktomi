"""Unit tests for guffin.pdf_rendering."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false
# Rationale: panflute has no type stubs; all five rules are triggered entirely by
# Unknown propagation from that import — suppressing them here avoids false positives.

from pathlib import Path

import panflute as pf  # type: ignore[import-untyped]
from pydantic import HttpUrl

from guffin.graph import (
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TextContentVertex,
    VertexTree,
)
from guffin.pdf_rendering import (
    build_blocks,
    vertex_tree_to_pandoc,
)
from conftest import article0_vertex_tree

_IMAGE_URL: HttpUrl = HttpUrl("https://example.com/imgs/photo.jpeg")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _str_text(inline: pf.Inline) -> str:
    """Return the text of a panflute Str inline element."""
    assert isinstance(inline, pf.Str)
    return inline.text


def _first_inline_text(block: pf.Block) -> str:
    """Return the text of the first Str in the first inline of a block."""
    return _str_text(list(block.content)[0])


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocPageVertex
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocPageVertex:
    """Tests for vertex_tree_to_pandoc() — PageVertex root behaviour."""

    def test_page_title_set_in_metadata(self) -> None:
        """Page title appears as the Pandoc metadata title."""
        tree = VertexTree(vertices=[PageVertex(uid="page00001", title="My Page")])
        doc = vertex_tree_to_pandoc(tree, {})
        assert "title" in doc.metadata
        title_inlines = list(doc.metadata["title"].content)
        assert len(title_inlines) == 1
        assert _str_text(title_inlines[0]) == "My Page"

    def test_page_with_no_children_produces_no_blocks(self) -> None:
        """A bare PageVertex with no children produces an empty document body."""
        tree = VertexTree(vertices=[PageVertex(uid="page00001", title="Empty")])
        doc = vertex_tree_to_pandoc(tree, {})
        assert list(doc.content) == []

    def test_non_page_root_produces_no_metadata_title(self) -> None:
        """When the root is not a PageVertex, no metadata title is set."""
        tree = VertexTree(vertices=[HeadingVertex(uid="head00001", text="Intro", heading=1)])
        doc = vertex_tree_to_pandoc(tree, {})
        assert "title" not in doc.metadata


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocHeadingVertex
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocHeadingVertex:
    """Tests for vertex_tree_to_pandoc() — HeadingVertex rendering."""

    def test_heading_level_preserved(self) -> None:
        """HeadingVertex produces a Header block at the recorded heading level."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Section 1", heading=2)
        tree = VertexTree(vertices=[page, heading])
        blocks = list(vertex_tree_to_pandoc(tree, {}).content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Header)
        assert blocks[0].level == 2
        assert _first_inline_text(blocks[0]) == "Section 1"

    def test_h3_heading(self) -> None:
        """HeadingVertex at level 3 produces an H3 Header."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Subsection", heading=3)
        tree = VertexTree(vertices=[page, heading])
        blocks = list(vertex_tree_to_pandoc(tree, {}).content)
        assert isinstance(blocks[0], pf.Header)
        assert blocks[0].level == 3

    def test_h4_through_h6(self) -> None:
        """HeadingVertices at levels 4, 5, 6 produce Headers at the correct levels."""
        page = PageVertex(uid="page00001", title="P", children=["head0004a", "head0005a", "head0006a"])
        h4 = HeadingVertex(uid="head0004a", text="H4", heading=4)
        h5 = HeadingVertex(uid="head0005a", text="H5", heading=5)
        h6 = HeadingVertex(uid="head0006a", text="H6", heading=6)
        tree = VertexTree(vertices=[page, h4, h5, h6])
        blocks = list(vertex_tree_to_pandoc(tree, {}).content)
        assert [b.level for b in blocks] == [4, 5, 6]

    def test_nested_headings_flattened_into_document(self) -> None:
        """Children of a HeadingVertex are rendered as sibling blocks, not nested."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        h2 = HeadingVertex(uid="head0001a", text="Chapter", heading=2, children=["head0001b"])
        h3 = HeadingVertex(uid="head0001b", text="Section", heading=3)
        tree = VertexTree(vertices=[page, h2, h3])
        blocks = list(vertex_tree_to_pandoc(tree, {}).content)
        assert len(blocks) == 2
        assert isinstance(blocks[0], pf.Header)
        assert blocks[0].level == 2
        assert isinstance(blocks[1], pf.Header)
        assert blocks[1].level == 3


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocTextContentVertex
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocTextContentVertex:
    """Tests for vertex_tree_to_pandoc() — TextContentVertex rendering."""

    def test_depth_1_is_para(self) -> None:
        """A TextContentVertex that is a direct child of the page renders as a Para."""
        page = PageVertex(uid="page00001", title="P", children=["txt00001a"])
        block = TextContentVertex(uid="txt00001a", text="Hello world")
        tree = VertexTree(vertices=[page, block])
        blocks = list(vertex_tree_to_pandoc(tree, {}).content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Para)
        assert _first_inline_text(blocks[0]) == "Hello world"

    def test_depth_2_text_under_heading_is_bullet(self) -> None:
        """A TextContentVertex under a HeadingVertex (depth 2) renders as a BulletList."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Section", heading=2, children=["txt00001a"])
        block = TextContentVertex(uid="txt00001a", text="Body text")
        tree = VertexTree(vertices=[page, heading, block])
        blocks = list(vertex_tree_to_pandoc(tree, {}).content)
        # blocks: [Header, BulletList]
        assert len(blocks) == 2
        assert isinstance(blocks[1], pf.BulletList)
        items = list(blocks[1].content)
        assert len(items) == 1
        assert isinstance(items[0], pf.ListItem)
        item_blocks = list(items[0].content)
        assert isinstance(item_blocks[0], pf.Plain)
        assert _first_inline_text(item_blocks[0]) == "Body text"

    def test_nested_text_produces_nested_bullet_list(self) -> None:
        """A TextContentVertex child of another TextContentVertex renders as a nested BulletList."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="S", heading=2, children=["txt00001a"])
        parent = TextContentVertex(uid="txt00001a", text="Parent", children=["txt00001b"])
        child = TextContentVertex(uid="txt00001b", text="Child")
        tree = VertexTree(vertices=[page, heading, parent, child])
        blocks = list(vertex_tree_to_pandoc(tree, {}).content)
        bullet_list = blocks[1]
        assert isinstance(bullet_list, pf.BulletList)
        parent_item = list(bullet_list.content)[0]
        parent_item_blocks = list(parent_item.content)
        # [Plain("Parent"), BulletList([ListItem(Plain("Child"))])]
        assert len(parent_item_blocks) == 2
        nested_list = parent_item_blocks[1]
        assert isinstance(nested_list, pf.BulletList)
        child_item = list(nested_list.content)[0]
        assert _first_inline_text(list(child_item.content)[0]) == "Child"


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocImageVertex
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocImageVertex:
    """Tests for vertex_tree_to_pandoc() — ImageVertex rendering."""

    def test_fetched_image_is_embedded(self, tmp_path: Path) -> None:
        """When image_files has an entry for the vertex, a pf.Image is used."""
        fake_img = tmp_path / "photo.jpg"
        fake_img.write_bytes(b"")
        page = PageVertex(uid="page00001", title="P", children=["img00001a"])
        image = ImageVertex(uid="img00001a", source=_IMAGE_URL, alt_text="A flower")
        tree = VertexTree(vertices=[page, image])
        doc = vertex_tree_to_pandoc(tree, {"img00001a": fake_img})
        blocks = list(doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Para)
        inline = list(blocks[0].content)[0]
        assert isinstance(inline, pf.Image)
        assert inline.url == str(fake_img)

    def test_unfetched_image_falls_back_to_link(self) -> None:
        """When image_files has no entry for the vertex, a pf.Link is used."""
        page = PageVertex(uid="page00001", title="P", children=["img00001a"])
        image = ImageVertex(uid="img00001a", source=_IMAGE_URL, alt_text="A flower")
        tree = VertexTree(vertices=[page, image])
        doc = vertex_tree_to_pandoc(tree, {})
        blocks = list(doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Para)
        inline = list(blocks[0].content)[0]
        assert isinstance(inline, pf.Link)
        assert inline.url == str(_IMAGE_URL)

    def test_unfetched_image_link_label_uses_alt_text(self) -> None:
        """The fallback link label uses alt_text when present."""
        page = PageVertex(uid="page00001", title="P", children=["img00001a"])
        image = ImageVertex(uid="img00001a", source=_IMAGE_URL, alt_text="A flower")
        tree = VertexTree(vertices=[page, image])
        doc = vertex_tree_to_pandoc(tree, {})
        inline = list(list(doc.content)[0].content)[0]
        assert isinstance(inline, pf.Link)
        assert _str_text(list(inline.content)[0]) == "A flower"

    def test_unfetched_image_link_label_falls_back_to_file_name(self) -> None:
        """The fallback link label uses file_name when alt_text is absent."""
        page = PageVertex(uid="page00001", title="P", children=["img00001a"])
        image = ImageVertex(uid="img00001a", source=_IMAGE_URL, file_name="photo.jpg")
        tree = VertexTree(vertices=[page, image])
        doc = vertex_tree_to_pandoc(tree, {})
        inline = list(list(doc.content)[0].content)[0]
        assert isinstance(inline, pf.Link)
        assert _str_text(list(inline.content)[0]) == "photo.jpg"


# ---------------------------------------------------------------------------
# TestBuildBlocksCoalescing
# ---------------------------------------------------------------------------


class TestBuildBlocksCoalescing:
    """Tests for build_blocks() — sibling TextContentVertex coalescing."""

    def test_consecutive_text_siblings_coalesced_into_one_bullet_list(self) -> None:
        """Two consecutive TextContentVertex siblings at depth 2 produce a single BulletList."""
        t1 = TextContentVertex(uid="txt000001", text="Item 1")
        t2 = TextContentVertex(uid="txt000002", text="Item 2")
        uid_map = {"txt000001": t1, "txt000002": t2}
        blocks = build_blocks(["txt000001", "txt000002"], uid_map, {}, depth=2)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.BulletList)
        assert len(list(blocks[0].content)) == 2

    def test_heading_between_text_siblings_splits_bullet_lists(self) -> None:
        """A HeadingVertex between two TextContentVertices produces two separate BulletLists."""
        t1 = TextContentVertex(uid="txt000001", text="Before")
        h = HeadingVertex(uid="head00001", text="Break", heading=3)
        t2 = TextContentVertex(uid="txt000002", text="After")
        uid_map = {"txt000001": t1, "head00001": h, "txt000002": t2}
        blocks = build_blocks(["txt000001", "head00001", "txt000002"], uid_map, {}, depth=2)
        # [BulletList([Before]), Header, BulletList([After])]
        assert len(blocks) == 3
        assert isinstance(blocks[0], pf.BulletList)
        assert isinstance(blocks[1], pf.Header)
        assert isinstance(blocks[2], pf.BulletList)

    def test_text_at_depth_1_is_not_coalesced_into_bullet_list(self) -> None:
        """TextContentVertices at depth 1 render as Paras, not BulletList items."""
        t1 = TextContentVertex(uid="txt000001", text="Para 1")
        t2 = TextContentVertex(uid="txt000002", text="Para 2")
        uid_map = {"txt000001": t1, "txt000002": t2}
        blocks = build_blocks(["txt000001", "txt000002"], uid_map, {}, depth=1)
        assert len(blocks) == 2
        assert all(isinstance(b, pf.Para) for b in blocks)

    def test_unknown_uid_is_skipped(self) -> None:
        """A UID not in uid_map is silently skipped."""
        t1 = TextContentVertex(uid="txt000001", text="Present")
        uid_map = {"txt000001": t1}
        blocks = build_blocks(["missingXY", "txt000001"], uid_map, {}, depth=1)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Para)


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocArticleFixture
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocArticleFixture:
    """Integration test for vertex_tree_to_pandoc() using the Test Article 0 fixture."""

    def test_metadata_title_is_test_article_0(self) -> None:
        """Doc metadata title matches the page title from the fixture."""
        doc = vertex_tree_to_pandoc(article0_vertex_tree(), {})
        title_inlines = list(doc.metadata["title"].content)
        assert _str_text(title_inlines[0]) == "Test Article 0"

    def test_block_count(self) -> None:
        """The fixture produces the expected number of top-level blocks."""
        doc = vertex_tree_to_pandoc(article0_vertex_tree(), {})
        # 3 H2s + 3 H3s + 2 H4s + 1 H5 + 1 Para(Link) + 1 BulletList = 12
        assert len(list(doc.content)) == 12

    def test_first_block_is_section_1_header(self) -> None:
        """The first block is an H2 Header for 'Section 1'."""
        doc = vertex_tree_to_pandoc(article0_vertex_tree(), {})
        first = list(doc.content)[0]
        assert isinstance(first, pf.Header)
        assert first.level == 2
        assert _first_inline_text(first) == "Section 1"

    def test_image_renders_as_fallback_link_when_no_image_files(self) -> None:
        """The ImageVertex in the fixture renders as a pf.Link when image_files is empty."""
        doc = vertex_tree_to_pandoc(article0_vertex_tree(), {})
        blocks = list(doc.content)
        image_para = next(
            (b for b in blocks if isinstance(b, pf.Para) and isinstance(list(b.content)[0], pf.Link)), None
        )
        assert image_para is not None

    def test_text_content_vertex_renders_as_bullet_list(self) -> None:
        """The TextContentVertex ('AI assistant') renders as a BulletList."""
        doc = vertex_tree_to_pandoc(article0_vertex_tree(), {})
        blocks = list(doc.content)
        bullet_lists = [b for b in blocks if isinstance(b, pf.BulletList)]
        assert len(bullet_lists) == 1
        items = list(bullet_lists[0].content)
        assert len(items) == 1
        assert _first_inline_text(list(items[0].content)[0]) == "AI assistant (Claude Opus 4.6): "
