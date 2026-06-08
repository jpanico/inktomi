# Test Fixtures

This directory contains test data used by the guffin test suite.

## Directory Structure

- `images/` — Test images referenced by live integration tests
- `json/` — Raw Roam Local API response payloads used by unit tests
- `markdown/` — Expected CommonMark output files and supporting assets
- `yaml/` — Serialized `RoamNode` and `Vertex` trees used by unit tests

## Files

### images/
- `flower.jpeg` — JPEG fixture used in `TestFetchRoamAssetFetch::test_live`
- `test_article_1.png` — Screenshot of the `[[Test Article]] 1` page in Roam (reference only)
- `test_article_2.png` — Screenshot of the `[[Test Article]] 2` page in Roam (reference only)

### json/
- `image_node.json` — Raw Roam node payload for a Firestore image block; used in `TestTranscribeNode::test_transcribes_image_node_from_fixture`

### markdown/
- `descendant_rule.md` — CSS descendant-rule reference snippet used in `TestExportRoamPageNoBundle`
- `flower.jpeg` — Image asset bundled alongside `test_article_1_expected.md` in the no-bundle export test

### yaml/
- *(see **Test Articles**)*

## Test Articles

Two live Roam pages serve as the primary test sources: `[[Test Article]] 1` and
`[[Test Article]] 2`.  For each source, `tests/regen_fixtures.py` generates six
fixture files that capture different stages and views of the data pipeline.

### No-refs fixture set (`include_refs=False`) — a linear pipeline

These three fixtures represent successive stages of the export pipeline applied
to the anchor subtree alone, with no referenced pages included:

| Fixture | What it captures |
|---|---|
| `<prefix>_nodes.yaml` | The Roam nodes (page + blocks) as parsed `RoamNode` model objects |
| `<prefix>_vertices.yaml` | The same subtree transcribed into the export model (`VertexTree`) |
| `<prefix>_expected.md` | The fully rendered CommonMark output |

### With-refs fixture set (`include_refs=True`) — three views of the same fetch

These three fixtures are all derived from a single API call that pulls the anchor
subtree together with every page and block it references.  Rather than a pipeline,
they are three different lenses on the same underlying data:

| Fixture | What it captures |
|---|---|
| `<prefix>_raw_result.yaml` | The raw Datalog wire response before any `RoamNode` parsing |
| `<prefix>_anchor_tree.yaml` | The `NodeTree` of the anchor subtree itself (within the broader refs fetch) |
| `<prefix>_nodes_by_uid.yaml` | All fetched nodes — anchor subtree plus every referenced page/block — keyed by UID |

## Usage

Fixture paths are resolved via constants defined in `tests/conftest.py`:

```python
from conftest import FIXTURES_IMAGES_DIR, FIXTURES_JSON_DIR, FIXTURES_MD_DIR, FIXTURES_YAML_DIR

data = (FIXTURES_YAML_DIR / "test_article_1_vertices.yaml").read_text()
image = (FIXTURES_IMAGES_DIR / "flower.jpeg").read_bytes()
```

To regenerate fixtures from the live Roam graph:

```bash
source .venv/bin/activate
python tests/regen_fixtures.py "[[Test Article]] 1" --prefix test_article_1
python tests/regen_fixtures.py "[[Test Article]] 2" --prefix test_article_2
```
