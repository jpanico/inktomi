# CLAUDE.md

## Project Overview
Python 3.14 toolkit for exporting Roam Research pages to self-contained
documents.  Supports two output formats:

- **Markdown** — renders to CommonMark and optionally bundles Cloud
  Firestore-hosted images into a self-contained `.mdbundle` directory.
- **PDF** — builds a Pandoc object model directly from the `VertexTree`
  via Panflute, fetches and embeds Cloud Firestore images, and produces a
  PDF via Pandoc + Typst.

## Setup
```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

## Key Commands
```bash
dump-roam-tree <page_title_or_node_uid> -p <port> -g <graph> -t <token> [-v/-V] [-n/-N] [-r/-R] [--node-props <props>]
export-roam-tree <page_title_or_node_uid> -p <port> -g <graph> -t <token> -o <output_dir> [--format markdown|pdf] [--bundle|--no-bundle] [--cache-dir <dir>]
# --format markdown (default): writes <target>.mdbundle/ (--bundle) or <target>.md (--no-bundle)
# --format pdf: writes <target>.pdf via Pandoc + Typst; requires typst on PATH

# Run the full check pipeline (format + lint + type check + tests) in one shot:
hatch run check

# Individual steps (run in this order):
pydocstringformatter --write src/ # reflow docstring content (PEP 257)
black .                           # format code
ruff check --fix src/ tests/      # lint + fix docstring style (Google convention)
pyright                           # type check (strict)
pytest                            # run tests (excludes live tests)

