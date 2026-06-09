"""Unit tests for guffin.render.md_rendering."""

from io import StringIO

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]

from guffin.render.md_rendering import _GFM_CALLOUT_FILTER
from guffin.render.pandoc_rendering import vertex_tree_to_pandoc

from conftest import FIXTURES_MD_DIR, article1_vertex_tree


class TestRenderArticleFixture:
    """Integration tests for the md_rendering Pandoc output path."""

    def test_article_fixture_renders_to_expected_markdown(self) -> None:
        """Rendering article1 via Pandoc with the GFM callout filter matches the expected fixture."""
        doc = vertex_tree_to_pandoc(article1_vertex_tree(), {}, title_in_header=True)
        buf = StringIO()
        pf.dump(doc, output_stream=buf)  # type: ignore[no-untyped-call]
        result = pypandoc.convert_text(  # type: ignore[no-untyped-call]
            buf.getvalue(),
            "gfm",
            format="json",
            extra_args=["--wrap=none", f"--lua-filter={_GFM_CALLOUT_FILTER}"],
        )
        expected = (FIXTURES_MD_DIR / "test_article_1_expected.md").read_text()
        assert result == expected
