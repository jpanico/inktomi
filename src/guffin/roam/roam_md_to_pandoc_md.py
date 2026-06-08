"""Normalize Roam flavored Markdown to Pandoc Markdown.

Roam Research uses a Markdown dialect ("Roamdown") that diverges from standard
Markdown in several ways.  This module transforms a single Roam block string into
a Pandoc Markdown-compatible string.  See ``docs/roam-md.md`` for a full
description of the differences.

The conversion functions operate on plain Python strings (one block string at a
time) and are stateless and side-effect-free.  They are designed to be composed
via :func:`to_pandoc_md`, which applies every transformation in a defined,
stable order.

Constructs intentionally left verbatim for future expansion:

- Block references — ``((block-uid))``
- Block embeds — ``{{embed: ((block-uid))}}``
- Other Roam components — ``{{TODO}}``, ``{{DONE}}``, ``{{query: ...}}``, etc.

Public symbols:

- :func:`to_pandoc_md` — apply all conversions to a Roam block string and
  return the Pandoc Markdown result.
- :func:`convert_italics` — convert ``__italic__`` → ``*italic*``.
- :func:`convert_highlights` — convert ``^^text^^`` → ``[text]{.mark}``.
- :func:`convert_page_link_aliases` — convert ``[display]([[Page Name]])``
  → ``[display](Page Name)``.
- :func:`strip_double_brackets` — remove ``[[`` and ``]]`` delimiters, leaving
  the inner text (e.g. ``[[Page Name]]`` → ``Page Name``).
"""

import re

from pydantic import validate_call

# ---------------------------------------------------------------------------
# Module-level compiled patterns
# ---------------------------------------------------------------------------

# Roam italic: __text__ (double underscores).  Must not match bold (**text**).
# Negative look-behind/ahead prevents matching inside bold markers.
_ITALIC_RE: re.Pattern[str] = re.compile(r"(?<!\w)__(?!\s)(.+?)(?<!\s)__(?!\w)", re.DOTALL)

# Roam highlight: ^^text^^.  Converted to a Pandoc bracketed span with class
# "mark" via the bracketed_spans extension (enabled by default in Pandoc Markdown).
_HIGHLIGHT_RE: re.Pattern[str] = re.compile(r"\^\^(.+?)\^\^", re.DOTALL)

# Roam alias to a page link: [display text]([[Page Name]]).  Capture group 1 is
# the display text (no square brackets); group 2 is the page name (no square
# brackets).  Must be applied before strip_double_brackets so the [[...]] target
# can be identified and converted to a plain Pandoc Markdown link destination.
_PAGE_LINK_ALIAS_RE: re.Pattern[str] = re.compile(r"\[([^\[\]]+)\]\(\[\[([^\[\]]*)\]\]\)")

# Double-bracket delimiters used by Roam for page links ([[Page Name]]) and
# hashtag page links (#[[multi-word tag]]).  Matched and removed independently
# to handle arbitrarily nested page links (e.g. [[nested [[pages]]]]).
_DOUBLE_OPEN_RE: re.Pattern[str] = re.compile(r"\[\[")
_DOUBLE_CLOSE_RE: re.Pattern[str] = re.compile(r"\]\]")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@validate_call
def to_pandoc_md(roam_string: str) -> str:
    """Convert a Roam block string to Pandoc Markdown by applying all transformations.

    Transformations are applied in a fixed order designed to avoid
    double-substitution artefacts.  Each individual conversion is also
    available as a standalone function for testing or selective use.

    The following Roam constructs are intentionally left verbatim for future
    expansion: block references ``((uid))``, block embeds
    ``{{embed: ((uid))}}``, and other ``{{…}}`` components.

    Args:
        roam_string: A single Roam block string (the raw ``string`` field from a
            :class:`~guffin.roam.roam_node.RoamNode`).

    Returns:
        The Pandoc Markdown string.
    """
    result: str = roam_string
    result = convert_page_link_aliases(result)
    result = strip_double_brackets(result)
    result = convert_italics(result)
    result = convert_highlights(result)
    return result


@validate_call
def convert_italics(roam_string: str) -> str:
    """Convert Roam italic syntax to Pandoc Markdown italic syntax.

    Roam uses ``__double underscores__`` for italics; Pandoc Markdown uses
    ``*single asterisks*``.  This function replaces every ``__text__`` span
    with ``*text*``.

    Args:
        roam_string: A Roam block string, possibly containing ``__italic__`` spans.

    Returns:
        The string with all ``__italic__`` spans replaced by ``*italic*``.
    """
    return _ITALIC_RE.sub(r"*\1*", roam_string)


@validate_call
def convert_highlights(roam_string: str) -> str:
    """Convert Roam highlight syntax to a Pandoc Markdown bracketed span.

    Roam uses ``^^text^^`` for background highlights.  Pandoc Markdown
    represents this as ``[text]{.mark}`` via the ``bracketed_spans`` extension
    (enabled by default in Pandoc Markdown), which maps to a ``Span`` AST node
    with class ``mark``.

    Args:
        roam_string: A Roam block string, possibly containing ``^^highlight^^`` spans.

    Returns:
        The string with all ``^^text^^`` spans replaced by ``[text]{.mark}``.
    """
    return _HIGHLIGHT_RE.sub(r"[\1]{.mark}", roam_string)


@validate_call
def convert_page_link_aliases(roam_string: str) -> str:
    """Convert Roam page-link aliases to Pandoc Markdown inline links.

    Roam supports ``[display text]([[Page Name]])`` to create an aliased link
    to a page.  This function converts each such construct to the Pandoc
    Markdown inline link ``[display text](Page Name)``, removing the
    ``[[``/``]]`` delimiters and using the page name as the link destination.

    Must be applied before :func:`strip_double_brackets` so that the ``[[…]]``
    target is identified and converted rather than blindly stripped.

    Args:
        roam_string: A Roam block string, possibly containing alias patterns.

    Returns:
        The string with all ``[display]([[Page Name]])`` patterns replaced by
        ``[display](Page Name)``.
    """
    return _PAGE_LINK_ALIAS_RE.sub(r"[\1](\2)", roam_string)


@validate_call
def strip_double_brackets(roam_string: str) -> str:
    """Remove ``[[`` and ``]]`` delimiters from *roam_string*, leaving inner text.

    Handles Roam page links (``[[Page Name]]``), hashtag page links
    (``#[[multi-word tag]]``), and arbitrarily nested page links
    (``[[nested [[pages]]]]``) by independently removing all ``[[`` and ``]]``
    occurrences.  Single square brackets ``[`` and ``]`` are intentionally
    preserved, as they carry meaning in Pandoc Markdown (link labels, bracketed
    spans, etc.).

    Examples::

        strip_double_brackets("[[Page Name]]")         # → "Page Name"
        strip_double_brackets("[[nested [[pages]]]]")  # → "nested pages"
        strip_double_brackets("#[[multi-word tag]]")   # → "#multi-word tag"
        strip_double_brackets("[text]")                # → "[text]"

    Args:
        roam_string: A Roam block string, possibly containing ``[[…]]`` constructs.

    Returns:
        The string with all ``[[`` and ``]]`` occurrences removed.
    """
    result: str = _DOUBLE_OPEN_RE.sub("", roam_string)
    result = _DOUBLE_CLOSE_RE.sub("", result)
    return result
