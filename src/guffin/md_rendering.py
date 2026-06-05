r"""Render a :class:`~guffin.graph.VertexTree` to CommonMark and write Markdown exports to disk.

Converts the normalized vertex tree produced by
:func:`~guffin.roam_transcribe.transcribe` into a CommonMark string, and
provides the full pipeline for writing that string to disk as either a plain
``.md`` file or a self-contained ``.mdbundle`` directory that embeds downloaded
Cloud Firestore images.

Rendering rules:

- :class:`~guffin.graph.PageVertex` — rendered as an H1 heading
  (``# title``).
- :class:`~guffin.graph.HeadingVertex` — rendered as a CommonMark
  heading at the vertex's recorded level (``#`` … ``######``).
- :class:`~guffin.graph.TextContentVertex` — direct children of the
  page (depth 1) are rendered as paragraphs; deeper vertices are rendered as
  indented bullet-list items (``- text``, ``  - text``, …).
- :class:`~guffin.graph.ImageVertex` — rendered as a CommonMark image
  link (``![alt](url)``).

Public symbols:

- :func:`vertex_tree_to_md` — render a :class:`~guffin.graph.VertexTree` to a
  CommonMark document string.
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
- :func:`bundle_md_document` — end-to-end: accept a Markdown string, fetch its
  Cloud Firestore images, and write a ``.mdbundle`` directory.
- :func:`render` — end-to-end: render a :class:`~guffin.graph.VertexTree` to a
  ``.mdbundle`` directory (parallel entry point to :func:`~guffin.pdf_rendering.render`).
"""

import logging
import re
from pathlib import Path
from typing import Final, overload

from pydantic import HttpUrl, validate_call

from guffin.filenames import normalize_for_posix
from guffin.graph import (
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TextContentVertex,
    Vertex,
    VertexChildren,
    VertexTree,
)
from guffin.roam_asset_fetch import fetch_and_cache_asset
from guffin.roam_local_api import ApiEndpoint
from guffin.roam_primitives import IMAGE_LINK_RE, Uid

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rendering — VertexTree → CommonMark string
# ---------------------------------------------------------------------------


def vertex_tree_to_md(vertex_tree: VertexTree) -> str:
    """Render *vertex_tree* to a CommonMark document string.

    The page title is rendered as an H1 heading.  Heading vertices become
    CommonMark ``#``-headings at their recorded level.  Text-content vertices
    that are direct children of the page (depth 1) are rendered as paragraphs;
    deeper text-content vertices are rendered as indented bullet-list items.
    Image vertices are rendered as CommonMark image links.

    Args:
        vertex_tree: The :class:`~guffin.graph.VertexTree` to render.

    Returns:
        A CommonMark document string ending with a single trailing newline.
    """
    logger.debug("vertex_tree=%r", vertex_tree)
    uid_map: Final[dict[Uid, Vertex]] = {v.uid: v for v in vertex_tree.vertices}
    child_uids: Final[set[Uid]] = {uid for v in vertex_tree.vertices if v.children for uid in v.children}
    root: Final[Vertex] = next(v for v in vertex_tree.vertices if v.uid not in child_uids)
    out: Final[list[str]] = []
    _render_vertex(root, uid_map, depth=0, out=out)
    return "\n".join(out).rstrip("\n") + "\n"


def _render_children(children: VertexChildren, uid_map: dict[Uid, Vertex], depth: int, out: list[str]) -> None:
    """Render each child UID in *children* into *out* at *depth*.

    Unknown UIDs are skipped with a warning.

    Args:
        children: Ordered list of child UIDs to render.
        uid_map: Mapping from UID to :data:`~guffin.graph.Vertex`.
        depth: Current tree depth (0 = page root).
        out: Accumulator list of output lines.
    """
    for uid in children:
        if uid not in uid_map:
            logger.warning("child uid=%r not found in uid_map; skipping", uid)
            continue
        _render_vertex(uid_map[uid], uid_map, depth, out)


