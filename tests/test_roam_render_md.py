"""Unit tests for guffin.md_rendering."""

from pydantic import HttpUrl

from guffin.graph import (
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TextContentVertex,
    VertexTree,
)
from guffin.md_rendering import render

from conftest import FIXTURES_MD_DIR, article0_vertex_tree

_IMAGE_URL: HttpUrl = HttpUrl("https://example.com/imgs/photo.jpeg")


class TestRenderPageOnly:
    """Tests for render() with a page vertex and no children."""

    def test_page_only_produces_h1(self) -> None:
        """Test that a bare page with no children renders as a lone H1."""
        tree = VertexTree(vertices=[PageVertex(uid="page00001", title="My Page")])
        assert render(tree) == "# My Page\n"

    def test_page_title_used_verbatim(self) -> None:
        """Test that the page title is used as-is in the H1 line."""
        tree = VertexTree(vertices=[PageVertex(uid="page00001", title="Hello, World!")])
        assert render(tree) == "# Hello, World!\n"

    def test_output_ends_with_single_newline(self) -> None:
        """Test that the output always ends with exactly one trailing newline."""
        tree = VertexTree(vertices=[PageVertex(uid="page00001", title="My Page")])
        result = render(tree)
        assert result.endswith("\n")
        assert not result.endswith("\n\n")


class TestRenderTextContent:
    """Tests for render() with TextContentVertex nodes at various depths."""

    def test_direct_child_of_page_is_paragraph(self) -> None:
        """Test that a depth-1 TextContentVertex is rendered as a paragraph."""
        page = PageVertex(uid="page00001", title="My Page", children=["txt00001a"])
        block = TextContentVertex(uid="txt00001a", text="Hello world")
        tree = VertexTree(vertices=[page, block])
        assert render(tree) == "# My Page\n\nHello world\n"

    def test_multiple_direct_children_are_separate_paragraphs(self) -> None:
        """Test that multiple depth-1 TextContentVertices each become their own paragraph."""
        page = PageVertex(uid="page00001", title="My Page", children=["txt00001a", "txt00001b"])
        block_a = TextContentVertex(uid="txt00001a", text="First")
        block_b = TextContentVertex(uid="txt00001b", text="Second")
        tree = VertexTree(vertices=[page, block_a, block_b])
        assert render(tree) == "# My Page\n\nFirst\n\nSecond\n"

    def test_nested_text_content_becomes_bullet(self) -> None:
        """Test that a depth-2 TextContentVertex is rendered as a bullet list item."""
        page = PageVertex(uid="page00001", title="My Page", children=["txt00001a"])
        parent = TextContentVertex(uid="txt00001a", text="Parent", children=["txt00001b"])
        child = TextContentVertex(uid="txt00001b", text="Child")
        tree = VertexTree(vertices=[page, parent, child])
        assert render(tree) == "# My Page\n\nParent\n\n- Child\n"

    def test_depth_3_text_content_is_indented_bullet(self) -> None:
        """Test that a depth-3 TextContentVertex is rendered with one level of indentation."""
        page = PageVertex(uid="page00001", title="My Page", children=["txt00001a"])
        depth1 = TextContentVertex(uid="txt00001a", text="Depth 1", children=["txt00001b"])
        depth2 = TextContentVertex(uid="txt00001b", text="Depth 2", children=["txt00001c"])
        depth3 = TextContentVertex(uid="txt00001c", text="Depth 3")
        tree = VertexTree(vertices=[page, depth1, depth2, depth3])
        assert render(tree) == "# My Page\n\nDepth 1\n\n- Depth 2\n  - Depth 3\n"

    def test_depth_4_text_content_is_double_indented_bullet(self) -> None:
        """Test that a depth-4 TextContentVertex is rendered with two levels of indentation."""
        page = PageVertex(uid="page00001", title="My Page", children=["txt00001a"])
        d1 = TextContentVertex(uid="txt00001a", text="D1", children=["txt00001b"])
        d2 = TextContentVertex(uid="txt00001b", text="D2", children=["txt00001c"])
        d3 = TextContentVertex(uid="txt00001c", text="D3", children=["txt00001d"])
        d4 = TextContentVertex(uid="txt00001d", text="D4")
        tree = VertexTree(vertices=[page, d1, d2, d3, d4])
        assert render(tree) == "# My Page\n\nD1\n\n- D2\n  - D3\n    - D4\n"


