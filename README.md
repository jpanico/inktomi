# inktomi

Python 3.14 toolkit for bundling Roam Research markdown exports with their Cloud Firestore-hosted images into self-contained `.mdbundle` directories.

## Development Setup

### Prerequisites

- Python 3.14 or higher
- Git

### Initial Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/inktomi.git
   cd inktomi
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

   This installs the `inktomi` package in editable mode (changes to code are immediately reflected),
   along with all runtime and development dependencies declared in [`pyproject.toml`](pyproject.toml).

### Running Tests

Once the development environment is set up, run the full check pipeline (format, lint, type check, and tests) with a single command:

```bash
hatch run check
```

This runs, in order: `black`, `pydocstringformatter`, `ruff format --preview`, `ruff check --fix`, `pyright`, and `pytest`.

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
export ROAM_LIVE_TESTS=1
pytest -m live
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

**2. Structural formatting — `ruff format --preview`**

Fixes indentation, trailing whitespace, and blank lines around docstrings.

```bash
ruff format --preview src/
```

**3. Google-style lint — `ruff check`**

Enforces Google docstring convention and auto-fixes violations.

```bash
ruff check src/ tests/
ruff check --fix src/ tests/
```

Recommended order: `pydocstringformatter` → `ruff format --preview` → `ruff check --fix`.

### Type Checking

