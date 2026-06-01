"""Tests for the roam_md_bundle module."""

import logging

# pyright: basic
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from pydantic import HttpUrl, ValidationError

from inktomi.roam_md_bundle import (
    find_markdown_image_links,
    fetch_and_save_image,
    replace_image_links,
    normalize_link_text,
    remove_escaped_double_brackets,
    bundle_md_file,
    _normalize_for_posix,
)
from inktomi.roam_asset import RoamAsset
from inktomi.roam_local_api import ApiEndpoint, ApiEndpointURL
from datetime import datetime

logger = logging.getLogger(__name__)


class TestNormalizeForPosix:
    """Tests for the _normalize_for_posix function."""

    def test_replaces_spaces_with_underscores(self) -> None:
        """Test that spaces are replaced with underscores."""
        result: str = _normalize_for_posix("hello world test")
        assert result == "hello_world_test"

    def test_removes_special_characters(self) -> None:
        """Test that special characters are removed."""
        result: str = _normalize_for_posix("hello@world!test#file.txt")
        assert result == "helloworldtestfile.txt"

    def test_preserves_safe_characters(self) -> None:
        """Test that safe characters (alphanumeric, underscore, hyphen, period) are preserved."""
        result: str = _normalize_for_posix("file_name-123.txt")
        assert result == "file_name-123.txt"

    def test_handles_unicode_characters(self) -> None:
        """Test that Unicode characters are converted to ASCII equivalents."""
        result: str = _normalize_for_posix("café résumé naïve")
        assert result == "cafe_resume_naive"

    def test_handles_empty_string(self) -> None:
        """Test handling of empty string."""
        result: str = _normalize_for_posix("")
        assert result == ""

    def test_handles_only_special_characters(self) -> None:
        """Test handling of string with only special characters."""
        result: str = _normalize_for_posix("@#$%^&*()")
        assert result == ""

    def test_handles_parentheses_and_brackets(self) -> None:
        """Test that parentheses and brackets are removed."""
        result: str = _normalize_for_posix("My Document (2024) [Draft].txt")
        assert result == "My_Document_2024_Draft.txt"

    def test_handles_mixed_case(self) -> None:
        """Test that mixed case is preserved."""
        result: str = _normalize_for_posix("MyDocumentFile.TXT")
        assert result == "MyDocumentFile.TXT"

    def test_handles_multiple_spaces(self) -> None:
        """Test that multiple consecutive spaces become single underscores."""
        result: str = _normalize_for_posix("hello    world")
        assert result == "hello_world"

    def test_handles_email_addresses(self) -> None:
        """Test normalization of email-like strings."""
        result: str = _normalize_for_posix("user@example.com")
        assert result == "userexample.com"

    def test_handles_urls(self) -> None:
        """Test normalization of URL-like strings."""
        result: str = _normalize_for_posix("https://example.com/path")
        assert result == "httpsexample.compath"

    def test_preserves_file_extensions(self) -> None:
        """Test that file extensions with periods are preserved."""
        result: str = _normalize_for_posix("document.backup.tar.gz")
        assert result == "document.backup.tar.gz"

    def test_handles_accented_characters(self) -> None:
        """Test various accented characters are normalized."""
        result: str = _normalize_for_posix("Zürich Москва 北京")
        # Zürich -> Zurich, Cyrillic and Chinese characters removed
        assert result == "Zurich"

    def test_handles_leading_trailing_special_chars(self) -> None:
        """Test that leading/trailing special characters are removed."""
        result: str = _normalize_for_posix("!!!filename###.txt")
        assert result == "filename.txt"


