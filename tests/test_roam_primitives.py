"""Tests for the roam_primitives module."""

from guffin.roam_primitives import MediaType


class TestMediaTypeFromFileName:
    """Tests for MediaType.from_file_name classmethod."""

    def test_jpeg_extension_variant(self) -> None:
        """.jpeg resolves to JPEG even though the canonical extension is .jpg."""
        assert MediaType.from_file_name("photo.jpeg") == MediaType.JPEG

    def test_jpg_extension(self) -> None:
        """.jpg resolves to JPEG."""
        assert MediaType.from_file_name("photo.jpg") == MediaType.JPEG

    def test_png(self) -> None:
        """.png resolves to PNG."""
        assert MediaType.from_file_name("image.png") == MediaType.PNG

    def test_unknown_extension_returns_none(self) -> None:
        """An unrecognized extension returns None."""
        assert MediaType.from_file_name("file.xyz") is None


class TestMediaTypeExtension:
    """Tests for MediaType.extension property and MediaType.from_extension classmethod."""

    def test_jpeg(self) -> None:
        """MediaType.JPEG.extension returns .jpg."""
        assert MediaType.JPEG.extension == ".jpg"

    def test_png(self) -> None:
        """MediaType.PNG.extension returns .png."""
        assert MediaType.PNG.extension == ".png"

    def test_gif(self) -> None:
        """MediaType.GIF.extension returns .gif."""
        assert MediaType.GIF.extension == ".gif"

    def test_webp(self) -> None:
        """MediaType.WEBP.extension returns .webp."""
        assert MediaType.WEBP.extension == ".webp"

    def test_svg(self) -> None:
        """MediaType.SVG.extension returns .svg."""
        assert MediaType.SVG.extension == ".svg"

    def test_from_extension_unknown_returns_none(self) -> None:
        """An unrecognized file extension returns None from from_extension."""
        assert MediaType.from_extension(".xyz") is None
