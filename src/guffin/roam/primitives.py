"""Foundational Roam Research primitives: type aliases, stub models, and pattern constants.

Public symbols are organized into five groups:

- **Primitive type aliases**: :data:`Uid`, :data:`Id`, :data:`Order`, :data:`HeadingLevel`,
  :data:`PageTitle`, :data:`Url`.
- **Composite type aliases**: :data:`UidPair`, :data:`RawChildren`, :data:`RawRefs`.
- **Stub models**: :class:`IdObject`, :class:`LinkObject`.
- **Pattern constants**: :data:`UID_PATTERN` — raw regex string for a Roam node UID;
  :data:`UID_RE` — compiled form; :data:`ROAM_BLOCK_QUOTE_PREFIX` — string prefix for a
  Roam block quote (and callout); :data:`CALLOUT_RE` — compiled regex that matches and
  decomposes a full callout block string; :data:`MD_BLOCK_QUOTE_PREFIX` — string prefix for a standard
  Markdown blockquote line; :data:`IMAGE_LINK_RE` — compiled regex matching a Roam markdown
  image link whose URL is a Cloud Firestore storage URL.
- **Enumerations**: :class:`CalloutType` — the twelve Roam callout type keywords.
- **Callout model**: :class:`RoamCallout` — parsed decomposition of a callout block string.
- **Callout parser**: :func:`parse_callout` — parse a raw block string as a :class:`RoamCallout`.
- **Block-quote predicate**: :func:`is_roam_block_quote` — return ``True`` when a string is a
  Roam or standard Markdown block quote.
- **Block-quote marker stripper**: :func:`strip_block_quote_marker` — strip the leading block-quote
  marker from a block-quote string and return the remaining content.
"""

import enum
import re
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, validate_call

UID_PATTERN: Final[str] = r"^[A-Za-z0-9_-]{9}$"
"""Raw regex pattern string for a Roam node UID: exactly 9 alphanumeric/dash/underscore characters."""

UID_RE: Final[re.Pattern[str]] = re.compile(UID_PATTERN)
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


class CalloutType(enum.StrEnum):
    """The twelve Roam callout type keywords as they appear in the raw block string marker.

    The marker format is ``[[>]] [[!<TYPE>]]`` where ``<TYPE>`` is one of these values
    (always uppercase in the Roam source).

    These map one-to-one to the lowercase :class:`~guffin.vertex.CalloutVertex.CalloutType`
    values in the export model; convert with ``CalloutVertex.CalloutType(member.lower())``.
    """

    INFO = "INFO"
    QUOTE = "QUOTE"
    EXAMPLE = "EXAMPLE"
    NOTE = "NOTE"
    WARNING = "WARNING"
    DANGER = "DANGER"
    TIP = "TIP"
    SUMMARY = "SUMMARY"
    SUCCESS = "SUCCESS"
    QUESTION = "QUESTION"
    FAILURE = "FAILURE"
    BUG = "BUG"


ROAM_BLOCK_QUOTE_PREFIX: Final[str] = "[[>]]"
"""String prefix for a Roam block quote (and by extension, a Roam callout).

In Roam's Markdown model ``[[>]]`` is the block-quote marker; callouts are a
styled subtype of block quote whose marker is ``[[>]] [[!<TYPE>]]``.  Used as
a fast pre-filter before applying :data:`CALLOUT_RE` and by
:func:`is_roam_block_quote`.
"""

MD_BLOCK_QUOTE_PREFIX: Final[str] = ">"
"""String prefix that identifies a standard CommonMark blockquote line.

A line beginning with ``>`` (optionally followed by a space) is a CommonMark
block quote marker.  Used by :func:`is_roam_block_quote`.
"""

CALLOUT_RE: Final[re.Pattern[str]] = re.compile(
    rf"(?P<prefix>{re.escape(ROAM_BLOCK_QUOTE_PREFIX)})"
    rf" \[\[!(?P<callout_type>{'|'.join(ct.value for ct in CalloutType)})\]\]"
    r"\s*(?P<title>[^\n]*)(?:\n(?P<body>.*))?",
    re.DOTALL,
)
"""Compiled regex matching and decomposing a full Roam callout block string.

Named groups:

- ``prefix`` — the literal ``[[>]]`` opener.
- ``callout_type`` — one of the twelve recognised type keywords (``INFO``, ``QUOTE``,
  ``EXAMPLE``, ``NOTE``, ``WARNING``, ``DANGER``, ``TIP``, ``SUMMARY``, ``SUCCESS``,
  ``QUESTION``, ``FAILURE``, ``BUG``).
- ``title`` — the remainder of the first line after the marker and any intervening
  whitespace; may be an empty string when no title text is present.
- ``body`` — everything after the first newline; ``None`` when the string contains no
  newline.  ``re.DOTALL`` is set so ``.`` matches embedded newlines within the body.
"""


