"""Tests for graph module utility functions."""

from guffin.graph import ImageVertex, PageVertex, TextContentVertex, VertexTree, image_urls, image_vertices, root_vertex

from conftest import article0_vertex_tree

_URL_A = "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/imgs%2Fa.jpeg?alt=media&token=aaa"
_URL_B = "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/imgs%2Fb.jpeg?alt=media&token=bbb"

_ARTICLE_IMAGE_URL = (
    "https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com"
    "/o/imgs%2Fapp%2FSCFH%2F-9owRBegJ8.jpeg.enc?alt=media&token=9b673aae-8089-4a91-84df-9dac152a7f94"
)


def _page(uid: str = "pageuid01") -> PageVertex:
    return PageVertex(uid=uid, title="Page")


def _image(uid: str = "imguid001", url: str = _URL_A) -> ImageVertex:
    return ImageVertex(uid=uid, source=url)  # type: ignore[arg-type]


def _text(uid: str = "textuid01") -> TextContentVertex:
    return TextContentVertex(uid=uid, text="hello")


# ---------------------------------------------------------------------------
# TestImageVertices
# ---------------------------------------------------------------------------


class TestImageVertices:
    """Tests for image_vertices()."""

    def test_returns_only_image_vertices(self) -> None:
        """Mixed tree — only the ImageVertex is returned."""
        tree = VertexTree(vertices=[_page(), _image("imguid001")])
        result = image_vertices(tree)
        assert len(result) == 1
        assert result[0].uid == "imguid001"

    def test_returns_empty_list_when_no_images(self) -> None:
        """Tree with no images returns an empty list."""
        tree = VertexTree(vertices=[_page()])
        assert image_vertices(tree) == []

    def test_preserves_insertion_order(self) -> None:
        """Multiple image vertices are returned in insertion order."""
        tree = VertexTree(vertices=[_page(), _image("imguid001", _URL_A), _image("imguid002", _URL_B)])
        result = image_vertices(tree)
        assert [v.uid for v in result] == ["imguid001", "imguid002"]

    def test_article_fixture_has_one_image_vertex(self) -> None:
        """Test Article 0 fixture contains exactly one image vertex."""
        result = image_vertices(article0_vertex_tree())
        assert len(result) == 1
        assert isinstance(result[0], ImageVertex)


# ---------------------------------------------------------------------------
# TestImageUrls
# ---------------------------------------------------------------------------


class TestImageUrls:
    """Tests for image_urls()."""

    def test_returns_source_urls(self) -> None:
        """Returns the source URL of each image vertex."""
        tree = VertexTree(vertices=[_page(), _image("imguid001", _URL_A), _image("imguid002", _URL_B)])
        result = image_urls(tree)
        assert [str(u) for u in result] == [_URL_A, _URL_B]

    def test_returns_empty_list_when_no_images(self) -> None:
        """Tree with no images returns an empty list."""
        tree = VertexTree(vertices=[_page()])
        assert image_urls(tree) == []

    def test_article_fixture_image_url(self) -> None:
        """Test Article 0 fixture image URL matches the known fixture value."""
        urls = image_urls(article0_vertex_tree())
        assert len(urls) == 1
        assert str(urls[0]) == _ARTICLE_IMAGE_URL


# ---------------------------------------------------------------------------
# TestRootVertex
# ---------------------------------------------------------------------------


class TestRootVertex:
    """Tests for root_vertex()."""

    def test_single_vertex_is_root(self) -> None:
        """A tree with one vertex returns that vertex as root."""
        page = _page()
        tree = VertexTree(vertices=[page])
        assert root_vertex(tree) == page

    def test_returns_vertex_with_no_parent(self) -> None:
        """Root is the vertex whose uid does not appear in any children list."""
        page = _page(uid="pageuid01")
        child = _text(uid="textuid01")
        tree = VertexTree(vertices=[PageVertex(uid="pageuid01", title="Page", children=["textuid01"]), child])
        assert root_vertex(tree).uid == "pageuid01"

    def test_non_root_is_not_returned(self) -> None:
        """A child vertex is never returned as root."""
        page = PageVertex(uid="pageuid01", title="Page", children=["textuid01"])
        child = _text(uid="textuid01")
        tree = VertexTree(vertices=[page, child])
        assert root_vertex(tree).uid != "textuid01"

    def test_article_fixture_root_is_page_vertex(self) -> None:
        """Test Article 0 fixture root is a PageVertex."""
        assert isinstance(root_vertex(article0_vertex_tree()), PageVertex)