class TestFindMarkdownImageLinks:
    """Tests for the find_markdown_image_links function."""

    def test_finds_single_firebase_link(self) -> None:
        """Test finding a single Cloud Firestore image link."""
        markdown_text: str = (
            "![alt text](https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2F-9owRBegJ8.jpeg.enc?alt=media&token=abc123)"
        )

        matches: list[tuple[str, HttpUrl]] = find_markdown_image_links(markdown_text)

        assert len(matches) == 1
        assert (
            str(matches[0][1])
            == "https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com/o/imgs%2Fapp%2FSCFH%2F-9owRBegJ8.jpeg.enc?alt=media&token=abc123"
        )
        assert isinstance(matches[0][1], HttpUrl)

    def test_finds_multiple_firebase_links(self) -> None:
        """Test finding multiple Cloud Firestore image links."""
        markdown_text: str = """
        ![image1](https://firebasestorage.googleapis.com/v0/b/test1.appspot.com/o/img1.png?token=abc)
        Some text here
        ![image2](https://firebasestorage.googleapis.com/v0/b/test2.appspot.com/o/img2.jpg?token=def)
        """

        matches: list[tuple[str, HttpUrl]] = find_markdown_image_links(markdown_text)

        assert len(matches) == 2
        assert "img1.png" in str(matches[0][1])
        assert "img2.jpg" in str(matches[1][1])
        assert isinstance(matches[0][1], HttpUrl)
        assert isinstance(matches[1][1], HttpUrl)

    def test_ignores_non_firebase_links(self) -> None:
        """Test that non-Cloud Firestore URLs are ignored."""
        markdown_text: str = """
        ![local](./local-image.png)
        ![remote](https://example.com/image.jpg)
        ![Cloud Firestore](https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/img.png?token=abc)
        """

        matches: list[tuple[str, HttpUrl]] = find_markdown_image_links(markdown_text)

        assert len(matches) == 1
        assert "firebasestorage.googleapis.com" in str(matches[0][1])
        assert isinstance(matches[0][1], HttpUrl)

    def test_none_markdown_raises_validation_error(self) -> None:
        """Test that None markdown_text raises ValidationError."""
        with pytest.raises(ValidationError):
            find_markdown_image_links(None)  # type: ignore[arg-type]

    def test_empty_markdown_returns_empty_list(self) -> None:
        """Test that empty markdown returns empty list."""
        markdown_text: str = ""

        matches: list[tuple[str, HttpUrl]] = find_markdown_image_links(markdown_text)

        assert len(matches) == 0

    def test_markdown_without_images_returns_empty_list(self) -> None:
        """Test that markdown without images returns empty list."""
        markdown_text: str = "# Heading\n\nSome text without any images."

        matches: list[tuple[str, HttpUrl]] = find_markdown_image_links(markdown_text)

        assert len(matches) == 0

    def test_handles_multiline_alt_text(self) -> None:
        """Test that multiline alt text is handled correctly."""
        markdown_text: str = """![This is
        multiline
        alt text](https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/img.png?token=abc)"""

        matches: list[tuple[str, HttpUrl]] = find_markdown_image_links(markdown_text)

        assert len(matches) == 1
        assert "firebasestorage.googleapis.com" in str(matches[0][1])
        assert isinstance(matches[0][1], HttpUrl)

    def test_returns_full_match_and_url(self) -> None:
        """Test that function returns both full match and URL."""
        markdown_text: str = "![alt](https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/img.png?token=abc)"

        matches: list[tuple[str, HttpUrl]] = find_markdown_image_links(markdown_text)

        full_match, url = matches[0]
        assert full_match.startswith("![")
        assert full_match.endswith(")")
        assert str(url).startswith("https://firebasestorage.googleapis.com")
        assert isinstance(url, HttpUrl)


class TestFetchAndSaveImage:
    """Tests for the fetch_and_save_image function."""

    @patch("inktomi.roam_md_bundle.FetchRoamAsset.fetch")
    @patch("builtins.open", new_callable=mock_open)
    def test_fetches_and_saves_image_successfully(self, mock_file: Mock, mock_fetch: Mock) -> None:
        """Test successful image fetch and save."""
        # Setup
        api_endpoint: ApiEndpoint = ApiEndpoint(
            url=ApiEndpointURL(local_api_port=3333, graph_name="test-graph"),
            bearer_token="test-token",
        )
        firebase_url: HttpUrl = HttpUrl(
            "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/img.png?token=abc"
        )
        output_dir: Path = Path("/tmp/test")

        mock_roam_asset: RoamAsset = RoamAsset(
            file_name="test_image.png",
            last_modified=datetime.now(),
            media_type="image/png",
            contents=b"fake image data",
        )
        mock_fetch.return_value = mock_roam_asset

        # Execute
        result_url, result_filename = fetch_and_save_image(api_endpoint, firebase_url, output_dir)

        # Verify
        assert result_url == firebase_url
        assert isinstance(result_url, HttpUrl)
        assert result_filename == "test_image.png"
        mock_fetch.assert_called_once()
        mock_file.assert_called_once_with(output_dir / "test_image.png", "wb")

    @patch("inktomi.roam_md_bundle.FetchRoamAsset.fetch")
    def test_fetch_failure_raises_exception(self, mock_fetch: Mock) -> None:
        """Test that fetch failure raises an exception."""
        api_endpoint: ApiEndpoint = ApiEndpoint(
            url=ApiEndpointURL(local_api_port=3333, graph_name="test-graph"),
            bearer_token="test-token",
        )
        firebase_url: HttpUrl = HttpUrl(
            "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/img.png?token=abc"
        )
        output_dir: Path = Path("/tmp/test")

        mock_fetch.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="Network error"):
            fetch_and_save_image(api_endpoint, firebase_url, output_dir)

    def test_none_api_endpoint_raises_validation_error(self) -> None:
        """Test that None api_endpoint raises ValidationError."""
        firebase_url: HttpUrl = HttpUrl(
            "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/img.png?token=abc"
        )
        output_dir: Path = Path("/tmp/test")

        with pytest.raises(ValidationError):
            fetch_and_save_image(None, firebase_url, output_dir)  # type: ignore[arg-type]

    def test_none_firebase_url_raises_validation_error(self) -> None:
        """Test that None firebase_url raises ValidationError."""
        api_endpoint: ApiEndpoint = ApiEndpoint(
            url=ApiEndpointURL(local_api_port=3333, graph_name="test-graph"),
            bearer_token="test-token",
        )
        output_dir: Path = Path("/tmp/test")

        with pytest.raises(ValidationError):
            fetch_and_save_image(api_endpoint, None, output_dir)  # type: ignore[arg-type]

    def test_none_output_dir_raises_validation_error(self) -> None:
        """Test that None output_dir raises ValidationError."""
        api_endpoint: ApiEndpoint = ApiEndpoint(
            url=ApiEndpointURL(local_api_port=3333, graph_name="test-graph"),
            bearer_token="test-token",
        )
        firebase_url: HttpUrl = HttpUrl(
            "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/img.png?token=abc"
        )

        with pytest.raises(ValidationError):
            fetch_and_save_image(api_endpoint, firebase_url, None)  # type: ignore[arg-type]


