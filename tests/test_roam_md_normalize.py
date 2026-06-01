"""Unit tests for inktomi.roam_md_normalize."""

from inktomi.roam_md_normalize import normalize, normalize_italics, strip_square_brackets


class TestNormalizeItalics:
    """Tests for normalize_italics — converting Roam __italic__ to CommonMark *italic*."""

    def test_basic(self) -> None:
        """Test that a simple __word__ is converted to *word*."""
        assert normalize_italics("__hello__") == "*hello*"

    def test_multi_word(self) -> None:
        """Test that a multi-word __italic span__ is converted correctly."""
        assert normalize_italics("__hello world__") == "*hello world*"

    def test_multiple_spans(self) -> None:
        """Test that multiple __italic__ spans in one string are all converted."""
        assert normalize_italics("__foo__ and __bar__") == "*foo* and *bar*"

    def test_inline(self) -> None:
        """Test that an italic span embedded in plain text is converted."""
        assert normalize_italics("some __italic__ text") == "some *italic* text"

    def test_no_italic(self) -> None:
        """Test that plain text without italic markers is returned unchanged."""
        assert normalize_italics("plain text") == "plain text"

    def test_bold_unchanged(self) -> None:
        """Test that CommonMark **bold** markers are left alone."""
        assert normalize_italics("**bold**") == "**bold**"

    def test_italic_and_bold(self) -> None:
        """Test that italic is converted while bold is preserved in the same string."""
        assert normalize_italics("__italic__ and **bold**") == "*italic* and **bold**"

    def test_leading_space_inside_not_matched(self) -> None:
        """Test that a space after opening __ prevents the span from matching."""
        # space after opening __ → not a Roam italic
        assert normalize_italics("__ not italic__") == "__ not italic__"

    def test_trailing_space_inside_not_matched(self) -> None:
        """Test that a space before closing __ prevents the span from matching."""
        # space before closing __ → not a Roam italic
        assert normalize_italics("__not italic __") == "__not italic __"

    def test_adjacent_punctuation(self) -> None:
        """Test that punctuation immediately after closing __ does not block conversion."""
        assert normalize_italics("__italic__!") == "*italic*!"

    def test_empty_string(self) -> None:
        """Test that an empty string is returned unchanged."""
        assert normalize_italics("") == ""


class TestStripSquareBrackets:
    """Tests for strip_square_brackets — removing all [ and ] characters."""

    def test_page_link(self) -> None:
        """Test that a standard [[Page Name]] link has its brackets stripped."""
        assert strip_square_brackets("[[Page Name]]") == "Page Name"

    def test_nested_page_link(self) -> None:
        """Test that nested brackets in [[nested [[pages]]]] are all removed."""
        assert strip_square_brackets("[[nested [[pages]]]]") == "nested pages"

    def test_hash_tag(self) -> None:
        """Test that #[[multi-word tag]] loses its brackets but keeps the hash."""
        assert strip_square_brackets("#[[multi-word tag]]") == "#multi-word tag"

    def test_single_brackets(self) -> None:
        """Test that a single-bracket [text] also has its brackets removed."""
        assert strip_square_brackets("[text]") == "text"

    def test_alias_to_page_link(self) -> None:
        """Test that [display text]([[Page Name]]) strips [] but preserves ()."""
        # [display text]([[Page Name]]) — only [] removed, () preserved
        assert strip_square_brackets("[display text]([[Page Name]])") == "display text(Page Name)"

    def test_no_brackets(self) -> None:
        """Test that plain text without brackets is returned unchanged."""
        assert strip_square_brackets("plain text") == "plain text"

    def test_block_reference_unaffected(self) -> None:
        """Test that ((block-uid)) passes through unchanged since it has no square brackets."""
        # ((block-uid)) has no square brackets — should pass through unchanged
        assert strip_square_brackets("((block-uid))") == "((block-uid))"

    def test_empty_string(self) -> None:
        """Test that an empty string is returned unchanged."""
        assert strip_square_brackets("") == ""

    def test_mixed_content(self) -> None:
        """Test that a page link embedded in surrounding text is handled correctly."""
        assert strip_square_brackets("See [[Page Name]] for details.") == "See Page Name for details."


class TestNormalize:
    """Tests for normalize — applying all Roam-to-CommonMark transformations in order."""

    def test_italics_and_page_link(self) -> None:
        """Test that both italic conversion and bracket stripping are applied."""
        assert normalize("__italic__ [[page]]") == "*italic* page"

    def test_italics_applied_before_brackets(self) -> None:
        """Test that italic conversion runs before bracket stripping."""
        # italic span inside a page link: [[__italic__]] → after italics: [[*italic*]]
        # after strip brackets: *italic*
        assert normalize("[[__italic__]]") == "*italic*"

    def test_plain_text_passthrough(self) -> None:
        """Test that plain text with no Roam syntax is returned unchanged."""
        assert normalize("plain text") == "plain text"

    def test_empty_string(self) -> None:
        """Test that an empty string is returned unchanged."""
        assert normalize("") == ""

    def test_bold_and_page_link(self) -> None:
        """Test that bold is preserved while the page link brackets are stripped."""
        assert normalize("**bold** [[page]]") == "**bold** page"
