#!/usr/bin/env python3
"""
MCP Server — GenePattern Runner

Exposes three tools to Claude Desktop / Claude Code:
  parse_gp_module        — parse a module zip and return parameter schema
  run_gp_module          — run the module in a local Docker container
  get_output_file_content — fetch output files for inline display

Usage:
    python runner/server.py
"""

import os
import sys

# Support running from both the project root and from runner/
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
sys.path.insert(0, _here)
sys.path.insert(0, _root)

try:
    from tools import mcp
except ImportError as e:
    print(f"Error: could not import tools module: {e}")
    print("Run from the project root: python runner/server.py")
    sys.exit(1)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
