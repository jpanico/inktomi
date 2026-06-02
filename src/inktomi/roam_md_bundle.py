r"""Core bundling logic for Roam Research Markdown documents and files.

Provides utilities for finding Cloud Firestore image links in Markdown content,
fetching the images via the Roam Local API, and writing self-contained
``.mdbundle`` directories that contain the updated Markdown and all downloaded
images.

Public symbols:

- :func:`find_markdown_image_links` — find all Cloud Firestore image links in a
  Markdown string; return a list of ``(full_match, url)`` tuples.
- :func:`fetch_and_save_image` — fetch a single image from Cloud Firestore via
  the Local API and write it to a local directory; supports a file-based cache.
- :func:`fetch_all_images` — fetch and save all images from a list of image
  links; collect ``(url, local_filename)`` pairs for later URL replacement.
- :func:`replace_image_links` — replace Cloud Firestore URLs with local
  filenames in a Markdown string.
- :func:`normalize_link_text` — remove line breaks from link text in Markdown
  links.
- :func:`remove_escaped_double_brackets` — strip escaped ``\\[\\[`` / ``\\]\\]``
  bracket pairs from Markdown text (artefacts of Roam's export format).
- :func:`create_bundle_directory` — create the ``.mdbundle`` output directory
  for a Markdown file stem.
- :func:`bundle_md_file` — end-to-end: read a Markdown file from disk, fetch
  its Cloud Firestore images, and write a ``.mdbundle`` directory.
- :func:`bundle_md_document` — end-to-end: accept a Markdown string, fetch its
  Cloud Firestore images, and write a ``.mdbundle`` directory.
"""

import hashlib
import shutil
import unicodedata
import re
import logging
from pathlib import Path
from typing import Final, overload
from pydantic import HttpUrl, validate_call

from inktomi.roam_local_api import ApiEndpoint
from inktomi.roam_asset_fetch import FetchRoamAsset
from inktomi.roam_asset import RoamAsset
from inktomi.roam_primitives import IMAGE_LINK_RE

logger = logging.getLogger(__name__)


@validate_call
def _normalize_for_posix(text: str) -> str:
    """Normalize a string to be safe for POSIX filenames without shell escaping.

    Converts the string to use only characters that are safe in POSIX filenames
    and don't require escaping in standard Unix shells (bash, zsh, etc.).

    Safe characters: a-z, A-Z, 0-9, underscore (_), hyphen (-), period (.)

    Args:
        text: The string to normalize

    Returns:
        A normalized string safe for use as a POSIX filename

    Raises:
        ValidationError: If text is None or invalid
    """
    # 1. Decompose Unicode (e.g., convert 'é' to 'e' + accent)
    result: str = unicodedata.normalize("NFKD", text)
    # 2. Convert to ASCII and ignore non-ascii characters
    result = result.encode("ascii", "ignore").decode("ascii")
    # 3. Replace runs of one or more spaces with a single underscore
    result = re.sub(r" +", "_", result)
    # 4. Remove anything that isn't alphanumeric, underscore, hyphen, or period
    result = re.sub(r"[^a-zA-Z0-9._-]", "", result)
    # 5. Collapse multiple consecutive underscores into a single underscore
    result = re.sub(r"_+", "_", result)
    # 6. Remove leading/trailing underscores
    result = result.strip("_")
    return result


@validate_call
def create_bundle_directory(markdown_file: Path, output_dir: Path) -> Path:
    """Create the .mdbundle directory for the markdown file.

    Args:
        markdown_file: Path to the markdown file being bundled
        output_dir: Parent directory where the .mdbundle folder will be created

    Returns:
        Path to the created bundle directory

    Raises:
        ValidationError: If any parameter is None or invalid
    """
    bundle_dir_stem: Final[str] = _normalize_for_posix(markdown_file.stem)
    # Create bundle directory: <output_dir>/<markdown_file_stem>.mdbundle/
    # Use stem to remove file extension (e.g., "my_notes.md" -> "my_notes")
    bundle_dir_name: Final[str] = f"{bundle_dir_stem}.mdbundle"
    bundle_dir: Final[Path] = output_dir / bundle_dir_name
    bundle_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Created bundle directory: %s", bundle_dir)

    return bundle_dir


