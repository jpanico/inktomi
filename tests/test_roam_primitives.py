"""Tests for the roam_primitives module."""

from guffin.roam_primitives import MediaType


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