def _render_vertex(vertex: Vertex, uid_map: dict[Uid, Vertex], depth: int, out: list[str]) -> None:
    """Render *vertex* and its subtree into *out* at *depth*.

    Dispatches to type-specific rendering logic via a ``match`` on the concrete
    vertex class, then recurses into children.

    Args:
        vertex: The :data:`~guffin.graph.Vertex` to render.
        uid_map: Mapping from UID to :data:`~guffin.graph.Vertex`.
        depth: Current tree depth (0 = page root, 1 = direct page child, …).
        out: Accumulator list of output lines.

    Raises:
        TypeError: If *vertex* is not one of the four known concrete
            :data:`~guffin.graph.Vertex` subclasses.
    """
    logger.debug("vertex=%r, depth=%d", vertex, depth)
    match vertex:
        case PageVertex(title=title):
            out.append(f"# {title}")
            out.append("")
        case HeadingVertex(heading=heading, text=text):
            out.append(f"{'#' * heading} {text}")
            out.append("")
        case TextContentVertex(text=text):
            if depth == 1:
                out.append(text)
                out.append("")
            else:
                indent = "  " * (depth - 2)
                out.append(f"{indent}- {text}")
        case ImageVertex(source=source, alt_text=alt_text):
            alt = alt_text or ""
            out.append(f"![{alt}]({source})")
            out.append("")
        case _:
            raise TypeError(f"Unrecognized vertex type: {type(vertex).__name__!r} (uid={vertex.uid!r})")
    if vertex.children:
        _render_children(vertex.children, uid_map, depth + 1, out)


# ---------------------------------------------------------------------------
# Bundle utilities — image fetching, URL rewriting, directory management
# ---------------------------------------------------------------------------


@validate_call
def find_markdown_image_links(markdown_text: str) -> list[tuple[str, HttpUrl]]:
    """Find all Cloud Firestore image links in a Markdown string.

    Args:
        markdown_text: The Markdown content to search.

    Returns:
        List of ``(full_match, image_url)`` tuples, one per Cloud Firestore
        image link found in *markdown_text*.

    Raises:
        ValidationError: If ``markdown_text`` is ``None`` or invalid.
    """
    matches: Final[list[tuple[str, HttpUrl]]] = []
    for match in IMAGE_LINK_RE.finditer(markdown_text):
        full_match: str = match.group(0)
        image_url: HttpUrl = HttpUrl(match.group("url"))
        matches.append((full_match, image_url))
    logger.debug("Found %d Cloud Firestore image links", len(matches))
    return matches


@validate_call
def fetch_and_save_image(
    api_endpoint: ApiEndpoint,
    firebase_url: HttpUrl,
    output_dir: Path,
    cache_dir: Path | None = None,
) -> tuple[HttpUrl, str]:
    """Fetch an image from Roam, write it to *output_dir*, and return its local filename.

    Delegates fetching and caching to
    :func:`~guffin.roam_asset_fetch.fetch_and_cache_asset`.  The asset is
    saved to *output_dir* under its deterministic ``<sha256>.<ext>`` filename,
    ensuring consistent filenames across cached and uncached runs.

    Args:
        api_endpoint: The Roam Local API endpoint (URL + bearer token).
        firebase_url: The Cloud Firestore storage URL.
        output_dir: Directory where the image file is written.
        cache_dir: Optional directory for caching downloaded assets across runs.

    Returns:
        A ``(firebase_url, local_filename)`` tuple where ``local_filename`` is
        the name of the saved file within *output_dir*.

    Raises:
        ValidationError: If ``firebase_url`` or ``api_endpoint`` is ``None`` or invalid.
        requests.exceptions.ConnectionError: If the Local API is unreachable.
        requests.exceptions.HTTPError: If the Local API returns a non-200 status.
    """
    asset = fetch_and_cache_asset(firebase_url, api_endpoint, cache_dir)
    output_path: Final[Path] = output_dir / asset.file_name
    output_path.write_bytes(asset.contents)
    logger.info("Saved image to: %s", output_path)
    return (firebase_url, asset.file_name)


