#!/bin/bash
# Wrapper script to run dump_roam_tree.py with the correct Python environment
#
# Usage: ./dump-roam-tree.sh <page_title_or_node_uid> [--port <port>] [--graph <graph>] [--token <token>]
#                            [--node-props <props>] [--mode <v|n|vn>]
#
# --mode controls which tree(s) are printed: v=vertex (default), n=node, vn=both
#
# Environment variables (may be set instead of CLI flags):
#   GUFFIN_ROAM_LOCAL_API_PORT  — port for Roam Local API
#   GUFFIN_ROAM_GRAPH_NAME      — name of the Roam graph
#   GUFFIN_ROAM_API_TOKEN       — bearer token for Roam Local API authentication

# Get the repo root (one level above this script's directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Activate the virtual environment
source "$REPO_ROOT/.venv/bin/activate"

# Run the entry point with all arguments
dump-roam-tree "$@"
