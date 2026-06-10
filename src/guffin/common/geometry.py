"""Generic two-dimensional geometry types.

Public symbols:

- :class:`ImageSize` — pixel dimensions (width × height) of a two-dimensional image.
"""

from pydantic import BaseModel, ConfigDict


class ImageSize(BaseModel):
    """Pixel dimensions of a two-dimensional image.

    Both axes are optional because either dimension may be unknown or unset.

    Attributes:
        width: Pixel width of the image, or ``None`` if not recorded.
        height: Pixel height of the image, or ``None`` if not recorded.
    """

    model_config = ConfigDict(frozen=True)

    width: int | None = None
    height: int | None = None