class RoamCallout(BaseModel):
    """Parsed decomposition of a callout block string.

    Captures the three semantic components extracted from the raw block string
    by :data:`CALLOUT_RE`.

    Attributes:
        callout_type: Callout category keyword from the ``[[>]] [[!<TYPE>]]`` marker.
        title: Callout heading text — the remainder of the first line after the marker.
        body: Callout body text — everything after the first newline in the block string;
            empty string when absent.
    """

    model_config = ConfigDict(frozen=True)

    callout_type: CalloutType = Field(..., description="Callout category keyword from the [[>]] [[!<TYPE>]] marker.")
    title: str = Field(..., description="Callout heading text — the remainder of the first line after the marker.")
    body: str = Field(
        ..., description="Callout body text — everything after the first newline; empty string when absent."
    )


@validate_call
def parse_callout(block_string: str) -> RoamCallout | None:
    """Parse *block_string* as a :class:`RoamCallout`, or return ``None`` if it is not a callout.

    Returns ``None`` when *block_string* does not start with :data:`ROAM_BLOCK_QUOTE_PREFIX`.

    Args:
        block_string: The raw block string to parse.

    Returns:
        A :class:`RoamCallout` when *block_string* matches :data:`CALLOUT_RE`; ``None`` otherwise.
        The ``body`` field is an empty string when *block_string* contains no newline.

    Raises:
        ValueError: When *block_string* starts with :data:`ROAM_BLOCK_QUOTE_PREFIX` but does not match
            :data:`CALLOUT_RE` (malformed callout marker).
    """
    if not block_string.startswith(ROAM_BLOCK_QUOTE_PREFIX):
        return None
    m: Final[re.Match[str] | None] = CALLOUT_RE.match(block_string)
    if m is None:
        raise ValueError(
            f"block string starts with {ROAM_BLOCK_QUOTE_PREFIX!r} " f"but does not match callout pattern; got {block_string!r}"
        )
    return RoamCallout(
        callout_type=CalloutType(m.group("callout_type")),
        title=m.group("title"),
        body=m.group("body") or "",
    )


@validate_call
def is_roam_block_quote(block_string: str) -> bool:
    """Return ``True`` if *block_string* is a Roam or standard Markdown block quote.

    Recognises two forms:

    - **Standard Markdown**: *block_string* starts with :data:`MD_BLOCK_QUOTE_PREFIX` (``>``).
    - **Roam-specific**: *block_string* starts with :data:`ROAM_BLOCK_QUOTE_PREFIX` (``[[>]]``) but does
      not match :data:`CALLOUT_RE` — i.e. a plain ``[[>]]``-prefixed blockquote rather
      than a typed callout.

    Args:
        block_string: The string to test.

    Returns:
        ``True`` when *block_string* matches either the standard or Roam blockquote form.
    """
    if block_string.startswith(ROAM_BLOCK_QUOTE_PREFIX):
        return not CALLOUT_RE.match(block_string)
    return block_string.startswith(MD_BLOCK_QUOTE_PREFIX)


@validate_call
def strip_block_quote_marker(block_string: str) -> str:
    """Strip the leading block-quote marker from *block_string* and return the remaining content.

    Strips :data:`ROAM_BLOCK_QUOTE_PREFIX` (``[[>]]``) for Roam-style block quotes or
    :data:`MD_BLOCK_QUOTE_PREFIX` (``>``) for standard Markdown block quotes, then
    strips any leading whitespace from the remainder.

    Args:
        block_string: A block-quote string as recognised by :func:`is_roam_block_quote`.

    Returns:
        The content of the block quote with the leading marker and any intervening
        whitespace removed.

    Raises:
        ValueError: If *block_string* is not a block quote according to
            :func:`is_roam_block_quote`.
    """
    if not is_roam_block_quote(block_string):
        raise ValueError(f"string is not a block quote: {block_string!r}")
    prefix: Final[str] = ROAM_BLOCK_QUOTE_PREFIX if block_string.startswith(ROAM_BLOCK_QUOTE_PREFIX) else MD_BLOCK_QUOTE_PREFIX
    return block_string[len(prefix) :].lstrip()


IMAGE_LINK_RE: Final[re.Pattern[str]] = re.compile(
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
