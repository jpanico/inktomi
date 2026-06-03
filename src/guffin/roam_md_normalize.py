"""Normalize Roam flavored Markdown to CommonMark.

Roam Research uses a Markdown dialect ("Roamdown") that diverges from CommonMark
in several ways.  This module provides functions that transform a single Roam block
string into a CommonMark-compatible string.  See ``docs/roam-md.md`` for a full
description of the differences.

The normalization functions operate on plain Python strings (one block string at a
time) and are stateless and side-effect-free.  They are designed to be composed via
:func:`normalize`, which applies every transformation in a defined, stable order.

Public symbols:

- :func:`normalize` — apply all normalizations to a Roam block string and return the
  CommonMark result.
- :func:`normalize_italics` — convert ``__italic__`` → ``*italic*``.
- :func:`strip_square_brackets` — remove all ``[`` and ``]`` characters (strips
  page-link, tag, and alias bracket scaffolding).
"""

import re

# ---------------------------------------------------------------------------
# Module-level compiled patterns
# ---------------------------------------------------------------------------

# Roam italic: __text__ (double underscores).  Must not match bold (**text**).
# Negative look-behind/ahead prevents matching inside bold markers.
_ITALIC_RE: re.Pattern[str] = re.compile(r"(?<!\w)__(?!\s)(.+?)(?<!\s)__(?!\w)", re.DOTALL)

# All square-bracket characters — used to strip Roam page-link and alias bracket
# scaffolding (e.g. [[Page Name]], #[[tag]], [text]([[link]])) leaving only the
# inner text.
_SQUARE_BRACKET_RE: re.Pattern[str] = re.compile(r"[\[\]]")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize(roam_string: str) -> str:
    """Apply all Roam-to-CommonMark normalizations to *roam_string*.

    Transformations are applied in a fixed order designed to avoid
    double-substitution artefacts.  Each individual normalization is also
    available as a standalone function for testing or selective use.

    Args:
        roam_string: A single Roam block string (the raw ``string`` field from a
            :class:`~guffin.roam_node.RoamNode`).

    Returns:
        The normalized CommonMark string.
    """
    result: str = roam_string
    result = normalize_italics(result)
    result = strip_square_brackets(result)
    return result


def normalize_italics(roam_string: str) -> str:
    """Convert Roam italic syntax to CommonMark italic syntax.

    Roam uses ``__double underscores__`` for italics; CommonMark uses
    ``*single asterisks*``.  This function replaces every ``__text__``
    span with ``*text*``.

    Args:
        roam_string: A Roam block string, possibly containing ``__italic__`` spans.

    Returns:
        The string with all ``__italic__`` spans replaced by ``*italic*``.
    """
    return _ITALIC_RE.sub(r"*\1*", roam_string)


def strip_square_brackets(roam_string: str) -> str:
    """Remove all square-bracket characters from *roam_string*.

    Strips every ``[`` and ``]`` character, including those from nested
    constructs such as ``[[Page Name]]``, ``#[[multi-word tag]]``, and
    ``[display text]([[Page Name]])``, leaving only the inner text.

    Examples::

        strip_square_brackets("[[Page Name]]")          # → "Page Name"
        strip_square_brackets("[[nested [[pages]]]]")   # → "nested pages"
        strip_square_brackets("#[[multi-word tag]]")    # → "#multi-word tag"

    Args:
        roam_string: A Roam block string, possibly containing square-bracket
            constructs.

    Returns:
        The string with all ``[`` and ``]`` characters removed.
    """
    return _SQUARE_BRACKET_RE.sub("", roam_string)