# Live tests — NOT part of the check pipeline; must be explicitly requested:
ROAM_LIVE_TESTS=1 pytest -m live -v  # requires Roam Desktop running locally
```

## Project Structure
- `src/guffin/` — main package
  - **CLI entry points**
    - `dump_roam_tree.py` — dumps a Roam page or node subtree as a Rich tree to the terminal; supports `--vertex-tree`/`--node-tree`/`--raw-results` flags (`dump-roam-tree`)
    - `export_roam_tree.py` — exports a Roam page or node subtree; `--format markdown` (default) writes a `.mdbundle` or plain `.md`; `--format pdf` writes a PDF via Panflute + Pandoc + Typst; target is a page title or node UID (`export-roam-tree`)
    - `roam_tree_loader.py` — shared tree-loading pipeline; `fetch_roam_trees` resolves a target, fetches nodes, and returns a `(NodeFetchResult, VertexTree | None)` pair
  - **Core logic**
    - `roam_md_bundle.py` — core bundling logic
    - `roam_md_normalize.py` — normalizes Roam-flavored Markdown strings to CommonMark
    - `roam_transcribe.py` — transcribes `NodeTree` → `VertexTree`; applies `normalize()` to all text fields
    - `md_rendering.py` — renders a `VertexTree` to a CommonMark document string
    - `pdf_rendering.py` — renders a `VertexTree` to PDF: fetches image assets via `FetchRoamAsset`, builds a Panflute `Doc`, exports via Pandoc + Typst
    - `rich_rendering.py` — Rich panel/tree rendering for `NodeTree` and `VertexTree`
    - `validation.py` — generic accumulator-pipeline validation framework
  - **Model layer**
    - `roam_primitives.py` — foundational type aliases, stub models, `UID_PATTERN`, `UID_RE`, `IMAGE_LINK_RE` (dependency root)
    - `roam_node.py` — `RoamNode`, `NodeType`, `node_type`, `NodesByUid`
    - `roam_network.py` — `NodeNetwork` type alias; network validators (`all_children_present`, `all_parents_present`, `has_unique_ids`, `is_acyclic`) and utilities (`all_descendants`, `refs_ids`)
    - `roam_tree.py` — `NodeTree` (factory `build()`, fields `root_node`/`tree_network`/`refs_by_id`), `NodeTreeDFSIterator`, `is_tree`
    - `graph.py` — `Vertex` union, `VertexTree`, `VertexTreeDFSIterator`
    - `roam_schema.py` — Datomic schema model types (`RoamNamespace`, etc.)
    - `roam_asset.py` — Cloud Firestore asset model
  - **API / fetching**
    - `roam_local_api.py` — `ApiEndpoint` model for the Roam Local API
    - `roam_node_fetch_result.py` — `NodeFetchAnchor`, `NodeFetchSpec`, `NodeFetchResult`; fetch result model and factory methods (`from_raw`, `from_network`); `anchor_node` helper
    - `roam_node_fetch.py` — fetches `RoamNode` records via Local API; `fetch_roam_nodes` dispatches on page title vs. node UID
    - `roam_schema_fetch.py` — fetches Datomic schema via Local API
    - `roam_asset_fetch.py` — fetches Firestore assets via Local API
  - **Infrastructure**
    - `logging_config.py` — colorized logging (`configure_logging()`); reads `LOG_LEVEL` env var
- `scripts/` — shell wrapper scripts (`dump-roam-tree.sh`, `export-roam-tree.sh`) and maintenance scripts (`regen_article0_fixtures.py` — regenerates all test fixtures derived from "Test Article 0" from the live graph)
- `tests/fixtures/` — sample markdown, images, JSON, YAML for tests

## Conventions
- Src layout: package lives under `src/guffin/`
- Line length: 120 chars (Black + Ruff)
- Docstrings: PEP 257 format (pydocstringformatter), Google style convention (Ruff)
- Tests: pytest, files named `test_*.py`
- **Strong typing**: all Python code must use type annotations throughout; no `Any` types; enforced by pyright in strict mode
- **Bash tool calls**: never chain multiple commands with `&&` in a single Bash tool call; use separate Bash tool calls instead. Never use heredoc embeds (`$(cat <<'EOF'...EOF)`) in Bash tool calls; use plain `-m "..."` strings with `\n` for newlines instead.
- **Logging format**: all `logger.*()` calls must use `%`-style format strings (e.g., `logger.info("x=%s", x)`) — never f-strings (e.g., `logger.info(f"x={x}")`); this enables lazy interpolation and better log aggregation in monitoring tools.
- **Immutable bindings**: all local variables and module-level constants must be annotated `Final[T]` by default (e.g., `x: Final[int] = 1`, `MY_CONST: Final[str] = "value"`); only omit `Final` when the binding genuinely needs to be reassigned. Inside Pydantic models, use `ClassVar[T]` for class-level constants (Pydantic excludes these from model fields).

## Modern Python Requirements (Python 3.14)
All code written or modified by Claude MUST follow these conventions — no exceptions:

- **Built-in generics**: always `list[x]`, `tuple[x, y]`, `dict[k, v]`, `set[x]` — never `List`, `Tuple`, `Dict`, `Set` from `typing`
- **Union syntax**: always `X | Y` and `X | None` — never `Union[X, Y]` or `Optional[X]`
- **Type aliases**: always `type Foo = ...` (PEP 695) — never `Foo: TypeAlias = ...` or bare `Foo = ...`
- **No `from __future__ import annotations`**: not needed in Python 3.14 (PEP 649 deferred evaluation is the default)
- **No string-quoted forward references**: never `"ClassName"` in annotations; if a forward reference is needed, reorder definitions so the referenced name is declared first
- **No `cast()`**: never use `typing.cast()`; fix the type properly instead
- **No `Any`**: never use `typing.Any`; use a precise type or a type variable
- **Enum mixin subclasses**: always use the dedicated single-inheritance mixin — never mix a built-in type with `Enum`/`Flag` directly (Ruff `UP042`):
  - `class Foo(str, Enum)` → `class Foo(enum.StrEnum)`
  - `class Foo(int, Enum)` → `class Foo(enum.IntEnum)`
  - `class Foo(int, Flag)` → `class Foo(enum.IntFlag)`

## Reference Docs
- `docs/roam-md.md` — Roam flavored Markdown vs. CommonMark differences (relevant to normalization work)
- `docs/roam-local-api.md` — Roam Local API reference (endpoints, request/response shapes)
- `docs/roam-querying.md` — Datalog query patterns used to fetch Roam nodes
- `docs/roam-schema.md` — Roam Datomic schema reference (attributes, value types, cardinality)
- `docs/processing_pipeline.md` — high-level overview of the core data processing pipeline

## Environment Variables
- `ROAM_LOCAL_API_PORT` — port for Roam Local API (all CLI tools)
- `ROAM_GRAPH_NAME` — Roam graph name (all CLI tools)
- `ROAM_API_TOKEN` — bearer token for auth (all CLI tools)
- `ROAM_EXPORT_DIR` — output directory for `export-roam-tree`
- `ROAM_CACHE_DIR` — directory for caching downloaded Cloud Firestore assets (`export-roam-tree`)
- `ROAM_LIVE_TESTS` — set to any non-empty value to enable live tests (e.g. `ROAM_LIVE_TESTS=1`); requires Roam Desktop running locally
