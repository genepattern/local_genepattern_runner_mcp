#!/usr/bin/env python3
"""Command-line interface for running GenePattern modules locally."""

import argparse
import json
import os
import sys
from pathlib import Path

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
sys.path.insert(0, _here)
sys.path.insert(0, _root)

try:
    import yaml
except ImportError:
    print("Error: pyyaml is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

from tools import run_gp_module, parse_gp_module


def _resolve(val: str) -> str:
    """Resolve a path string; if it exists as a file, return its absolute path."""
    candidate = Path(val).expanduser()
    if candidate.exists():
        return str(candidate.resolve())
    return val


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a GenePattern module locally using Docker.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example YAML file (run.yaml):
  module: path/to/module.zip
  output_dir: ./outputs          # optional, defaults to current directory
  parameters:
    raw.data: path/to/input.txt
    normalization.method: relative
    value.column: "4"
    header.present: "FALSE"
""",
    )
    parser.add_argument(
        "params_file",
        help="YAML file containing 'module', optional 'output_dir', and 'parameters'",
    )
    parser.add_argument(
        "--output-dir", "-o",
        help="Output directory (overrides output_dir in YAML; defaults to current directory)",
    )
    parser.add_argument(
        "--parse-only",
        action="store_true",
        help="Parse and print module info as JSON without running it",
    )

    args = parser.parse_args()

    params_path = Path(args.params_file).expanduser().resolve()
    if not params_path.exists():
        print(f"Error: params file not found: {params_path}", file=sys.stderr)
        sys.exit(1)

    with open(params_path) as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        print("Error: YAML file must be a mapping/dictionary", file=sys.stderr)
        sys.exit(1)

    module_key = config.get("module") or config.get("zip_path")
    if not module_key:
        print(
            "Error: YAML must include a 'module' key with the path to the module zip file",
            file=sys.stderr,
        )
        sys.exit(1)

    zip_path = _resolve(str(module_key))
    if not Path(zip_path).exists():
        print(f"Error: module zip not found: {zip_path}", file=sys.stderr)
        sys.exit(1)

    if args.parse_only:
        print(parse_gp_module(zip_path))
        return

    # Output directory: CLI arg > YAML value > cwd
    if args.output_dir:
        output_dir = str(Path(args.output_dir).expanduser().resolve())
    elif "output_dir" in config:
        output_dir = str(Path(str(config["output_dir"])).expanduser().resolve())
    else:
        output_dir = str(Path.cwd())

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Resolve any parameter value that is an existing file path to absolute
    raw_params = config.get("parameters") or {}
    resolved_params = {k: _resolve(str(v)) for k, v in raw_params.items()}

    print(f"Module:           {zip_path}", file=sys.stderr)
    print(f"Output directory: {output_dir}", file=sys.stderr)
    print(f"Parameters:", file=sys.stderr)
    for k, v in resolved_params.items():
        print(f"  {k}: {v}", file=sys.stderr)

    result_json = run_gp_module(
        zip_path=zip_path,
        param_values_json=json.dumps(resolved_params),
        output_dir=output_dir,
    )

    result = json.loads(result_json)

    if result.get("success"):
        print(f"\nSuccess (exit code: {result.get('exit_code', 0)})")
        output_files = result.get("output_files", [])
        if output_files:
            print(f"\nOutput files ({len(output_files)}) written to: {output_dir}")
            for f in output_files:
                name = f.get("name", f.get("path", ""))
                size = f.get("size", 0)
                print(f"  {name}  ({size:,} bytes)")
        if result.get("stdout"):
            print(f"\nStdout:\n{result['stdout']}")
    else:
        print(f"\nFailed (exit code: {result.get('exit_code', -1)})", file=sys.stderr)
        if result.get("stderr"):
            print(f"\nStderr:\n{result['stderr']}", file=sys.stderr)
        if result.get("stdout"):
            print(f"\nStdout:\n{result['stdout']}")
        if result.get("error"):
            print(f"\nError: {result['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