class TestReplaceImageLinks:
    """Tests for the replace_image_links function."""

    def test_replaces_single_url(self) -> None:
        """Test replacing a single URL."""
        markdown_text: str = "![alt](https://firebasestorage.googleapis.com/o/img.png)"
        url_replacements: list[tuple[HttpUrl, str]] = [
            (HttpUrl("https://firebasestorage.googleapis.com/o/img.png"), "local_image.png")
        ]

        result: str = replace_image_links(markdown_text, url_replacements)

        assert "local_image.png" in result
        assert "firebasestorage.googleapis.com" not in result

    def test_replaces_multiple_urls(self) -> None:
        """Test replacing multiple URLs."""
        markdown_text: str = """
        ![img1](https://firebasestorage.googleapis.com/o/img1.png)
        ![img2](https://firebasestorage.googleapis.com/o/img2.jpg)
        """
        url_replacements: list[tuple[HttpUrl, str]] = [
            (HttpUrl("https://firebasestorage.googleapis.com/o/img1.png"), "local1.png"),
            (HttpUrl("https://firebasestorage.googleapis.com/o/img2.jpg"), "local2.jpg"),
        ]

        result: str = replace_image_links(markdown_text, url_replacements)

        assert "local1.png" in result
        assert "local2.jpg" in result
        assert "firebasestorage.googleapis.com" not in result

    def test_empty_replacements_returns_original(self) -> None:
        """Test that empty replacements list returns original text."""
        markdown_text: str = "![alt](https://firebasestorage.googleapis.com/o/img.png)"
        url_replacements: list[tuple[HttpUrl, str]] = []

        result: str = replace_image_links(markdown_text, url_replacements)

        assert result == markdown_text

    def test_none_markdown_text_returns_none(self) -> None:
        """Test that None markdown_text returns None."""
        url_replacements: list[tuple[HttpUrl, str]] = [
            (HttpUrl("https://firebasestorage.googleapis.com/o/img.png"), "local_image.png")
        ]

        result = replace_image_links(None, url_replacements)  # type: ignore[arg-type]

        assert result is None

    def test_preserves_markdown_structure(self) -> None:
        """Test that markdown structure is preserved."""
        markdown_text: str = "# Heading\n\n![image](https://firebasestorage.googleapis.com/o/img.png)\n\nSome text"
        url_replacements: list[tuple[HttpUrl, str]] = [
            (HttpUrl("https://firebasestorage.googleapis.com/o/img.png"), "local.png")
        ]

        result: str = replace_image_links(markdown_text, url_replacements)

        assert "# Heading" in result
        assert "Some text" in result
        assert "local.png" in result

    def test_invalid_url_replacements_raises_validation_error(self) -> None:
        """Test that invalid url_replacements raises ValidationError."""
        markdown_text: str = "![image](https://firebasestorage.googleapis.com/o/img.png)"

        # Pass invalid url_replacements (not a list of tuples)
        with pytest.raises(ValidationError):
            replace_image_links(markdown_text, "invalid")  # type: ignore[arg-type]

    def test_none_url_replacements_raises_validation_error(self) -> None:
        """Test that None url_replacements raises ValidationError."""
        markdown_text: str = "![image](https://firebasestorage.googleapis.com/o/img.png)"

        with pytest.raises(ValidationError):
            replace_image_links(markdown_text, None)  # type: ignore[arg-type]