@validate_call
def find_markdown_image_links(markdown_text: str) -> list[tuple[str, HttpUrl]]:
    """Find all Markdown image links in the text.

    Args:
        markdown_text: The Markdown content to search

    Returns:
        List of tuples: (full_match, image_url)
        Example: [('![](https://firebase...)', HttpUrl('https://firebase...'))]

    Raises:
        ValidationError: If markdown_text is None or invalid
    """
    matches: Final[list[tuple[str, HttpUrl]]] = []
    for match in IMAGE_LINK_RE.finditer(markdown_text):
        full_match: str = match.group(0)  # Full ![...](...)
        image_url_str: str = match.group("url")  # Just the URL as string
        image_url: HttpUrl = HttpUrl(image_url_str)  # Convert to HttpUrl
        matches.append((full_match, image_url))

    logger.info("Found %d Cloud Firestore image links", len(matches))
    return matches


def _cache_key(firebase_url: HttpUrl) -> str:
    """Compute a SHA-256 hex digest of the Cloud Firestore URL for use as a cache key."""
    return hashlib.sha256(str(firebase_url).encode()).hexdigest()


@validate_call
def fetch_and_save_image(
    api_endpoint: ApiEndpoint,
    firebase_url: HttpUrl,
    output_dir: Path,
    cache_dir: Path | None = None,
) -> tuple[HttpUrl, str]:
    """Fetch an image from Roam and save it locally, using a cache if provided.

    When cache_dir is set, the asset is looked up by a SHA-256 hash of its Cloud Firestore URL.
    On a cache hit the file is copied directly to output_dir without calling the Roam API.
    On a cache miss the file is fetched from the API and stored in both the cache and output_dir.

    Args:
        api_endpoint: The Roam Local API endpoint (URL + bearer token).
        firebase_url: The Cloud Firestore storage URL
        output_dir: Directory where the image should be saved
        cache_dir: Optional directory for caching downloaded assets across runs

    Returns:
        Tuple of (firebase_url, local_file_path)

    Raises:
        ValidationError: If any parameter is None or invalid
        Exception: If fetch or save fails
    """
    # Check the cache first
    if cache_dir is not None:
        key: str = _cache_key(firebase_url)
        cached_files: Final[list[Path]] = list(cache_dir.glob(f"{key}.*"))
        if cached_files:
            cached_file: Final[Path] = cached_files[0]
            dest: Final[Path] = output_dir / cached_file.name
            shutil.copy2(cached_file, dest)
            logger.info("Cache hit for %s -> %s", firebase_url, cached_file.name)
            return (firebase_url, cached_file.name)

    logger.info("Fetching image from: %s", firebase_url)

    # Fetch the file from Roam
    roam_asset: Final[RoamAsset] = FetchRoamAsset.fetch(api_endpoint=api_endpoint, firebase_url=firebase_url)

    # Determine the file name to use in the bundle output directory
    file_name: str = roam_asset.file_name

    # Save to the cache if a cache directory was provided
    if cache_dir is not None:
        key = _cache_key(firebase_url)
        ext: Final[str] = Path(roam_asset.file_name).suffix  # e.g. ".jpeg"
        cache_file_name: Final[str] = f"{key}{ext}"
        cache_path: Final[Path] = cache_dir / cache_file_name
        with open(cache_path, "wb") as f:
            f.write(roam_asset.contents)
        logger.info("Cached asset to: %s", cache_path)
        # Use the cache file name in the bundle so repeated runs produce identical output
        file_name = cache_file_name

    # Save the file to the output directory
    output_path: Final[Path] = output_dir / file_name
    with open(output_path, "wb") as f:
        f.write(roam_asset.contents)

    logger.info("Saved image to: %s", output_path)

    return (firebase_url, file_name)


@overload
def replace_image_links(markdown_text: None, url_replacements: list[tuple[HttpUrl, str]]) -> None: ...


@overload
def replace_image_links(markdown_text: str, url_replacements: list[tuple[HttpUrl, str]]) -> str: ...


