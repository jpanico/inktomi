"""Unit tests for guffin.roam.roam_md_to_pandoc_md."""

from guffin.roam.roam_md_to_pandoc_md import (
    convert_highlights,
    convert_italics,
    convert_page_link_aliases,
    strip_double_brackets,
    to_pandoc_md,
)


class TestConvertItalics:
    """Tests for convert_italics — converting Roam __italic__ to Pandoc Markdown *italic*."""

    def test_basic(self) -> None:
        """Test that a simple __word__ is converted to *word*."""
        assert convert_italics("__hello__") == "*hello*"

    def test_multi_word(self) -> None:
        """Test that a multi-word __italic span__ is converted correctly."""
        assert convert_italics("__hello world__") == "*hello world*"

    def test_multiple_spans(self) -> None:
        """Test that multiple __italic__ spans in one string are all converted."""
        assert convert_italics("__foo__ and __bar__") == "*foo* and *bar*"

    def test_inline(self) -> None:
        """Test that an italic span embedded in plain text is converted."""
        assert convert_italics("some __italic__ text") == "some *italic* text"

    def test_no_italic(self) -> None:
        """Test that plain text without italic markers is returned unchanged."""
        assert convert_italics("plain text") == "plain text"

    def test_bold_unchanged(self) -> None:
        """Test that Pandoc Markdown **bold** markers are left alone."""
        assert convert_italics("**bold**") == "**bold**"

    def test_italic_and_bold(self) -> None:
        """Test that italic is converted while bold is preserved in the same string."""
        assert convert_italics("__italic__ and **bold**") == "*italic* and **bold**"

    def test_leading_space_inside_not_matched(self) -> None:
        """Test that a space after opening __ prevents the span from matching."""
        assert convert_italics("__ not italic__") == "__ not italic__"

    def test_trailing_space_inside_not_matched(self) -> None:
        """Test that a space before closing __ prevents the span from matching."""
        assert convert_italics("__not italic __") == "__not italic __"

    def test_adjacent_punctuation(self) -> None:
        """Test that punctuation immediately after closing __ does not block conversion."""
        assert convert_italics("__italic__!") == "*italic*!"

    def test_empty_string(self) -> None:
        """Test that an empty string is returned unchanged."""
        assert convert_italics("") == ""


class TestConvertHighlights:
    """Tests for convert_highlights — converting Roam ^^highlight^^ to [text]{.mark}."""

    def test_basic(self) -> None:
        """Test that a simple ^^word^^ is converted to [word]{.mark}."""
        assert convert_highlights("^^hello^^") == "[hello]{.mark}"

    def test_multi_word(self) -> None:
        """Test that a multi-word ^^highlight span^^ is converted correctly."""
        assert convert_highlights("^^hello world^^") == "[hello world]{.mark}"

    def test_multiple_spans(self) -> None:
        """Test that multiple ^^highlight^^ spans in one string are all converted."""
        assert convert_highlights("^^foo^^ and ^^bar^^") == "[foo]{.mark} and [bar]{.mark}"

    def test_inline(self) -> None:
        """Test that a highlight span embedded in plain text is converted."""
        assert convert_highlights("some ^^highlighted^^ text") == "some [highlighted]{.mark} text"

    def test_no_highlight(self) -> None:
        """Test that plain text without highlight markers is returned unchanged."""
        assert convert_highlights("plain text") == "plain text"

    def test_incomplete_not_matched(self) -> None:
        """Test that a single ^^ without a closing pair is left unchanged."""
        assert convert_highlights("^^not complete") == "^^not complete"

    def test_empty_string(self) -> None:
        """Test that an empty string is returned unchanged."""
        assert convert_highlights("") == ""


class TestConvertPageLinkAliases:
    """Tests for convert_page_link_aliases — [display]([[Page Name]]) → [display](Page Name)."""

    def test_basic(self) -> None:
        """Test that a simple alias is converted to a Pandoc Markdown inline link."""
        assert convert_page_link_aliases("[display]([[Page Name]])") == "[display](Page Name)"

    def test_multi_word_display_and_page(self) -> None:
        """Test that multi-word display text and page name are both handled correctly."""
        assert convert_page_link_aliases("[display text]([[Multi Word Page]])") == "[display text](Multi Word Page)"

    def test_plain_page_link_unchanged(self) -> None:
        """Test that a plain [[Page Name]] without alias prefix is left unchanged."""
        assert convert_page_link_aliases("[[Page Name]]") == "[[Page Name]]"

    def test_block_ref_alias_unchanged(self) -> None:
        """Test that a [display]((block-uid)) alias to a block ref is left unchanged."""
        assert convert_page_link_aliases("[display]((block-uid))") == "[display]((block-uid))"

    def test_multiple_aliases(self) -> None:
        """Test that multiple aliases in one string are all converted."""
        assert convert_page_link_aliases("[a]([[P1]]) and [b]([[P2]])") == "[a](P1) and [b](P2)"

    def test_no_alias(self) -> None:
        """Test that plain text with no alias pattern is returned unchanged."""
        assert convert_page_link_aliases("plain text") == "plain text"

    def test_empty_string(self) -> None:
        """Test that an empty string is returned unchanged."""
        assert convert_page_link_aliases("") == ""