class TestRenderHeadings:
    """Tests for render() with HeadingVertex nodes."""

    def test_h2_heading(self) -> None:
        """Test that an H2 HeadingVertex renders as a ## heading."""
        page = PageVertex(uid="page00001", title="My Page", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Section 1", heading=2)
        tree = VertexTree(vertices=[page, heading])
        assert render(tree) == "# My Page\n\n## Section 1\n"

    def test_h3_heading(self) -> None:
        """Test that an H3 HeadingVertex renders as a ### heading."""
        page = PageVertex(uid="page00001", title="My Page", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Subsection", heading=3)
        tree = VertexTree(vertices=[page, heading])
        assert render(tree) == "# My Page\n\n### Subsection\n"

    def test_h4_through_h6(self) -> None:
        """Test that H4, H5, and H6 HeadingVertices render with the correct number of hashes."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a", "head0001b", "head0001c"])
        h4 = HeadingVertex(uid="head0001a", text="H4", heading=4)
        h5 = HeadingVertex(uid="head0001b", text="H5", heading=5)
        h6 = HeadingVertex(uid="head0001c", text="H6", heading=6)
        tree = VertexTree(vertices=[page, h4, h5, h6])
        assert render(tree) == "# P\n\n#### H4\n\n##### H5\n\n###### H6\n"

    def test_heading_with_text_children(self) -> None:
        """Test that a HeadingVertex with TextContentVertex children renders them as bullets."""
        page = PageVertex(uid="page00001", title="My Page", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Section 1", heading=2, children=["txt00001a"])
        block = TextContentVertex(uid="txt00001a", text="Body text")
        tree = VertexTree(vertices=[page, heading, block])
        assert render(tree) == "# My Page\n\n## Section 1\n\n- Body text\n"

    def test_nested_headings(self) -> None:
        """Test that a HeadingVertex nested inside another renders at its recorded heading level."""
        page = PageVertex(uid="page00001", title="Doc", children=["head0001a"])
        h2 = HeadingVertex(uid="head0001a", text="Chapter", heading=2, children=["head0001b"])
        h3 = HeadingVertex(uid="head0001b", text="Section", heading=3)
        tree = VertexTree(vertices=[page, h2, h3])
        assert render(tree) == "# Doc\n\n## Chapter\n\n### Section\n"


class TestRenderImages:
    """Tests for render() with ImageVertex nodes."""

    def test_image_with_alt_text(self) -> None:
        """Test that an ImageVertex with alt_text renders as ![alt](url)."""
        page = PageVertex(uid="page00001", title="My Page", children=["img00001a"])
        image = ImageVertex(uid="img00001a", source=_IMAGE_URL, alt_text="A flower")
        tree = VertexTree(vertices=[page, image])
        assert render(tree) == f"# My Page\n\n![A flower]({_IMAGE_URL})\n"

    def test_image_without_alt_text(self) -> None:
        """Test that an ImageVertex with no alt_text renders as ![](url)."""
        page = PageVertex(uid="page00001", title="My Page", children=["img00001a"])
        image = ImageVertex(uid="img00001a", source=_IMAGE_URL)
        tree = VertexTree(vertices=[page, image])
        assert render(tree) == f"# My Page\n\n![]({_IMAGE_URL})\n"


class TestRenderTestArticle:
    """Integration test for render() using the test_article_0_vertices.yaml fixture."""

    def test_article_fixture_renders_correctly(self) -> None:
        """Test that the full test_article VertexTree renders to the expected CommonMark output."""
        expected = (FIXTURES_MD_DIR / "test_article_0_expected.md").read_text()
        assert render(article0_vertex_tree()) == expected