@validate_call
def replace_image_links(markdown_text: str | None, url_replacements: list[tuple[HttpUrl, str]]) -> str | None:
    """Replace Cloud Firestore URLs with local file paths in Markdown text.

    Args:
        markdown_text: The original Markdown content (can be None)
        url_replacements: List of (firebase_url, local_filename) tuples

    Returns:
        Updated Markdown text with local file references, or None if markdown_text is None

    Raises:
        ValidationError: If url_replacements is invalid
    """
    # Return None if markdown_text is None
    if markdown_text is None:
        return None

    updated_text: str = markdown_text

    for firebase_url, local_filename in url_replacements:
        # Replace the Cloud Firestore URL with the local filename (convert HttpUrl to string for replacement)
        updated_text = updated_text.replace(str(firebase_url), local_filename)
        logger.info("Replaced %s with %s", firebase_url, local_filename)

    return updated_text


@validate_call
def normalize_link_text(markdown_text: str) -> str:
    """Remove line breaks from link text in Markdown links.

    Markdown links should not have multi-line link text. This function finds all
    Markdown links (both images and regular links) and removes any line breaks
    within the link text portion, replacing them with spaces.

    Args:
        markdown_text: The Markdown content to normalize

    Returns:
        Markdown text with single-line link text

    Raises:
        ValidationError: If markdown_text is None or invalid
    """
    # Pattern to match both image links ![text](url) and regular links [text](url)
    # Captures: optional '!', link text (which may contain newlines), and url
    pattern: Final[str] = r"(!?\[)((?:[^\]]|\n)+?)(\]\([^\)]+\))"

    def replace_newlines(match: re.Match[str]) -> str:
        prefix: Final[str] = match.group(1)  # '![' or '['
        link_text: Final[str] = match.group(2)  # The link text (may have newlines)
        suffix: Final[str] = match.group(3)  # '](url)'

        # Replace newlines in link text with spaces
        normalized_text: Final[str] = re.sub(r"\n+", " ", link_text)

        return f"{prefix}{normalized_text}{suffix}"

    return re.sub(pattern, replace_newlines, markdown_text)


@validate_call
def remove_escaped_double_brackets(markdown_text: str) -> str:
    r"""Remove escaped double brackets from Markdown text.

    Roam Research uses [[page links]] syntax which gets escaped to \\[\\[ and \\]\\]
    when exported. This function removes those escaped brackets.

    Args:
        markdown_text: The Markdown content to process

    Returns:
        Markdown text with escaped double brackets removed

    Raises:
        ValidationError: If markdown_text is None or invalid
    """
    # Remove escaped opening double brackets: \[\[
    text: str = markdown_text.replace(r"\[\[", "")
    # Remove escaped closing double brackets: \]\]
    text = text.replace(r"\]\]", "")
    return text


@validate_call
def fetch_all_images(
    image_links: list[tuple[str, HttpUrl]],
    api_endpoint: ApiEndpoint,
    output_dir: Path,
    cache_dir: Path | None = None,
) -> list[tuple[HttpUrl, str]]:
    """Fetch and save all images from the provided list of image links.

    Args:
        image_links: List of (full_match, firebase_url) tuples
        api_endpoint: The Roam Local API endpoint (URL + bearer token).
        output_dir: Directory where images should be saved
        cache_dir: Optional directory for caching downloaded assets across runs

    Returns:
        List of (firebase_url, local_filename) tuples for successfully fetched images

    Raises:
        ValidationError: If any parameter is None or invalid
    """
    url_replacements: Final[list[tuple[HttpUrl, str]]] = []
    for _, firebase_url in image_links:
        try:
            firebase_url_result, local_filename = fetch_and_save_image(
                api_endpoint, firebase_url, output_dir, cache_dir
            )
            url_replacements.append((firebase_url_result, local_filename))
        except Exception as e:
            logger.error("Failed to fetch %s: %s", firebase_url, e)
            # Continue with other images

    return url_replacements