[Pyright](https://github.com/microsoft/pyright) is configured in **strict** mode for `src/`:

```bash
pyright
```

All production code under `src/inktomi/` must be fully annotated with no `Any` types. Test modules (`tests/`) use `basic` type checking (`# pyright: basic` directive at the top of each test file).

## Project Structure

```
inktomi/
├── src/
│   └── inktomi/                  # Main package
│       ├── __init__.py
│       ├── dump_roam_tree.py      # CLI: dump a Roam page or node subtree as a Rich tree to the terminal
│       ├── export_roam_tree.py    # CLI: export a Roam page or node subtree to a .mdbundle or plain .md
│       ├── roam_tree_loader.py    # Shared tree-loading pipeline; fetch_roam_trees resolves a target, fetches nodes, returns (NodeTree, VertexTree)
│       ├── roam_md_bundle.py      # Core bundling logic
│       ├── roam_md_normalize.py   # Normalize Roam-flavored Markdown to CommonMark
│       ├── roam_transcribe.py     # Transcribe NodeTree → VertexTree (applies normalize())
│       ├── md_rendering.py        # Render VertexTree → CommonMark document string
│       ├── rich_rendering.py      # Rich panel/tree rendering for NodeTree and VertexTree
│       ├── validation.py          # Generic accumulator-pipeline validation framework
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
│   ├── fixtures/                  # Sample markdown, images, JSON, YAML
│   ├── test_export_roam_tree.py
│   ├── test_roam_asset_fetch.py
│   ├── test_roam_graph.py
│   ├── test_roam_local_api.py
│   ├── test_roam_md_bundle.py
│   ├── test_roam_md_normalize.py
│   ├── test_roam_network.py
│   ├── test_roam_node.py
│   ├── test_roam_node_fetch.py
│   ├── test_roam_node_fetch_result.py
│   ├── test_roam_render_md.py
│   ├── test_roam_schema_fetch.py
│   ├── test_roam_transcribe.py
│   └── test_roam_tree.py
├── scripts/
│   ├── dump-roam-tree.sh           # Shell wrapper for dump-roam-tree
│   ├── export-roam-tree.sh         # Shell wrapper for export-roam-tree
│   ├── setup-mdbundle-handler.sh   # Setup .mdbundle auto-open in Typora
│   └── refresh-mdbundle-folders.sh # Refresh existing .mdbundle folders
├── docs/
│   ├── MDBUNDLE_SETUP.md           # macOS .mdbundle integration guide
│   ├── processing_pipeline.md      # High-level overview of the core data processing pipeline
│   ├── roam-local-api.md           # Roam Local API (JSON over HTTP) reference
│   ├── roam-md.md                  # Roam-flavored Markdown vs. CommonMark differences
│   ├── roam-querying.md            # Datalog query language and query reference
│   ├── roam-schema.md              # Full Roam attribute schema from a live graph
│   └── roam_database.png           # Datomic/DataScript datom model diagram
├── pyproject.toml                  # Project configuration
└── README.md
```

## Usage

The package provides two command-line utilities.

### `export-roam-tree` — Export a Roam page or node subtree to CommonMark

Fetches a Roam page or node subtree via the Local API, normalizes it, and writes the result to the output directory. The positional argument is interpreted as a **node UID** if it matches `^[A-Za-z0-9_-]{9}$` (exactly 9 alphanumeric/dash/underscore characters); otherwise it is treated as a **page title**.

By default it creates a `.mdbundle` directory containing the CommonMark document and any downloaded Cloud Firestore images. Pass `--no-bundle` to write a plain `.md` file instead.

```bash
export-roam-tree <page_title_or_node_uid> -p <port> -g <graph> -t <token> -o <output_dir> [--bundle|--no-bundle] [--cache-dir <dir>]
```

Example — export by page title (bundled, default):
```bash
export-roam-tree "Test Article" -p 3333 -g SCFH -t your-bearer-token -o ~/docs
# → creates ~/docs/Test Article.mdbundle/
```

Example — export by node UID:
```bash
export-roam-tree wdMgyBiP9 -p 3333 -g SCFH -t your-bearer-token -o ~/docs
# → creates ~/docs/wdMgyBiP9.mdbundle/
```

Example — plain `.md` output:
```bash
export-roam-tree "Test Article" -p 3333 -g SCFH -t your-bearer-token -o ~/docs --no-bundle
# → creates ~/docs/Test Article.md
```

Supported environment variables:
```bash
export ROAM_LOCAL_API_PORT=3333
export ROAM_GRAPH_NAME=SCFH
export ROAM_API_TOKEN=your-bearer-token
export ROAM_EXPORT_DIR=~/docs
export ROAM_CACHE_DIR=~/.cache/roam   # optional: skip re-downloading unchanged images

export-roam-tree "Test Article"
```

### `dump-roam-tree` — Inspect a Roam page or node subtree as a Rich tree

Fetches a Roam page or node subtree and renders it as a colorized tree in the terminal. Useful for inspecting the raw node structure or the normalized vertex structure. The positional argument follows the same page-title-vs-node-UID inference as `export-roam-tree`.

```bash
dump-roam-tree <page_title_or_node_uid> -p <port> -g <graph> -t <token> [--vertex-tree|-v] [--node-tree|-n] [--raw-results|-r] [--include-refs|-i] [--node-props <props>]
```

Flags (all are boolean toggles with a `--no-*` / uppercase-letter inverse):

| Flag | Short | Default | Effect |
|---|---|---|---|
| `--vertex-tree` | `-v/-V` | **on** | Render the normalized vertex tree |
| `--node-tree` | `-n/-N` | off | Render the raw node tree |
| `--raw-results` | `-r/-R` | off | Print the raw Datalog query results |
| `--include-refs` | `-i/-I` | **on** | Also fetch nodes referenced via `:block/refs` and their descendants (page-title targets only) |

`--node-props heading,parents` selects which `RoamNode` fields appear in each node panel body.

Examples:
```bash
# Default: vertex tree + refs included
dump-roam-tree "Test Article" -p 3333 -g SCFH -t your-bearer-token

# Node tree + vertex tree, with custom node props
dump-roam-tree "Test Article" -p 3333 -g SCFH -t your-bearer-token -n -v --node-props heading,parents

# Raw Datalog results only, no refs
dump-roam-tree "Test Article" -p 3333 -g SCFH -t your-bearer-token -r -V -I

# Fetch by node UID
dump-roam-tree wdMgyBiP9 -p 3333 -g SCFH -t your-bearer-token
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

**How it works:**
- Double-clicking a `.mdbundle` folder launches `OpenMDBundle.app`
- The app uses AppleScript to properly handle the "open" event from macOS
- It extracts the markdown filename and opens it in Typora

**Troubleshooting:**
- If double-clicking doesn't work, try logging out and back in
- Right-click a `.mdbundle` folder → Get Info to verify "OpenMDBundle" appears under "Open with:"
- If it doesn't appear, run `mdimport <folder>` to force macOS to recognize it
- Test from command line: `open ~/path/to/your.mdbundle` should open in Typora

See [docs/MDBUNDLE_SETUP.md](docs/MDBUNDLE_SETUP.md) for detailed instructions and troubleshooting.

## Documentation

- [docs/processing_pipeline.md](docs/processing_pipeline.md) — High-level overview of the core data processing pipeline
- [docs/roam-local-api.md](docs/roam-local-api.md) — Roam Local API reference (JSON over HTTP)
- [docs/roam-md.md](docs/roam-md.md) — Roam-flavored Markdown vs. CommonMark differences
- [docs/roam-querying.md](docs/roam-querying.md) — Datalog query language, query structure, and all queries used in this project
- [docs/roam-schema.md](docs/roam-schema.md) — Full Roam attribute schema retrieved from a live graph
- [docs/MDBUNDLE_SETUP.md](docs/MDBUNDLE_SETUP.md) — macOS `.mdbundle` integration guide

## License

[MIT](LICENSE)
