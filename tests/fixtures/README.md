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

### json/
- `image_node.json` — Raw Roam node payload for a Firestore image block; used in `TestTranscribeNode::test_transcribes_image_node_from_fixture`

### markdown/
- `test_article_0_expected.md` — Expected CommonMark output for `Test Article 0`; used in `TestRenderTestArticle::test_article_fixture_renders_correctly`
- `descendant_rule.md` — CSS descendant-rule reference snippet used in `TestExportRoamPageNoBundle`
- `flower.jpeg` — Image asset bundled alongside `test_article_0_expected.md` in the no-bundle export test

### yaml/
- `test_article_0_nodes.yaml` — Serialized `NodeTree` for `Test Article 0`; used in `TestNodeTree` and `TestNodeTreeDFSIterator`
- `test_article_0_vertices.yaml` — Serialized `VertexTree` for `Test Article 0`; used in `TestVertexTreeDFSIterator`, `TestRenderTestArticle`, and `TestTranscribeArticleFixture`

## Usage

Fixture paths are resolved via constants defined in `tests/conftest.py`:

```python
from conftest import FIXTURES_IMAGES_DIR, FIXTURES_JSON_DIR, FIXTURES_MD_DIR, FIXTURES_YAML_DIR

data = (FIXTURES_YAML_DIR / "test_article_0_vertices.yaml").read_text()
image = (FIXTURES_IMAGES_DIR / "flower.jpeg").read_bytes()
```
