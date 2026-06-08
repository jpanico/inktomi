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
export-roam-tree <page_title_or_node_uid> -p <port> -g <graph> -t <token> -o <output_dir> [--format markdown|pdf] [--bundle|--no-bundle] [--cache-dir <dir>] [--template-dir <dir>]
# --format markdown (default): writes <target>.mdbundle/ (--bundle) or <target>.md (--no-bundle)
# --format pdf: writes <target>.pdf via Pandoc + Typst; requires typst on PATH
# --template-dir: directory containing user_cfg.typ overrides for PDF styling (pdf only)

# Run the full check pipeline (format + lint + type check + tests) in one shot:
hatch run check

# Individual steps (run in this order):
pydocstringformatter --write src/ # reflow docstring content (PEP 257)
black .                           # format code
ruff check --fix src/ tests/      # lint + fix docstring style (Google convention)
pyright                           # type check (strict)
pytest                            # run tests (excludes live tests)

# Live tests — NOT part of the check pipeline; must be explicitly requested:
GUFFIN_LIVE_TESTS=1 pytest -m live -v  # requires Roam Desktop running locally
```

## Project Structure
- `src/guffin/` — main package
  - **CLI entry points**
    - `dump_roam_tree.py` — dumps a Roam page or node subtree as a Rich tree to the terminal; supports `--vertex-tree`/`--node-tree`/`--raw-results` flags (`dump-roam-tree`)
    - `export_roam_tree.py` — exports a Roam page or node subtree; `--format markdown` (default) writes a `.mdbundle` or plain `.md`; `--format pdf` writes a PDF via Panflute + Pandoc + Typst; target is a page title or node UID (`export-roam-tree`)
  - **Core logic**
    - `roam_tree_loader.py` — shared tree-loading pipeline; `fetch_roam_trees` resolves a target, fetches nodes, and returns a `(NodeFetchResult, VertexTree | None)` pair
    - `roam_md_to_pandoc_md.py` — converts Roam-flavored Markdown strings to Pandoc Markdown; `to_pandoc_md()` is the main entry point
    - `roam_transcribe.py` — transcribes `NodeTree` → `VertexTree`; applies `to_pandoc_md()` to all text fields
    - `pandoc_rendering.py` — shared Pandoc/Panflute rendering utilities; `vertex_tree_to_pandoc()` builds a Panflute `Doc` from a `VertexTree` (batch-parsing inline Pandoc Markdown via a single Pandoc call); `fetch_images()` fetches Cloud Firestore image assets
    - `md_rendering.py` — renders a `VertexTree` to Markdown: invokes `pandoc_rendering`, serializes to Pandoc JSON, converts to CommonMark via Pandoc, writes a plain `.md` or `.mdbundle/` directory
    - `pdf_rendering.py` — renders a `VertexTree` to PDF: invokes `pandoc_rendering`, serializes to Pandoc JSON, converts to PDF via Pandoc + Typst
    - `filenames.py` — `shell_safe_filename()` normalizes strings to POSIX-safe filenames
    - `rich_rendering.py` — Rich panel/tree rendering for `NodeTree` and `VertexTree`
    - `validation.py` — generic accumulator-pipeline validation framework
  - **Model layer**
    - `roam_primitives.py` — foundational type aliases, stub models, `UID_PATTERN`, `UID_RE`, `IMAGE_LINK_RE` (dependency root)
    - `roam_node.py` — `RoamNode`, `NodeType`, `node_type`, `NodesByUid`
    - `roam_network.py` — `NodeNetwork` type alias; network validators (`all_children_present`, `all_parents_present`, `has_unique_ids`, `is_acyclic`) and utilities (`all_descendants`, `refs_ids`)
    - `roam_tree.py` — `NodeTree` (factory `build()`, fields `root_node`/`tree_network`/`refs_by_id`), `NodeTreeDFSIterator`, `is_tree`
    - `graph.py` — `Vertex` union, `VertexTree`, `VertexTreeDFSIterator`, `root_vertex()`; filter helpers `page_vertices()`, `heading_vertices()`, `text_content_vertices()`, `image_vertices()`, `image_urls()`
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
  - **Templates**
    - `templates/` — Bergfink Typst/Pandoc PDF template (package data; see `src/guffin/templates/README.md`); `user_cfg.typ` is the intended customization point
- `scripts/` — shell wrapper scripts (`dump-roam-tree.sh`, `export-roam-tree.sh`)
- `tests/fixtures/` — sample markdown, images, JSON, YAML for tests
- `tests/regen_fixtures.py` — developer script; regenerates all six fixture files for a given Roam page title or node UID (see **Test Fixtures** below)

## Test Fixtures

Three live Roam pages serve as the primary test sources: `[[Test Article]] 0`,
`[[Test Article]] 1`, and `[[Test Article]] 2`.  For each source, `tests/regen_fixtures.py` generates six
fixture files that capture different stages and views of the data pipeline.

### No-refs fixture set (`include_refs=False`) — a linear pipeline

Three fixtures representing successive stages of the export pipeline applied to
the anchor subtree alone, with no referenced pages included:

| Fixture | What it captures |
|---|---|
| `<prefix>_nodes.yaml` | The Roam nodes (page + blocks) as parsed `RoamNode` model objects |
| `<prefix>_vertices.yaml` | The same subtree transcribed into the export model (`VertexTree`) |
| `<prefix>_expected.md` | The fully rendered CommonMark output |

### With-refs fixture set (`include_refs=True`) — three views of the same fetch

Three fixtures derived from a single API call that pulls the anchor subtree
together with every page and block it references.  Rather than a pipeline, they
are three different lenses on the same underlying data:

| Fixture | What it captures |
|---|---|
| `<prefix>_raw_result.yaml` | The raw Datalog wire response before any `RoamNode` parsing |
| `<prefix>_anchor_tree.yaml` | The `NodeTree` of the anchor subtree itself (within the broader refs fetch) |
| `<prefix>_nodes_by_uid.yaml` | All fetched nodes — anchor subtree plus every referenced page/block — keyed by UID |

To regenerate fixtures from the live Roam graph (requires Roam Desktop running):
```bash
python tests/regen_fixtures.py "[[Test Article]] 0" --prefix test_article_0
python tests/regen_fixtures.py "[[Test Article]] 1" --prefix test_article_1
python tests/regen_fixtures.py "[[Test Article]] 2" --prefix test_article_2
```

## Git
- **Never commit or push without explicit instructions**: do not run `git commit` or `git push` unless the user explicitly asks. This applies even after completing a task — finish the work, then wait for the user to request a commit/push.

## Conventions
- Src layout: package lives under `src/guffin/`
- Line length: 120 chars (Black + Ruff)
- Docstrings: PEP 257 format (pydocstringformatter), Google style convention (Ruff)
- Tests: pytest, files named `test_*.py`
- **Strong typing**: all Python code must use type annotations throughout; no `Any` types; enforced by pyright in strict mode
- **Bash tool calls**: never chain multiple commands with `&&` in a single Bash tool call; use separate Bash tool calls instead. Never use heredoc embeds (`$(cat <<'EOF'...EOF)`) in Bash tool calls; use plain `-m "..."` strings with `\n` for newlines instead.
- **Logging format**: all `logger.*()` calls must use `%`-style format strings (e.g., `logger.info("x=%s", x)`) — never f-strings (e.g., `logger.info(f"x={x}")`); this enables lazy interpolation and better log aggregation in monitoring tools.
- **`@validate_call`**: decorate every public function and method (non-`_`-prefixed, non-dunder) with `@validate_call`. Exceptions: `@property` methods (technically incompatible), Pydantic model lifecycle methods (`model_*`, field validators, `__init__`), CLI entry-point functions wired by argparse, methods overriding non-Pydantic framework interfaces, generic functions whose type variables cannot be resolved at runtime, and classmethods/staticmethods whose return-type annotation references the class being defined (pydantic eagerly evaluates type hints at decoration time, before the class is added to module globals, causing a `NameError`). For `@staticmethod` and `@classmethod` methods that qualify, `@validate_call` is placed innermost — just above `def`, below the `@staticmethod`/`@classmethod` line. When a function has panflute (or other arbitrary-type) parameters, use `@validate_call(config=ConfigDict(arbitrary_types_allowed=True))` instead of plain `@validate_call`.
- **Immutable bindings**: all local variables and module-level constants must be annotated `Final[T]` by default (e.g., `x: Final[int] = 1`, `MY_CONST: Final[str] = "value"`); only omit `Final` when the binding genuinely needs to be reassigned. Inside Pydantic models, use `ClassVar[T]` for class-level constants (Pydantic excludes these from model fields).

## Architecture
- **CLI isolation**: only `export_roam_tree.py` and `dump_roam_tree.py` may import or use the Typer package. All other modules must be front-end agnostic so they can be used outside a CLI context without pulling in CLI dependencies.
- **Exit-point isolation**: all explicit process-exit calls (`typer.Exit`, `sys.exit`, etc.) must live exclusively in the CLI modules. Library code propagates exceptions; CLIs decide whether and how to exit. This keeps control-flow transparent and makes library code testable without mocking exit behaviour.

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
- `GUFFIN_ROAM_LOCAL_API_PORT` — port for Roam Local API (all CLI tools)
- `GUFFIN_ROAM_GRAPH_NAME` — Roam graph name (all CLI tools)
- `GUFFIN_ROAM_API_TOKEN` — bearer token for auth (all CLI tools)
- `GUFFIN_EXPORT_DIR` — output directory for `export-roam-tree`
- `GUFFIN_CACHE_DIR` — directory for caching downloaded Cloud Firestore assets (`export-roam-tree`)
- `GUFFIN_PDF_TEMPLATE_DIR` — directory containing a `user_cfg.typ` override for PDF styling (`export-roam-tree --format pdf`)
- `GUFFIN_DUMP_PANDOC_AST` — set to any non-empty value to dump the Pandoc JSON AST to `<output-dir>/<target>.pandoc.json` before the Pandoc conversion step (`export-roam-tree`, both formats)
- `GUFFIN_LIVE_TESTS` — set to any non-empty value to enable live tests (e.g. `GUFFIN_LIVE_TESTS=1`); requires Roam Desktop running locally
