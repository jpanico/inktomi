"""Unit tests for guffin.export_roam_tree."""

import logging
import pathlib
from typing import Final
from unittest.mock import patch

from typer.testing import CliRunner

from guffin.export_roam_tree import app
from guffin.roam_node_fetch_result import NodeFetchAnchor, NodeFetchResult, NodeFetchSpec

from conftest import FIXTURES_MD_DIR, article0_node_tree


class TestExportRoamTreeNoBundle:
    """Tests for export_roam_tree in --no-bundle mode."""

    def test_no_bundle_writes_expected_markdown(self, tmp_path: pathlib.Path) -> None:
        """Test that --no-bundle exports the correct CommonMark document.

        Loads nodes from the test_article_0_nodes.yaml fixture, mocks the Roam
        Local API fetch, invokes the CLI with --no-bundle, and asserts that the
        written .md file matches test_article_0_expected.md.
        """
        fetch_spec: Final[NodeFetchSpec] = NodeFetchSpec(
            anchor=NodeFetchAnchor(qualifier="Test Article 0"), include_refs=False
        )
        mock_result: Final[NodeFetchResult] = NodeFetchResult.from_network(
            article0_node_tree().tree_network, fetch_spec, raw_result=[[{}]]
        )
        runner: CliRunner = CliRunner()

        with patch(
            "guffin.roam_tree_loader.FetchRoamNodes.fetch_roam_nodes",
            return_value=mock_result,
        ):
            # configure_logging() runs at import time and installs a StreamHandler
            # on the root logger.  CliRunner closes its captured stream after invoke,
            # leaving a dangling handler that raises ValueError on the next write.
            # Temporarily clear root handlers to prevent that conflict.
            saved_handlers = logging.root.handlers[:]
            logging.root.handlers.clear()
            try:
                result = runner.invoke(
                    app,
                    [
                        "Test Article 0",
                        "--port",
                        "3333",
                        "--graph",
                        "SCFH",
                        "--token",
                        "tok",
                        "--output-dir",
                        str(tmp_path),
                        "--no-bundle",
                    ],
                )
            finally:
                logging.root.handlers = saved_handlers

        assert result.exit_code == 0, result.output
        output_file: pathlib.Path = tmp_path / "Test_Article_0.md"
        assert output_file.exists()
        expected: str = (FIXTURES_MD_DIR / "test_article_0_expected.md").read_text()
        assert output_file.read_text() == expected
