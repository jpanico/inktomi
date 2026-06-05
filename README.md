# guffin

Python 3.14 toolkit for exporting Roam Research graph sub-trees to self-contained documents. Supports two output formats:

- **Markdown** — renders to CommonMark and optionally bundles Roam-hosted (Cloud Firestore) images into a self-contained `.mdbundle` directory.
- **PDF** — builds a Pandoc object model directly from the normalized graph sub-tree via [Panflute](https://github.com/sergiocorreia/panflute), fetches and embeds Roam-hosted (Cloud Firestore) images, and produces a PDF via [Pandoc](https://pandoc.org) + [Typst](https://typst.app).

## Development Setup

### Prerequisites

- Python 3.14 or higher
- Git
- [Pandoc](https://pandoc.org/installing.html) — required for all export formats (`brew install pandoc`)
- [Typst](https://typst.app) — PDF engine used by Pandoc (`brew install typst`)

### Initial Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/jpanico/guffin.git
   cd guffin
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install the package in editable mode with development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

   This installs the `guffin` package in editable mode (changes to code are immediately reflected),
   along with all runtime and development dependencies declared in [`pyproject.toml`](pyproject.toml).

### Running Tests

Once the development environment is set up, run the full check pipeline (format, lint, type check, and tests) with a single command:

```bash
hatch run check
```

This runs, in order: `pydocstringformatter`, `black`, `ruff check --fix`, `pyright`, and `pytest`.

To run only the test suite:

```bash
pytest
```

To run tests with verbose output:
```bash
pytest -v
```

To run a specific test file:
```bash
pytest tests/test_roam_asset_fetch.py
```

#### Live Integration Tests

Some tests require the Roam Desktop app to be running locally. These are marked with `@pytest.mark.live` and are skipped by default. To enable them:

```bash
ROAM_LIVE_TESTS=1 ROAM_LOCAL_API_PORT=3333 ROAM_GRAPH_NAME=<graph> ROAM_API_TOKEN=<token> pytest -m live -v
```

### Code Formatting

This project uses [Black](https://black.readthedocs.io/) for code formatting (line length: 120):

```bash
black .
```

To check formatting without making changes:
```bash
black --check .
```

### Docstring Formatting and Linting

Docstrings are enforced at two levels:

**1. PEP 257 reflow — [`pydocstringformatter`](https://github.com/DanielNoord/pydocstringformatter)**

Reformats docstring content: line wrapping, blank-line structure, capitalisation, closing-quote placement.

```bash
pydocstringformatter --write src/
```

To preview without writing:
```bash
pydocstringformatter src/
```

**2. Google-style lint — `ruff check`**

Enforces Google docstring convention and auto-fixes violations.

```bash
ruff check src/ tests/
ruff check --fix src/ tests/
```

Recommended order: `pydocstringformatter` → `black` → `ruff check --fix`.

### Type Checking

[Pyright](https://github.com/microsoft/pyright) is configured in **strict** mode for `src/`:

```bash
pyright
```

All production code under `src/guffin/` must be fully annotated with no `Any` types. Test modules (`tests/`) are excluded from pyright via `pyproject.toml` and are not type-checked.

## Project Structure

```
guffin/
├── src/
│   └── guffin/                  # Main package
│       ├── dump_roam_tree.py      # CLI: dump a Roam page or node subtree as a Rich tree to the terminal
│       ├── export_roam_tree.py    # CLI: export a Roam page or node subtree (--format markdown|pdf)
│       ├── roam_tree_loader.py    # Shared tree-loading pipeline; fetch_roam_trees resolves a target, fetches nodes, returns (NodeTree, VertexTree)
│       ├── roam_md_to_commonmark.py # Convert Roam-flavored Markdown to CommonMark
│       ├── roam_transcribe.py     # Transcribe NodeTree → VertexTree (applies normalize())
│       ├── pandoc_rendering.py    # Shared Pandoc/panflute utilities: inline CommonMark parsing, image fetching, VertexTree → Doc conversion
│       ├── md_rendering.py        # Render VertexTree → Markdown via Pandoc; write .mdbundle or plain .md
│       ├── pdf_rendering.py       # Render VertexTree → PDF via pandoc_rendering + Pandoc + Typst
│       ├── rich_rendering.py      # Rich panel/tree rendering for NodeTree and VertexTree
│       ├── validation.py          # Generic accumulator-pipeline validation framework
│       ├── filenames.py           # POSIX filename normalization utilities
│       ├── roam_primitives.py     # Foundational type aliases, UID_PATTERN/UID_RE, IMAGE_LINK_RE (dep root)
│       ├── roam_node.py           # RoamNode, NodeType, node_type, NodesByUid
│       ├── roam_network.py        # NodeNetwork type alias; network validators and utilities (all_descendants, refs_ids)
│       ├── roam_tree.py           # NodeTree (build() factory, tree_network/refs_by_id fields), NodeTreeDFSIterator, is_tree
│       ├── graph.py               # Vertex union, VertexTree, VertexTreeDFSIterator
│       ├── roam_schema.py         # Datomic schema model types (RoamNamespace, etc.)
│       ├── roam_asset.py          # Cloud Firestore asset model
│       ├── roam_local_api.py      # ApiEndpoint model for the Roam Local API
│       ├── roam_node_fetch_result.py # NodeFetchAnchor, NodeFetchSpec, NodeFetchResult; fetch result model and factories
│       ├── roam_node_fetch.py     # Fetch RoamNode records via Local API; by page title or by node UID
│       ├── roam_schema_fetch.py   # Fetch Datomic schema via Local API
│       ├── roam_asset_fetch.py    # Fetch Firestore assets via Local API
│       └── logging_config.py      # Colorized logging; reads LOG_LEVEL env var
├── tests/                         # pytest test suite
│   ├── conftest.py                # Shared fixtures and helpers (api_endpoint, article0_node_tree, …)
│   └── fixtures/
│       ├── images/
│       │   ├── flower.jpeg                      # JPEG used in live asset-fetch tests
│       │   ├── test_article_0.png               # Screenshot of Test Article 0 in Roam
│       │   └── test_article_1.png               # Screenshot of Test Article 1 in Roam
│       ├── json/
│       │   └── image_node.json                  # Raw pull-block payload for a Firestore image block
│       ├── markdown/
│       │   ├── descendant_rule.md               # CSS descendant-rule reference snippet
│       │   ├── flower.jpeg                      # Image asset bundled alongside test_article_0_expected.md
│       │   └── test_article_0_expected.md       # Expected CommonMark output for Test Article 0
│       └── yaml/
│           ├── test_article_0_nodes.yaml        # Serialized NodeNetwork for Test Article 0
│           ├── test_article_0_vertices.yaml     # Serialized VertexTree for Test Article 0
│           ├── test_article_1_anchor_tree.yaml  # Serialized NodeTree for Test Article 1 (anchor subtree)
│           ├── test_article_1_nodes_by_uid.yaml # Serialized NodesByUid for Test Article 1
│           └── test_article_1_raw_result.yaml   # Raw Datalog result for Test Article 1
├── scripts/
│   ├── dump-roam-tree.sh              # Shell wrapper for dump-roam-tree
│   ├── export-roam-tree.sh            # Shell wrapper for export-roam-tree
│   ├── regen_article0_fixtures.py     # Regenerate all test fixtures derived from "Test Article 0"
│   ├── setup-mdbundle-handler.sh      # Setup .mdbundle auto-open in Typora (macOS)
│   └── refresh-mdbundle-folders.sh    # Refresh existing .mdbundle folders (macOS)
├── docs/
│   ├── MDBUNDLE_SETUP.md           # macOS .mdbundle integration guide
│   ├── processing_pipeline.md      # High-level overview of the core data processing pipeline
│   ├── roam-local-api.md           # Roam Local API (JSON over HTTP) reference
│   ├── roam-md.md                  # Roam-flavored Markdown vs. CommonMark differences
│   ├── roam-querying.md            # Datalog query language, query structure, and all queries used in this project
│   ├── roam-schema.md              # Full Roam attribute schema (kept in sync with RoamAttribute enum)
│   └── roam_database.png           # Datomic/DataScript datom model diagram
└── pyproject.toml                  # Project configuration
```

## Usage

The package provides two command-line utilities.

### `export-roam-tree` — Export a Roam page or node subtree

Fetches a Roam `Page` or `Node` subtree via the Local API, normalizes it, and writes the result in one of two formats controlled by `--format`. The positional argument is interpreted as a **node UID** if it matches `^[A-Za-z0-9_-]{9}$` (exactly 9 alphanumeric/dash/underscore characters); otherwise it is treated as a **page title**.

```bash
export-roam-tree <page_title_or_node_uid> --port <port> --graph <graph> --token <token> --output-dir <output_dir> \
  [--format markdown|pdf] [--bundle|--no-bundle] [--cache-dir <dir>]
```

#### Markdown output (default)

By default (`--format markdown`) it creates a `.mdbundle` directory containing the CommonMark document and any downloaded Cloud Firestore images. Pass `--no-bundle` to write a plain `.md` file instead.

```bash
# Bundled (default) — creates ~/docs/Test Article.mdbundle/
export-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs

# Plain .md — creates ~/docs/Test Article.md
export-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs --no-bundle

# Export by node UID
export-roam-tree wdMgyBiP9 --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs
```

#### PDF output

`--format pdf` builds a Pandoc object model directly from the vertex tree via Panflute, fetches and embeds Cloud Firestore images, and produces a PDF via Pandoc + Typst. Requires `typst` on `PATH`.

```bash
# Creates ~/docs/Test Article.pdf
export-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --output-dir ~/docs --format pdf
```

The `--bundle/--no-bundle` flags are ignored with `--format pdf`. The `--cache-dir` option works with both formats.

#### Environment variables

All options can be supplied via environment variables:

```bash
export ROAM_LOCAL_API_PORT=3333
export ROAM_GRAPH_NAME=SCFH
export ROAM_API_TOKEN=<your-bearer-token>
export ROAM_EXPORT_DIR=~/docs
export ROAM_CACHE_DIR=~/.cache/roam   # optional: skip re-downloading unchanged images

export-roam-tree "Test Article"                      # Markdown bundle (default)
export-roam-tree "Test Article" --format pdf         # PDF
```

### `dump-roam-tree` — Inspect a Roam page or node subtree as a Rich tree

Fetches a Roam `Page` or `Node` subtree via the Local API, and renders it as a colorized tree in the terminal. Useful for inspecting the raw node structure or the normalized vertex structure. The positional argument follows the same page-title-vs-node-UID inference as `export-roam-tree`.

```bash
dump-roam-tree <page_title_or_node_uid> --port <port> --graph <graph> --token <token> \
  [--vertex-tree] [--node-tree] [--raw-results] [--include-refs] [--node-props <props>]
```

Flags (all are boolean toggles with a `--no-*` / uppercase-letter inverse):

| Flag | Short | Default | Effect |
|---|---|---|---|
| `--vertex-tree` | `-v/-V` | **on** | Render the normalized vertex tree |
| `--node-tree` | `-n/-N` | off | Render the raw node tree |
| `--raw-results` | `-r/-R` | off | Print the raw Datalog query results |
| `--include-refs` | `-i/-I` | **on** | Also fetch nodes referenced via `:block/refs` and their descendants |

`--node-props heading,parents` selects which `RoamNode` fields appear for each node in the output.

Examples:
```bash
# Default: vertex tree + refs included
dump-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token

# Node tree + vertex tree, with custom node props
dump-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --node-tree --vertex-tree --node-props heading,parents

# Raw Datalog results only, no refs
dump-roam-tree "Test Article" --port 3333 --graph SCFH --token your-bearer-token --raw-results --no-vertex-tree --no-include-refs

# Fetch by node UID
dump-roam-tree wdMgyBiP9 --port 3333 --graph SCFH --token your-bearer-token
```

### macOS Integration: Auto-Open in Typora

To configure macOS to automatically open `.mdbundle` folders in Typora when double-clicked:

1. **Run the setup script:**
   ```bash
   ./scripts/setup-mdbundle-handler.sh
   ```

   This creates and registers `OpenMDBundle.app` which handles `.mdbundle` folders.

2. **Refresh existing .mdbundle folders (if any):**
   ```bash
   ./scripts/refresh-mdbundle-folders.sh ~/wip
   ```

   This updates the metadata for existing `.mdbundle` folders so macOS recognizes them properly.

3. **Done!** Double-clicking any `.mdbundle` folder will now open the markdown file in Typora

See [docs/MDBUNDLE_SETUP.md](docs/MDBUNDLE_SETUP.md) for detailed instructions and troubleshooting.

## Documentation

- [docs/processing_pipeline.md](docs/processing_pipeline.md) — High-level overview of the core data processing pipeline
- [docs/roam-local-api.md](docs/roam-local-api.md) — Roam Local API reference (JSON over HTTP)
- [docs/roam-md.md](docs/roam-md.md) — Roam-flavored Markdown vs. CommonMark differences
- [docs/roam-querying.md](docs/roam-querying.md) — Datalog query language, query structure, and all queries used in this project
- [docs/roam-schema.md](docs/roam-schema.md) — Full Roam attribute schema (kept in sync with `RoamAttribute` enum)
- [docs/MDBUNDLE_SETUP.md](docs/MDBUNDLE_SETUP.md) — macOS `.mdbundle` integration guide

## License

[MIT](LICENSE)
