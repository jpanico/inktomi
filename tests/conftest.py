"""Shared pytest configuration and test infrastructure for the guffin test suite."""

import os
import pathlib
from typing import Final

import pytest
import yaml

from guffin.graph import VertexTree, vertex_adapter
from guffin.roam.roam_local_api import ApiEndpoint, ApiEndpointURL
from guffin.roam.roam_node import NodeType, RoamNode, node_type
from guffin.roam.roam_tree import NodeTree
from guffin.roam.roam_primitives import IdObject

FIXTURES_YAML_DIR: pathlib.Path = pathlib.Path(__file__).parent / "fixtures" / "yaml"
"""Absolute path to the ``tests/fixtures/yaml/`` directory."""

FIXTURES_JSON_DIR: pathlib.Path = pathlib.Path(__file__).parent / "fixtures" / "json"
"""Absolute path to the ``tests/fixtures/json/`` directory."""

FIXTURES_IMAGES_DIR: pathlib.Path = pathlib.Path(__file__).parent / "fixtures" / "images"
"""Absolute path to the ``tests/fixtures/images/`` directory."""

FIXTURES_MD_DIR: pathlib.Path = pathlib.Path(__file__).parent / "fixtures" / "markdown"
"""Absolute path to the ``tests/fixtures/markdown/`` directory."""

STUB_TIME: int = 0
"""Stub value for ``RoamNode.time`` in tests where the timestamp is irrelevant."""

STUB_USER: IdObject = IdObject(id=1)
"""Stub value for ``RoamNode.user`` in tests where the user is irrelevant."""


@pytest.fixture
def api_endpoint() -> ApiEndpoint:
    """Return a minimal :class:`~guffin.roam.roam_local_api.ApiEndpoint` for unit tests."""
    return ApiEndpoint(
        url=ApiEndpointURL(local_api_port=3333, graph_name="test-graph"),
        bearer_token="test-token",
    )


@pytest.fixture
def live_api_endpoint() -> ApiEndpoint:
    """Return a live :class:`~guffin.roam.roam_local_api.ApiEndpoint` built from env vars.

    Requires ``GUFFIN_ROAM_LOCAL_API_PORT``, ``GUFFIN_ROAM_GRAPH_NAME``, and ``GUFFIN_ROAM_API_TOKEN``
    to be set in the environment.  Intended for use in tests marked ``@pytest.mark.live``.
    """
    return ApiEndpoint.from_parts(
        local_api_port=int(os.environ["GUFFIN_ROAM_LOCAL_API_PORT"]),
        graph_name=os.environ["GUFFIN_ROAM_GRAPH_NAME"],
        bearer_token=os.environ["GUFFIN_ROAM_API_TOKEN"],
    )


def article1_node_tree() -> NodeTree:
    """Load and return the ``[[Test Article]] 1`` :class:`~guffin.roam.roam_tree.NodeTree` from its YAML fixture."""
    raw: Final[list[dict[str, object]]] = yaml.safe_load((FIXTURES_YAML_DIR / "test_article_1_nodes.yaml").read_text())
    network: Final[list[RoamNode]] = [RoamNode.model_validate(r) for r in raw]
    root_node: Final[RoamNode] = next(n for n in network if node_type(n) == NodeType.ROAM_PAGE)
    return NodeTree.build(super_network=network, root_node=root_node)


def article1_vertex_tree() -> VertexTree:
    """Load and return the ``[[Test Article]] 1`` :class:`~guffin.graph.VertexTree` from its YAML fixture."""
    raw: Final[list[dict[str, object]]] = yaml.safe_load(
        (FIXTURES_YAML_DIR / "test_article_1_vertices.yaml").read_text()
    )
    return VertexTree(vertices=[vertex_adapter.validate_python(r) for r in raw])