class TestNormalizeLinkText:
    """Tests for the normalize_link_text function."""

    def test_normalizes_multiline_image_link_text(self) -> None:
        """Test that multi-line image link text is normalized to single line."""
        markdown_text: str = "![A\nflower](image.png)"
        result: str = normalize_link_text(markdown_text)
        assert result == "![A flower](image.png)"

    def test_normalizes_multiline_regular_link_text(self) -> None:
        """Test that multi-line regular link text is normalized to single line."""
        markdown_text: str = "[Click\nhere](https://example.com)"
        result: str = normalize_link_text(markdown_text)
        assert result == "[Click here](https://example.com)"

    def test_handles_multiple_newlines_in_link_text(self) -> None:
        """Test that multiple consecutive newlines are replaced with single space."""
        markdown_text: str = "![Alt\n\n\ntext](image.png)"
        result: str = normalize_link_text(markdown_text)
        assert result == "![Alt text](image.png)"

    def test_normalizes_multiple_links_in_text(self) -> None:
        """Test that multiple links in the same text are all normalized."""
        markdown_text: str = "![First\nimage](img1.png) and [Second\nlink](url.com)"
        result: str = normalize_link_text(markdown_text)
        assert result == "![First image](img1.png) and [Second link](url.com)"

    def test_preserves_single_line_links(self) -> None:
        """Test that links without line breaks are unchanged."""
        markdown_text: str = "![Single line](image.png) and [normal link](url.com)"
        result: str = normalize_link_text(markdown_text)
        assert result == "![Single line](image.png) and [normal link](url.com)"

    def test_preserves_non_link_content(self) -> None:
        """Test that text outside of links is not modified."""
        markdown_text: str = """# Heading
Some paragraph text
![Image\nwith breaks](img.png)
More text"""
        result: str = normalize_link_text(markdown_text)
        assert "# Heading" in result
        assert "Some paragraph text" in result
        assert "More text" in result
        assert "![Image with breaks](img.png)" in result


class TestRemoveEscapedDoubleBrackets:
    """Tests for the remove_escaped_double_brackets function."""

    def test_removes_escaped_opening_brackets(self) -> None:
        """Test that escaped opening double brackets are removed."""
        markdown_text: str = r"This is a \[\[page link\]\]"
        result: str = remove_escaped_double_brackets(markdown_text)
        assert result == "This is a page link"

    def test_removes_multiple_bracket_pairs(self) -> None:
        """Test that multiple pairs of escaped brackets are removed."""
        markdown_text: str = r"\[\[First\]\] and \[\[Second\]\]"
        result: str = remove_escaped_double_brackets(markdown_text)
        assert result == "First and Second"

    def test_removes_brackets_in_heading(self) -> None:
        """Test that escaped brackets in headings are removed."""
        markdown_text: str = r"# \[\[Illustration\]\] Mood Boards"
        result: str = remove_escaped_double_brackets(markdown_text)
        assert result == "# Illustration Mood Boards"

    def test_preserves_text_without_brackets(self) -> None:
        """Test that text without escaped brackets is unchanged."""
        markdown_text: str = "This is normal text with no brackets"
        result: str = remove_escaped_double_brackets(markdown_text)
        assert result == "This is normal text with no brackets"

    def test_preserves_regular_markdown_links(self) -> None:
        """Test that regular markdown links are not affected."""
        markdown_text: str = "[Regular link](url.com) and ![Image](img.png)"
        result: str = remove_escaped_double_brackets(markdown_text)
        assert result == "[Regular link](url.com) and ![Image](img.png)"

    def test_handles_mixed_content(self) -> None:
        """Test that function handles text with both escaped brackets and normal content."""
        markdown_text: str = r"# \[\[Page\]\] Title" + "\n\n" + r"Some text [link](url) and more \[\[refs\]\]"
        result: str = remove_escaped_double_brackets(markdown_text)
        assert result == "# Page Title\n\nSome text [link](url) and more refs"


