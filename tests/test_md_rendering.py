"""Unit tests for guffin.md_rendering."""

from io import StringIO

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]

from guffin.pandoc_rendering import vertex_tree_to_pandoc

from conftest import FIXTURES_MD_DIR, article0_vertex_tree


class TestRenderArticleFixture:
    """Integration tests for the md_rendering Pandoc output path."""

    def test_article_fixture_renders_to_expected_markdown(self) -> None:
        """Rendering article0 via Pandoc matches the expected CommonMark fixture."""
        doc = vertex_tree_to_pandoc(article0_vertex_tree(), {}, title_in_header=True)
        buf = StringIO()
        pf.dump(doc, output_stream=buf)  # type: ignore[no-untyped-call]
        result = pypandoc.convert_text(  # type: ignore[no-untyped-call]
            buf.getvalue(), "commonmark", format="json", extra_args=["--wrap=none"]
        )
        expected = (FIXTURES_MD_DIR / "test_article_0_expected.md").read_text()
        assert result == expected
