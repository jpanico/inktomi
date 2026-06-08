"""Roam Research asset data model.

Public symbols:

- :class:`RoamAsset` — immutable representation of an asset fetched from Cloud Firestore
  through the Roam API.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from guffin.common.media_type import MediaType


class RoamAsset(BaseModel):
    """Immutable representation of an asset fetched from Cloud Firestore through the Roam API.

    Roam uploads all user assets (files, media) to Cloud Firestore, and stores only Cloud Firestore
    locators (URLs) within the Roam graph DB itself (nodes).

    Once created, instances cannot be modified (frozen). All fields are required
    and validated at construction time.
    """

    model_config = ConfigDict(frozen=True)

    file_name: str = Field(..., min_length=1, description="Name of the file")
    last_modified: datetime = Field(..., description="Last modification timestamp")
    media_type: MediaType = Field(..., description="MIME type (e.g., 'image/jpeg')")
    contents: bytes = Field(..., description="Binary file contents")