@validate_call
def bundle_md_file(
    markdown_file: Path,
    local_api_port: int,
    graph_name: str,
    api_bearer_token: str,
    output_dir: Path,
    cache_dir: Path | None = None,
) -> None:
    """Bundle a Markdown file with its referenced images.

    Fetches and saves Cloud Firestore-hosted images, updating image links in the markdown file
    to use local file references in place of Cloud Firestore URLs.

    Creates a .mdbundle directory named <markdown_file>.mdbundle/ in the output_dir,
    containing the updated markdown file and all downloaded images.

    Args:
        markdown_file: Path to the Markdown file
        local_api_port: Port for Roam Local API
        graph_name: Name of the Roam graph
        api_bearer_token: The bearer token for authenticating with the Roam Local API
        output_dir: Parent directory where the .mdbundle folder will be created
        cache_dir: Optional directory for caching downloaded assets across runs

    Raises:
        ValidationError: If any parameter is None or invalid
        FileNotFoundError: If markdown file doesn't exist
        Exception: If processing fails
    """
    if not markdown_file.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_file}")

    bundle_dir: Final[Path] = create_bundle_directory(markdown_file, output_dir)

    logger.info("Processing Markdown file: %s", markdown_file)

    # Read the Markdown file
    markdown_text: Final[str] = markdown_file.read_text(encoding="utf-8")

    # Find all image links
    image_links: Final[list[tuple[str, HttpUrl]]] = find_markdown_image_links(markdown_text)

    if not image_links:
        logger.info("No Cloud Firestore image links found in the file")
        return

    # Create API endpoint
    api_endpoint: Final[ApiEndpoint] = ApiEndpoint.from_parts(
        local_api_port=local_api_port, graph_name=graph_name, bearer_token=api_bearer_token
    )

    # Fetch and save all images to the bundle directory
    url_replacements: Final[list[tuple[HttpUrl, str]]] = fetch_all_images(
        image_links, api_endpoint, bundle_dir, cache_dir
    )

    # Replace URLs in the Markdown text
    if url_replacements:
        updated_text: str = replace_image_links(markdown_text, url_replacements)

        # Normalize link text to remove line breaks
        updated_text = normalize_link_text(updated_text)

        # Remove escaped double brackets from Roam page links
        updated_text = remove_escaped_double_brackets(updated_text)

        # Write the updated Markdown file to the bundle directory
        output_file: Final[Path] = bundle_dir / f"{bundle_dir.stem}.md"
        output_file.write_text(updated_text, encoding="utf-8")
        logger.info("Wrote updated Markdown to: %s", output_file)
        logger.info("Successfully processed %d images", len(url_replacements))
    else:
        logger.warning("No images were successfully fetched")


@validate_call
def bundle_md_document(
    md_text: str,
    document_name: str,
    output_dir: Path,
    api_endpoint: ApiEndpoint,
    cache_dir: Path | None = None,
) -> None:
    """Bundle a Markdown document string with its referenced Cloud Firestore images.

    Accepts the Markdown content as a string rather than reading from a file on disk.
    Fetches and saves Cloud Firestore-hosted images found in the text, rewrites the image
    links to use local filenames, and writes the updated document into a new
    ``<document_name>.mdbundle/`` directory inside ``output_dir``.

    Args:
        md_text: The Markdown content to bundle.
        document_name: Name used to derive the bundle directory and output filename
            (e.g. a Roam page title). POSIX-normalized before use.
        output_dir: Parent directory where the ``.mdbundle`` folder will be created.
        api_endpoint: The Roam Local API endpoint (URL + bearer token).
        cache_dir: Optional directory for caching downloaded assets across runs.

    Raises:
        ValidationError: If any parameter is ``None`` or fails Pydantic validation.
        Exception: If image fetching or writing fails.
    """
    bundle_dir_stem: Final[str] = _normalize_for_posix(document_name)
    bundle_dir_name: Final[str] = f"{bundle_dir_stem}.mdbundle"
    bundle_dir: Final[Path] = output_dir / bundle_dir_name
    bundle_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Created bundle directory: %s", bundle_dir)

    image_links: Final[list[tuple[str, HttpUrl]]] = find_markdown_image_links(md_text)

    md_to_write: str = md_text
    if image_links:
        url_replacements: Final[list[tuple[HttpUrl, str]]] = fetch_all_images(
            image_links, api_endpoint, bundle_dir, cache_dir
        )
        if url_replacements:
            md_to_write = replace_image_links(md_text, url_replacements)
            logger.info("Successfully processed %d images", len(url_replacements))
        else:
            logger.warning("No images were successfully fetched")
    else:
        logger.info("No Cloud Firestore image links found in the document")

    output_file: Final[Path] = bundle_dir / f"{bundle_dir_stem}.md"
    output_file.write_text(md_to_write, encoding="utf-8")
    logger.info("Wrote Markdown to: %s", output_file)
