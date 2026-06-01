"""Foundational Roam Research primitives: type aliases, stub models, and pattern constants.

Public symbols are organized into four groups:

- **Primitive type aliases**: :data:`Uid`, :data:`Id`, :data:`Order`, :data:`HeadingLevel`,
  :data:`PageTitle`, :data:`Url`, :data:`MediaType`.
- **Composite type aliases**: :data:`UidPair`, :data:`RawChildren`, :data:`RawRefs`.
- **Stub models**: :class:`IdObject`, :class:`LinkObject`.
- **Pattern constants**: :data:`UID_PATTERN` — raw regex string for a Roam node UID;
  :data:`UID_RE` — compiled form; :data:`IMAGE_LINK_RE` — compiled regex matching a Roam
  markdown image link whose URL is a Cloud Firestore storage URL.
"""

import logging
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

logger = logging.getLogger(__name__)

UID_PATTERN: str = r"^[A-Za-z0-9_-]{9}$"
"""Raw regex pattern string for a Roam node UID: exactly 9 alphanumeric/dash/underscore characters."""

UID_RE: re.Pattern[str] = re.compile(UID_PATTERN)
"""Compiled regex for matching a Roam node UID."""

type Uid = Annotated[str, Field(pattern=UID_PATTERN)]
"""Nine-character alphanumeric stable block/page identifier (:block/uid)."""

type Id = int
"""Datomic internal numeric entity id (:db/id).

Ephemeral — not stable across exports.
"""

type Order = Annotated[int, Field(ge=0)]
"""Zero-based position of a child block among its siblings (:block/order)."""

type HeadingLevel = Annotated[int, Field(ge=1, le=6)]
"""Markdown heading level 1–6 (:block/heading).

Absent (None) on non-heading blocks.
"""

type PageTitle = Annotated[str, Field(min_length=1)]
"""Page title string (:node/title).

Only present on page entities.
"""

type Url = HttpUrl
"""A validated HTTP/HTTPS URL (e.g. a Cloud Firestore storage URL for a Roam-managed file)."""

type MediaType = Annotated[str, Field(pattern=r"^[\w-]+/[\w-]+$")]
"""IANA media type (MIME type) string, e.g. ``"image/jpeg"``.

Must match the pattern ``<type>/<subtype>`` where both components consist of
word characters and hyphens (e.g. ``"image/jpeg"``, ``"application/pdf"``).

References:
  - https://en.wikipedia.org/wiki/Media_type
  - https://www.iana.org/assignments/media-types/media-types.xhtml
"""

type UidPair = tuple[Literal["uid"], Uid]
"""A two-element tuple ``('uid', <uid-value>)`` used as a Datomic :entity/attrs source or value."""


class IdObject(BaseModel):
    """A thin wrapper carrying only a Datomic entity id.

    This is the stub shape returned by ``pull [*]`` for nested refs
    (e.g. ``:block/children``, ``:block/refs``, ``:block/page``).

    Attributes:
        id: The Datomic internal numeric entity id (:db/id).
    """

    model_config = ConfigDict(frozen=True)

    id: Id = Field(..., description="Datomic internal numeric entity id (:db/id)")


class LinkObject(BaseModel):
    """A :entity/attrs link entry, representing a typed attribute assertion.

    Each entry in a ``:entity/attrs`` value is a ``LinkObject`` carrying a
    source UidPair (the attribute identity) and a value UidPair (the asserted
    value).

    Attributes:
        source: ``('uid', <attr-uid>)`` — the attribute being asserted.
        value: ``('uid', <value-uid>)`` — the value of the assertion.
    """

    model_config = ConfigDict(frozen=True)

    source: UidPair = Field(..., description="Attribute identity as a ('uid', uid) pair")
    value: UidPair = Field(..., description="Asserted value as a ('uid', uid) pair")


type RawChildren = list[IdObject]
"""Child block stubs as returned directly by ``pull [*]``.

Each element is an :class:`IdObject` carrying only a ``:db/id``; full block data
is resolved during the normalization pass.
"""

type RawRefs = list[IdObject]
"""Page/block reference stubs as returned directly by ``pull [*]``.

Same shape as :data:`RawChildren` — :class:`IdObject` stubs awaiting normalization.
"""

IMAGE_LINK_RE: re.Pattern[str] = re.compile(
    r"!\[(?P<alt>(?:[^\]]|\n)*?)\]\((?P<url>https://firebasestorage\.googleapis\.com/[^\)]+)\)"
)
"""Compiled regex matching a Roam markdown image link whose URL is a Cloud Firestore storage URL.

Named groups:

- ``alt`` — the alt-text content between ``[`` and ``]`` (may be empty or multi-line).
- ``url`` — the Cloud Firestore storage URL between ``(`` and ``)``.

Example match on ``![my photo](https://firebasestorage.googleapis.com/v0/b/...)``:

- ``match.group(0)`` — the full ``![...](..)`` string.
- ``match.group("url")`` — just the URL.
- ``match.group("alt")`` — just the alt text.
"""