class TestBundleMdFile:
    """Tests for the bundle_md_file function."""

    def test_file_not_found_raises_exception(self, tmp_path: Path) -> None:
        """Test that non-existent file raises FileNotFoundError."""
        markdown_file: Path = tmp_path / "nonexistent_file.md"

        with pytest.raises(FileNotFoundError, match="Markdown file not found"):
            bundle_md_file(markdown_file, 3333, "test-graph", "test-token", tmp_path)

    @patch("inktomi.roam_md_bundle.find_markdown_image_links")
    def test_no_firebase_links_exits_early(self, mock_find: Mock, tmp_path: Path) -> None:
        """Test that function exits early when no Cloud Firestore links found."""
        # Create separate input and output directories
        input_dir: Path = tmp_path / "input"
        output_dir: Path = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        # Create a temporary markdown file in input directory
        markdown_file: Path = input_dir / "test.md"
        markdown_file.write_text("# Test\n\nNo images here.")

        mock_find.return_value = []

        # Should not raise exception
        bundle_md_file(markdown_file, 3333, "test-graph", "test-token", output_dir)

        # Verify no output file was created since no Cloud Firestore links were found
        output_file: Path = output_dir / "test.md"
        assert not output_file.exists()

    @patch("inktomi.roam_md_bundle.fetch_and_save_image")
    @patch("inktomi.roam_md_bundle.find_markdown_image_links")
    def test_processes_file_successfully(self, mock_find: Mock, mock_fetch: Mock, tmp_path: Path) -> None:
        """Test successful file processing."""
        # Create separate input and output directories
        input_dir: Path = tmp_path / "input"
        output_dir: Path = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        # Create a temporary markdown file in input directory
        markdown_file: Path = input_dir / "test.md"
        markdown_content: str = "![image](https://firebasestorage.googleapis.com/o/img.png)"
        markdown_file.write_text(markdown_content)

        # Mock finding links
        mock_find.return_value = [
            (
                "![image](https://firebasestorage.googleapis.com/o/img.png)",
                "https://firebasestorage.googleapis.com/o/img.png",
            )
        ]

        # Mock fetching and saving
        mock_fetch.return_value = ("https://firebasestorage.googleapis.com/o/img.png", "local_image.png")

        # Execute
        bundle_md_file(markdown_file, 3333, "test-graph", "test-token", output_dir)

        # Verify bundle directory was created (without .md extension)
        bundle_dir: Path = output_dir / "test.mdbundle"
        assert bundle_dir.exists()
        assert bundle_dir.is_dir()

        # Verify output file was created in the bundle directory
        output_file: Path = bundle_dir / "test.md"
        assert output_file.exists()

        # Verify content was updated
        output_content: str = output_file.read_text()
        assert "local_image.png" in output_content
        assert "firebasestorage.googleapis.com" not in output_content

    @patch("inktomi.roam_md_bundle.fetch_and_save_image")
    @patch("inktomi.roam_md_bundle.find_markdown_image_links")
    def test_continues_on_fetch_error(self, mock_find: Mock, mock_fetch: Mock, tmp_path: Path) -> None:
        """Test that processing continues when one image fetch fails."""
        # Create separate input and output directories
        input_dir: Path = tmp_path / "input"
        output_dir: Path = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        # Create a temporary markdown file in input directory
        markdown_file: Path = input_dir / "test.md"
        markdown_content: str = """
        ![image1](https://firebasestorage.googleapis.com/o/img1.png)
        ![image2](https://firebasestorage.googleapis.com/o/img2.png)
        """
        markdown_file.write_text(markdown_content)

        # Mock finding links
        mock_find.return_value = [
            (
                "![image1](https://firebasestorage.googleapis.com/o/img1.png)",
                "https://firebasestorage.googleapis.com/o/img1.png",
            ),
            (
                "![image2](https://firebasestorage.googleapis.com/o/img2.png)",
                "https://firebasestorage.googleapis.com/o/img2.png",
            ),
        ]

        # Mock first fetch to fail, second to succeed
        mock_fetch.side_effect = [
            Exception("Network error"),
            ("https://firebasestorage.googleapis.com/o/img2.png", "local_image2.png"),
        ]

        # Execute - should not raise exception
        bundle_md_file(markdown_file, 3333, "test-graph", "test-token", output_dir)

        # Verify bundle directory was created (without .md extension)
        bundle_dir: Path = output_dir / "test.mdbundle"
        assert bundle_dir.exists()

        # Verify output file was still created in the bundle directory
        output_file: Path = bundle_dir / "test.md"
        assert output_file.exists()

        # Verify second image was replaced
        output_content: str = output_file.read_text()
        assert "local_image2.png" in output_content