class TestStripDoubleBrackets:
    """Tests for strip_double_brackets — removing [[ and ]] delimiters only."""

    def test_page_link(self) -> None:
        """Test that [[Page Name]] has its double brackets stripped."""
        assert strip_double_brackets("[[Page Name]]") == "Page Name"

    def test_nested_page_link(self) -> None:
        """Test that nested [[nested [[pages]]]] has all double brackets removed."""
        assert strip_double_brackets("[[nested [[pages]]]]") == "nested pages"

    def test_hash_tag(self) -> None:
        """Test that #[[multi-word tag]] loses its double brackets but keeps the hash."""
        assert strip_double_brackets("#[[multi-word tag]]") == "#multi-word tag"

    def test_single_brackets_preserved(self) -> None:
        """Test that single-bracket [text] is left unchanged (valid Pandoc Markdown syntax)."""
        assert strip_double_brackets("[text]") == "[text]"

    def test_block_reference_unaffected(self) -> None:
        """Test that ((block-uid)) passes through unchanged since it has no double brackets."""
        assert strip_double_brackets("((block-uid))") == "((block-uid))"

    def test_no_brackets(self) -> None:
        """Test that plain text without brackets is returned unchanged."""
        assert strip_double_brackets("plain text") == "plain text"

    def test_empty_string(self) -> None:
        """Test that an empty string is returned unchanged."""
        assert strip_double_brackets("") == ""

    def test_mixed_content(self) -> None:
        """Test that a page link embedded in surrounding text is handled correctly."""
        assert strip_double_brackets("See [[Page Name]] for details.") == "See Page Name for details."

    def test_pandoc_link_after_alias_conversion(self) -> None:
        """Test that [display](Page Name) produced by alias conversion is left unchanged."""
        assert strip_double_brackets("[display](Page Name)") == "[display](Page Name)"


class TestToPandocMd:
    """Tests for to_pandoc_md — applying all Roam-to-Pandoc-Markdown conversions in order."""

    def test_italics_and_page_link(self) -> None:
        """Test that both italic conversion and double-bracket stripping are applied."""
        assert to_pandoc_md("__italic__ [[page]]") == "*italic* page"

    def test_italics_applied_before_brackets(self) -> None:
        """Test that italic conversion runs before double-bracket stripping."""
        assert to_pandoc_md("[[__italic__]]") == "*italic*"

    def test_plain_text_passthrough(self) -> None:
        """Test that plain text with no Roam syntax is returned unchanged."""
        assert to_pandoc_md("plain text") == "plain text"

    def test_empty_string(self) -> None:
        """Test that an empty string is returned unchanged."""
        assert to_pandoc_md("") == ""

    def test_bold_and_page_link(self) -> None:
        """Test that bold is preserved while the page link double brackets are stripped."""
        assert to_pandoc_md("**bold** [[page]]") == "**bold** page"

    def test_alias_converted_to_link(self) -> None:
        """Test that a page-link alias becomes a Pandoc Markdown inline link."""
        assert to_pandoc_md("[display]([[Page Name]])") == "[display](Page Name)"

    def test_highlight_converted_to_span(self) -> None:
        """Test that a Roam highlight becomes a Pandoc bracketed span."""
        assert to_pandoc_md("^^highlighted^^") == "[highlighted]{.mark}"

    def test_block_ref_left_verbatim(self) -> None:
        """Test that a Roam block reference is left unchanged."""
        assert to_pandoc_md("((block-uid))") == "((block-uid))"

    def test_block_embed_left_verbatim(self) -> None:
        """Test that a Roam block embed is left unchanged."""
        assert to_pandoc_md("{{embed: ((block-uid))}}") == "{{embed: ((block-uid))}}"

    def test_alias_and_highlight_combined(self) -> None:
        """Test that alias and highlight conversions compose: highlight inside display text becomes a span."""
        # strip_double_brackets runs before convert_highlights, so the [[ produced by
        # [bright]{.mark} inside the link display text is never treated as a page-link delimiter.
        assert to_pandoc_md("[^^bright^^]([[Page]])") == "[[bright]{.mark}](Page)"
