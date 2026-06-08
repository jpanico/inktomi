"""Utilities for producing safe, portable filenames.

Public symbols:

- :func:`shell_safe_filename` — normalize a string to be safe for POSIX
  filenames without shell escaping.
"""

import re
import unicodedata
from typing import Final

from pydantic import validate_call


@validate_call
def shell_safe_filename(text: str) -> str:
    """Normalize a string to be safe for POSIX filenames without shell escaping.

    Converts the string to use only characters that are safe in POSIX filenames
    and don't require escaping in standard Unix shells (bash, zsh, etc.).

    Safe characters: a-z, A-Z, 0-9, underscore (_), hyphen (-), period (.)

    Args:
        text: The string to normalize.

    Returns:
        A normalized string safe for use as a POSIX filename.

    Raises:
        ValidationError: If ``text`` is ``None`` or invalid.
    """
    result: Final[str] = unicodedata.normalize("NFKD", text)
    ascii_result: Final[str] = result.encode("ascii", "ignore").decode("ascii")
    no_spaces: Final[str] = re.sub(r" +", "_", ascii_result)
    safe_chars: Final[str] = re.sub(r"[^a-zA-Z0-9._-]", "", no_spaces)
    collapsed: Final[str] = re.sub(r"_+", "_", safe_chars)
    return collapsed.strip("_")