@overload
def replace_image_links(markdown_text: None, url_replacements: list[tuple[HttpUrl, str]]) -> None: ...


@overload
def replace_image_links(markdown_text: str, url_replacements: list[tuple[HttpUrl, str]]) -> str: ...


@validate_call
def replace_image_links(markdown_text: str | None, url_replacements: list[tuple[HttpUrl, str]]) -> str | None:
    """Replace Cloud Firestore URLs with local filenames in a Markdown string.

    Args:
        markdown_text: The original Markdown content, or ``None``.
        url_replacements: List of ``(firebase_url, local_filename)`` tuples.

    Returns:
        Updated Markdown text with local file references, or ``None`` if
        *markdown_text* is ``None``.

    Raises:
        ValidationError: If ``url_replacements`` is invalid.
    """
    if markdown_text is None:
        return None
    result: str = markdown_text
    for firebase_url, local_filename in url_replacements:
        result = result.replace(str(firebase_url), local_filename)
        logger.debug("Replaced %s with %s", firebase_url, local_filename)
    return result


@validate_call
def normalize_link_text(markdown_text: str) -> str:
    """Remove line breaks from link text in Markdown links.

    Finds all Markdown links (both images and regular links) and replaces any
    line breaks within the link text with spaces.

    Args:
        markdown_text: The Markdown content to normalize.

    Returns:
        Markdown text with single-line link text.

    Raises:
        ValidationError: If ``markdown_text`` is ``None`` or invalid.
    """
    pattern: Final[str] = r"(!?\[)((?:[^\]]|\n)+?)(\]\([^\)]+\))"

    def replace_newlines(match: re.Match[str]) -> str:
        prefix: Final[str] = match.group(1)
        link_text: Final[str] = match.group(2)
        suffix: Final[str] = match.group(3)
        normalized: Final[str] = re.sub(r"\n+", " ", link_text)
        return f"{prefix}{normalized}{suffix}"

    return re.sub(pattern, replace_newlines, markdown_text)


@validate_call
def remove_escaped_double_brackets(markdown_text: str) -> str:
    r"""Remove escaped double brackets from Markdown text.

    Roam Research uses ``[[page links]]`` syntax which gets escaped to
    ``\[\[`` and ``\]\]`` when exported.  This function strips those
    escaped brackets.

    Args:
        markdown_text: The Markdown content to process.

    Returns:
        Markdown text with escaped double brackets removed.

    Raises:
        ValidationError: If ``markdown_text`` is ``None`` or invalid.
    """
    return markdown_text.replace(r"\[\[", "").replace(r"\]\]", "")


@validate_call
def fetch_all_images(
    image_links: list[tuple[str, HttpUrl]],
    api_endpoint: ApiEndpoint,
    output_dir: Path,
    cache_dir: Path | None = None,
) -> list[tuple[HttpUrl, str]]:
    """Fetch and save all images from *image_links*, skipping failures.

    Args:
        image_links: List of ``(full_match, firebase_url)`` tuples.
        api_endpoint: The Roam Local API endpoint (URL + bearer token).
        output_dir: Directory where images should be saved.
        cache_dir: Optional directory for caching downloaded assets across runs.

    Returns:
        List of ``(firebase_url, local_filename)`` tuples for successfully
        fetched images.

    Raises:
        ValidationError: If any parameter is ``None`` or invalid.
    """
    url_replacements: Final[list[tuple[HttpUrl, str]]] = []
    for _, firebase_url in image_links:
        try:
            url_replacements.append(fetch_and_save_image(api_endpoint, firebase_url, output_dir, cache_dir))
        except Exception as e:
            logger.error("Failed to fetch %s: %s", firebase_url, e)
    return url_replacements


