#!/usr/bin/env python3
"""
MCP tools for running GenePattern modules in local Docker containers.
"""

import json
import os
import sys
import traceback
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP  # pyright: ignore[reportMissingImports]
except ImportError:
    print("Error: MCP package not found. Install with: pip install 'mcp[cli]'")
    sys.exit(1)

# Ensure the project root is on the path so gp_runner is importable
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
sys.path.insert(0, _root)

mcp = FastMCP("GenePattern-Runner")


@mcp.tool()
def parse_gp_module(zip_path: str) -> str:
    """
    Parse a GenePattern module zip file and return module information as JSON.

    Extracts the 'manifest' file from the zip and returns:
      - name, description, language, author, version
      - docker_image  (the job.docker.image value, colons unescaped)
      - command_line  (the commandLine template, with <param.name> placeholders)
      - parameters    (list of parameter dicts, each with name, type, optional,
                       description, choices, default_value, file_format, etc.)

    Args:
        zip_path: Absolute or ~ path to the GenePattern .zip module file.

    Returns:
        JSON string with the module info, or a JSON error object on failure.
    """
    try:
        from gp_runner.manifest_parser import extract_module_info
        info = extract_module_info(str(Path(zip_path).expanduser().resolve()))
        return json.dumps(info, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e), 'traceback': traceback.format_exc()})


@mcp.tool()
def run_gp_module(
    zip_path: str,
    param_values_json: str,
    output_dir: str,
) -> str:
    """
    Run a GenePattern module in a local Docker container.

    Steps performed automatically:
      1. Parse the manifest to get docker_image, commandLine, and parameters.
      2. Extract module files to a temp directory mounted as /module (read-only).
      3. Copy FILE input parameters to a work directory mounted as /work.
      4. Substitute all <param.name> placeholders (and <libdir>=>/module/) in
         the commandLine template.
      5. Run: docker run --rm -v <module>:/module:ro -v <work>:/work -w /work
                <docker_image> <constructed command>
      6. Copy all files from /work to output_dir.

    Args:
        zip_path:         Path to the GenePattern .zip module file.
        param_values_json: JSON object mapping parameter names to values.
                          For FILE parameters, supply the local file path —
                          the file is copied into the container automatically.
                          Example: {"input.file": "/data/expr.gct", "num.clusters": "5"}
        output_dir:       Directory where output files will be written.

    Returns:
        JSON with: job_id, exit_code, stdout, stderr, output_files (list),
        command (the full docker run string), success (bool).
    """
    try:
        from gp_runner.docker_runner import run_module
        param_values = json.loads(param_values_json)
        result = run_module(
            str(Path(zip_path).expanduser().resolve()),
            param_values,
            str(Path(output_dir).expanduser().resolve()),
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({
            'error': str(e),
            'traceback': traceback.format_exc(),
            'success': False,
        })


@mcp.tool()
def get_output_file_content(file_path: str) -> str:
    """
    Return the content of an output file in a display-ready form.

    - HTML / HTM  → type='html',   format='text',   content=<raw HTML string>
    - SVG         → type='image',  format='svg',    content=<raw SVG string>
    - PNG/JPG/GIF → type='image',  format='base64', content=<base64 string>,
                    mime_type indicates the exact image type
    - TXT/CSV/TSV/LOG/GCT etc. → type='text', format='text', content=<string>
    - Anything else → type='binary', content=None, size=<bytes>

    Args:
        file_path: Path to the output file.

    Returns:
        JSON with: name, path, size, type, mime_type, format, content (or None).
    """
    try:
        from gp_runner.docker_runner import describe_output_file
        result = describe_output_file(str(Path(file_path).expanduser().resolve()))
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({'error': str(e), 'traceback': traceback.format_exc()})
