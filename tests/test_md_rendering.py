"""Unit tests for guffin.md_rendering."""

import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pydantic import HttpUrl, ValidationError

from guffin.graph import (
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TextContentVertex,
    VertexTree,
)
from guffin.md_rendering import (
    bundle_md_file,
    fetch_and_save_image,
    find_markdown_image_links,
    normalize_link_text,
    remove_escaped_double_brackets,
    vertex_tree_to_md as render,
    replace_image_links,
)
from guffin.roam_asset import RoamAsset
from guffin.roam_local_api import ApiEndpoint, ApiEndpointURL

from conftest import FIXTURES_MD_DIR, article0_vertex_tree

logger = logging.getLogger(__name__)

_IMAGE_URL: HttpUrl = HttpUrl("https://example.com/imgs/photo.jpeg")


# ---------------------------------------------------------------------------
# TestRenderPageOnly
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# TestRenderTextContent
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# TestRenderHeadings
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# TestRenderImages
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# TestRenderTestArticle
# ---------------------------------------------------------------------------


class TestRenderTestArticle:
    """Integration test for render() using the test_article_0_vertices.yaml fixture."""

    def test_article_fixture_renders_correctly(self) -> None:
        """Test that the full test_article VertexTree renders to the expected CommonMark output."""
        expected = (FIXTURES_MD_DIR / "test_article_0_expected.md").read_text()
        assert render(article0_vertex_tree()) == expected


# ---------------------------------------------------------------------------
# TestFindMarkdownImageLinks
# ---------------------------------------------------------------------------


class TestFindMarkdownImageLinks:
    """Tests for find_markdown_image_links()."""

    def test_finds_single_firebase_link(self) -> None:
        """Test finding a single Cloud Firestore image link."""
        url = "https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2F-9owRBegJ8.jpeg.enc?alt=media&token=abc123"
        matches = find_markdown_image_links(f"![alt text]({url})")
        assert len(matches) == 1
        assert str(matches[0][1]) == url
        assert isinstance(matches[0][1], HttpUrl)

    def test_finds_multiple_firebase_links(self) -> None:
        """Test finding multiple Cloud Firestore image links."""
        text = (
            "![i1](https://firebasestorage.googleapis.com/v0/b/test1.appspot.com/o/img1.png?token=abc)\n"
            "![i2](https://firebasestorage.googleapis.com/v0/b/test2.appspot.com/o/img2.jpg?token=def)"
        )
        matches = find_markdown_image_links(text)
        assert len(matches) == 2
        assert "img1.png" in str(matches[0][1])
        assert "img2.jpg" in str(matches[1][1])

    def test_ignores_non_firebase_links(self) -> None:
        """Test that non-Cloud Firestore URLs are ignored."""
        text = (
            "![local](./local-image.png)\n"
            "![remote](https://example.com/image.jpg)\n"
            "![fb](https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/img.png?token=abc)"
        )
        matches = find_markdown_image_links(text)
        assert len(matches) == 1
        assert "firebasestorage.googleapis.com" in str(matches[0][1])

    def test_none_markdown_raises_validation_error(self) -> None:
        """Test that None markdown_text raises ValidationError."""
        with pytest.raises(ValidationError):
            find_markdown_image_links(None)  # type: ignore[arg-type]

    def test_empty_markdown_returns_empty_list(self) -> None:
        """Test that empty markdown returns empty list."""
        assert find_markdown_image_links("") == []

    def test_markdown_without_images_returns_empty_list(self) -> None:
        """Test that markdown without images returns empty list."""
        assert find_markdown_image_links("# Heading\n\nSome text.") == []

    def test_handles_multiline_alt_text(self) -> None:
        """Test that multiline alt text is handled correctly."""
        text = "![This is\nmultiline\nalt text](https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/img.png?token=abc)"
        matches = find_markdown_image_links(text)
        assert len(matches) == 1

    def test_returns_full_match_and_url(self) -> None:
        """Test that function returns both full match and URL."""
        text = "![alt](https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/img.png?token=abc)"
        full_match, url = find_markdown_image_links(text)[0]
        assert full_match.startswith("![")
        assert full_match.endswith(")")
        assert str(url).startswith("https://firebasestorage.googleapis.com")