# ---------------------------------------------------------------------------
# End-to-end export functions
# ---------------------------------------------------------------------------


@validate_call
def bundle_md_document(
    md_text: str,
    document_name: str,
    output_dir: Path,
    api_endpoint: ApiEndpoint,
    cache_dir: Path | None = None,
) -> None:
    """Bundle a Markdown document string with its referenced Cloud Firestore images.

    Accepts the Markdown content as a string rather than reading from a file on
    disk.  Fetches and saves Cloud Firestore-hosted images found in the text,
    rewrites the image links to use local filenames, and writes the updated
    document into a new ``<document_name>.mdbundle/`` directory inside
    *output_dir*.

    Args:
        md_text: The Markdown content to bundle.
        document_name: Name used to derive the bundle directory and output
            filename (e.g. a Roam page title). POSIX-normalized before use.
        output_dir: Parent directory where the ``.mdbundle`` folder will be
            created.
        api_endpoint: The Roam Local API endpoint (URL + bearer token).
        cache_dir: Optional directory for caching downloaded assets across runs.

    Raises:
        ValidationError: If any parameter is ``None`` or fails Pydantic
            validation.
    """
    bundle_dir_stem: Final[str] = normalize_for_posix(document_name)
    bundle_dir: Final[Path] = output_dir / f"{bundle_dir_stem}.mdbundle"
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

    md_to_write = normalize_link_text(md_to_write)
    md_to_write = remove_escaped_double_brackets(md_to_write)

    output_file: Final[Path] = bundle_dir / f"{bundle_dir_stem}.md"
    output_file.write_text(md_to_write, encoding="utf-8")
    logger.info("Wrote Markdown to: %s", output_file)


def render(
    vertex_tree: VertexTree,
    filename_stem: str,
    output_dir: Path,
    api_endpoint: ApiEndpoint,
    cache_dir: Path | None = None,
    bundle: bool = True,
) -> None:
    """Render *vertex_tree* to a Markdown file or bundle inside *output_dir*.

    Converts *vertex_tree* to CommonMark via :func:`vertex_tree_to_md`, then
    writes the result in one of two modes controlled by *bundle*:

    - ``bundle=True`` (default) — delegates to :func:`bundle_md_document` to
      fetch Cloud Firestore image assets and write a self-contained
      ``<normalized_filename_stem>.mdbundle/`` directory.
    - ``bundle=False`` — writes the CommonMark text directly to
      ``<output_dir>/<normalized_filename_stem>.md`` without fetching images.

    Parallel entry point to :func:`~guffin.pdf_rendering.render` — same
    signature (plus *bundle*), Markdown output.

    Args:
        vertex_tree: The normalized vertex tree to render.
        filename_stem: String used to derive the output filename (e.g. a Roam
            page title or node UID); POSIX-normalized before use.
        output_dir: Directory in which the output file or bundle is written;
            created if it does not already exist.
        api_endpoint: Roam Local API endpoint used to fetch image assets
            (bundle mode only; ignored when *bundle* is ``False``).
        cache_dir: Optional directory for caching downloaded image assets
            across runs.  Uses a SHA-256 hash of the Cloud Firestore URL as
            the cache key.  Ignored when *bundle* is ``False``.
        bundle: When ``True`` (default), writes a ``.mdbundle`` directory with
            embedded images.  When ``False``, writes a plain ``.md`` file.
    """
    md_text: Final[str] = vertex_tree_to_md(vertex_tree)
    if bundle:
        bundle_md_document(
            md_text=md_text,
            document_name=filename_stem,
            output_dir=output_dir,
            api_endpoint=api_endpoint,
            cache_dir=cache_dir,
        )
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path: Final[Path] = output_dir / f"{normalize_for_posix(filename_stem)}.md"
        output_path.write_text(md_text, encoding="utf-8")
        logger.info("Wrote Markdown to %s", output_path)