# ---------------------------------------------------------------------------
# TestFetchAndSaveImage
# ---------------------------------------------------------------------------


class TestFetchAndSaveImage:
    """Tests for fetch_and_save_image()."""

    @patch("guffin.md_rendering.fetch_and_cache_asset")
    def test_fetches_and_saves_image_successfully(self, mock_fetch_cache: Mock, tmp_path: Path) -> None:
        """Test successful image fetch and save."""
        api_endpoint = ApiEndpoint(
            url=ApiEndpointURL(local_api_port=3333, graph_name="test-graph"),
            bearer_token="test-token",
        )
        firebase_url = HttpUrl("https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/img.png?token=abc")
        mock_fetch_cache.return_value = RoamAsset(
            file_name="abc123.png",
            last_modified=datetime.now(),
            media_type="image/png",
            contents=b"fake image data",
        )

        result_url, result_filename = fetch_and_save_image(api_endpoint, firebase_url, tmp_path)

        assert result_url == firebase_url
        assert result_filename == "abc123.png"
        assert (tmp_path / "abc123.png").read_bytes() == b"fake image data"
        mock_fetch_cache.assert_called_once()

    @patch("guffin.md_rendering.fetch_and_cache_asset")
    def test_fetch_failure_raises_exception(self, mock_fetch_cache: Mock, tmp_path: Path) -> None:
        """Test that fetch failure raises an exception."""
        api_endpoint = ApiEndpoint(
            url=ApiEndpointURL(local_api_port=3333, graph_name="test-graph"),
            bearer_token="test-token",
        )
        firebase_url = HttpUrl("https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/img.png?token=abc")
        mock_fetch_cache.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="Network error"):
            fetch_and_save_image(api_endpoint, firebase_url, tmp_path)

    def test_none_api_endpoint_raises_validation_error(self) -> None:
        """Test that None api_endpoint raises ValidationError."""
        firebase_url = HttpUrl("https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/img.png?token=abc")
        with pytest.raises(ValidationError):
            fetch_and_save_image(None, firebase_url, Path("/tmp/test"))  # type: ignore[arg-type]

    def test_none_firebase_url_raises_validation_error(self) -> None:
        """Test that None firebase_url raises ValidationError."""
        api_endpoint = ApiEndpoint(
            url=ApiEndpointURL(local_api_port=3333, graph_name="test-graph"),
            bearer_token="test-token",
        )
        with pytest.raises(ValidationError):
            fetch_and_save_image(api_endpoint, None, Path("/tmp/test"))  # type: ignore[arg-type]

    def test_none_output_dir_raises_validation_error(self) -> None:
        """Test that None output_dir raises ValidationError."""
        api_endpoint = ApiEndpoint(
            url=ApiEndpointURL(local_api_port=3333, graph_name="test-graph"),
            bearer_token="test-token",
        )
        firebase_url = HttpUrl("https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/img.png?token=abc")
        with pytest.raises(ValidationError):
            fetch_and_save_image(api_endpoint, firebase_url, None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestReplaceImageLinks
# ---------------------------------------------------------------------------


class TestReplaceImageLinks:
    """Tests for replace_image_links()."""

    def test_replaces_single_url(self) -> None:
        """Test replacing a single URL."""
        text = "![alt](https://firebasestorage.googleapis.com/o/img.png)"
        result = replace_image_links(text, [(HttpUrl("https://firebasestorage.googleapis.com/o/img.png"), "local.png")])
        assert "local.png" in result
        assert "firebasestorage.googleapis.com" not in result

    def test_replaces_multiple_urls(self) -> None:
        """Test replacing multiple URLs."""
        text = "![i1](https://firebasestorage.googleapis.com/o/img1.png)\n![i2](https://firebasestorage.googleapis.com/o/img2.jpg)"
        result = replace_image_links(
            text,
            [
                (HttpUrl("https://firebasestorage.googleapis.com/o/img1.png"), "local1.png"),
                (HttpUrl("https://firebasestorage.googleapis.com/o/img2.jpg"), "local2.jpg"),
            ],
        )
        assert "local1.png" in result
        assert "local2.jpg" in result
        assert "firebasestorage.googleapis.com" not in result

    def test_empty_replacements_returns_original(self) -> None:
        """Test that an empty replacements list returns the original text."""
        text = "![alt](https://firebasestorage.googleapis.com/o/img.png)"
        assert replace_image_links(text, []) == text

    def test_none_markdown_text_returns_none(self) -> None:
        """Test that None markdown_text returns None."""
        result = replace_image_links(None, [(HttpUrl("https://firebasestorage.googleapis.com/o/img.png"), "local.png")])  # type: ignore[arg-type]
        assert result is None

    def test_preserves_markdown_structure(self) -> None:
        """Test that surrounding Markdown structure is preserved."""
        text = "# Heading\n\n![image](https://firebasestorage.googleapis.com/o/img.png)\n\nSome text"
        result = replace_image_links(text, [(HttpUrl("https://firebasestorage.googleapis.com/o/img.png"), "local.png")])
        assert "# Heading" in result
        assert "Some text" in result
        assert "local.png" in result

    def test_invalid_url_replacements_raises_validation_error(self) -> None:
        """Test that invalid url_replacements raises ValidationError."""
        with pytest.raises(ValidationError):
            replace_image_links("![image](https://firebasestorage.googleapis.com/o/img.png)", "invalid")  # type: ignore[arg-type]

    def test_none_url_replacements_raises_validation_error(self) -> None:
        """Test that None url_replacements raises ValidationError."""
        with pytest.raises(ValidationError):
            replace_image_links("![image](https://firebasestorage.googleapis.com/o/img.png)", None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestNormalizeLinkText
# ---------------------------------------------------------------------------


class TestNormalizeLinkText:
    """Tests for normalize_link_text()."""

    def test_normalizes_multiline_image_link_text(self) -> None:
        """Test that multi-line image link text is normalized to a single line."""
        assert normalize_link_text("![A\nflower](image.png)") == "![A flower](image.png)"

    def test_normalizes_multiline_regular_link_text(self) -> None:
        """Test that multi-line regular link text is normalized to a single line."""
        assert normalize_link_text("[Click\nhere](https://example.com)") == "[Click here](https://example.com)"

    def test_handles_multiple_newlines_in_link_text(self) -> None:
        """Test that multiple consecutive newlines are replaced with a single space."""
        assert normalize_link_text("![Alt\n\n\ntext](image.png)") == "![Alt text](image.png)"

    def test_normalizes_multiple_links_in_text(self) -> None:
        """Test that all links in a string are normalized."""
        assert (
            normalize_link_text("![First\nimage](img1.png) and [Second\nlink](url.com)")
            == "![First image](img1.png) and [Second link](url.com)"
        )

    def test_preserves_single_line_links(self) -> None:
        """Test that links without line breaks are unchanged."""
        text = "![Single line](image.png) and [normal link](url.com)"
        assert normalize_link_text(text) == text

    def test_preserves_non_link_content(self) -> None:
        """Test that text outside links is not modified."""
        text = "# Heading\nSome paragraph text\n![Image\nwith breaks](img.png)\nMore text"
        result = normalize_link_text(text)
        assert "# Heading" in result
        assert "Some paragraph text" in result
        assert "More text" in result
        assert "![Image with breaks](img.png)" in result


# ---------------------------------------------------------------------------
# TestRemoveEscapedDoubleBrackets
# ---------------------------------------------------------------------------


class TestRemoveEscapedDoubleBrackets:
    """Tests for remove_escaped_double_brackets()."""

    def test_removes_escaped_opening_brackets(self) -> None:
        """Test that escaped opening and closing double brackets are removed."""
        assert remove_escaped_double_brackets(r"This is a \[\[page link\]\]") == "This is a page link"

    def test_removes_multiple_bracket_pairs(self) -> None:
        """Test that multiple pairs of escaped brackets are removed."""
        assert remove_escaped_double_brackets(r"\[\[First\]\] and \[\[Second\]\]") == "First and Second"

    def test_removes_brackets_in_heading(self) -> None:
        """Test that escaped brackets in headings are removed."""
        assert remove_escaped_double_brackets(r"# \[\[Illustration\]\] Mood Boards") == "# Illustration Mood Boards"

    def test_preserves_text_without_brackets(self) -> None:
        """Test that text without escaped brackets is unchanged."""
        text = "This is normal text with no brackets"
        assert remove_escaped_double_brackets(text) == text

    def test_preserves_regular_markdown_links(self) -> None:
        """Test that regular markdown links are not affected."""
        text = "[Regular link](url.com) and ![Image](img.png)"
        assert remove_escaped_double_brackets(text) == text

    def test_handles_mixed_content(self) -> None:
        """Test that function handles text with both escaped brackets and normal content."""
        text = r"# \[\[Page\]\] Title" + "\n\n" + r"Some text [link](url) and more \[\[refs\]\]"
        assert remove_escaped_double_brackets(text) == "# Page Title\n\nSome text [link](url) and more refs"


# ---------------------------------------------------------------------------
# TestBundleMdFile
# ---------------------------------------------------------------------------


class TestBundleMdFile:
    """Tests for bundle_md_file()."""

    def test_file_not_found_raises_exception(self, tmp_path: Path) -> None:
        """Test that a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Markdown file not found"):
            bundle_md_file(tmp_path / "nonexistent_file.md", 3333, "test-graph", "test-token", tmp_path)

    @patch("guffin.md_rendering.find_markdown_image_links")
    def test_no_firebase_links_exits_early(self, mock_find: Mock, tmp_path: Path) -> None:
        """Test that the function exits early when no Cloud Firestore links are found."""
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        markdown_file = input_dir / "test.md"
        markdown_file.write_text("# Test\n\nNo images here.")
        mock_find.return_value = []

        bundle_md_file(markdown_file, 3333, "test-graph", "test-token", output_dir)

        assert not (output_dir / "test.md").exists()

    @patch("guffin.md_rendering.fetch_and_save_image")
    @patch("guffin.md_rendering.find_markdown_image_links")
    def test_processes_file_successfully(self, mock_find: Mock, mock_fetch: Mock, tmp_path: Path) -> None:
        """Test successful end-to-end file bundling."""
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        markdown_file = input_dir / "test.md"
        markdown_file.write_text("![image](https://firebasestorage.googleapis.com/o/img.png)")
        mock_find.return_value = [
            (
                "![image](https://firebasestorage.googleapis.com/o/img.png)",
                "https://firebasestorage.googleapis.com/o/img.png",
            )
        ]
        mock_fetch.return_value = ("https://firebasestorage.googleapis.com/o/img.png", "local_image.png")

        bundle_md_file(markdown_file, 3333, "test-graph", "test-token", output_dir)

        bundle_dir = output_dir / "test.mdbundle"
        assert bundle_dir.exists()
        assert bundle_dir.is_dir()
        output_file = bundle_dir / "test.md"
        assert output_file.exists()
        output_content = output_file.read_text()
        assert "local_image.png" in output_content
        assert "firebasestorage.googleapis.com" not in output_content

    @patch("guffin.md_rendering.fetch_and_save_image")
    @patch("guffin.md_rendering.find_markdown_image_links")
    def test_continues_on_fetch_error(self, mock_find: Mock, mock_fetch: Mock, tmp_path: Path) -> None:
        """Test that bundling continues when one image fetch fails."""
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        markdown_file = input_dir / "test.md"
        markdown_file.write_text(
            "![img1](https://firebasestorage.googleapis.com/o/img1.png)\n"
            "![img2](https://firebasestorage.googleapis.com/o/img2.png)"
        )
        mock_find.return_value = [
            ("![img1](...)", "https://firebasestorage.googleapis.com/o/img1.png"),
            ("![img2](...)", "https://firebasestorage.googleapis.com/o/img2.png"),
        ]
        mock_fetch.side_effect = [
            Exception("Network error"),
            ("https://firebasestorage.googleapis.com/o/img2.png", "local_image2.png"),
        ]

        bundle_md_file(markdown_file, 3333, "test-graph", "test-token", output_dir)

        bundle_dir = output_dir / "test.mdbundle"
        assert bundle_dir.exists()
        output_file = bundle_dir / "test.md"
        assert output_file.exists()
        assert "local_image2.png" in output_file.read_text()
