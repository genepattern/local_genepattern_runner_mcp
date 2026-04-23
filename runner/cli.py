#!/usr/bin/env python3
"""Command-line interface for running GenePattern modules locally."""

import argparse
import json
import os
import sys
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

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
    """If val is an existing local path, return its absolute form; otherwise return val."""
    candidate = Path(val).expanduser()
    if candidate.exists():
        return str(candidate.resolve())
    return val


def _is_url(val: str) -> bool:
    return val.startswith(("http://", "https://", "ftp://", "s3://"))


def _try_download(url: str, dest_dir: Path) -> Optional[Path]:
    """Attempt to download url into dest_dir. Returns local Path on success, None on failure."""
    filename = url.split("?")[0].rstrip("/").split("/")[-1] or "download"
    dest = dest_dir / filename
    try:
        print(f"  Downloading {url} ...", end=" ", flush=True)
        urllib.request.urlretrieve(url, str(dest))
        size = dest.stat().st_size
        print(f"OK ({size:,} bytes)")
        return dest
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        print(f"failed ({exc})")
        return None


def _resolve_file_param(name: str, value: str, download_dir: Path) -> str:
    """
    Resolve a parameter value that may be a URL or local path.

    - Local path that exists  → return absolute path
    - Reachable URL           → download and return local path
    - Unreachable URL         → prompt user for a local path or alternative URL
    """
    if not _is_url(value):
        return _resolve(value)

    local = _try_download(value, download_dir)
    if local:
        return str(local)

    # Download failed — prompt the user
    print(f"\n  Could not retrieve '{name}' from:\n    {value}")
    while True:
        alt = input(
            f"  Enter a local file path or URL for '{name}' (or press Enter to skip): "
        ).strip()
        if not alt:
            print(f"  Skipping '{name}' — original URL will be passed through.")
            return value
        if _is_url(alt):
            local = _try_download(alt, download_dir)
            if local:
                return str(local)
            print("  Download failed. Try again.")
        else:
            candidate = Path(alt).expanduser().resolve()
            if candidate.exists():
                return str(candidate)
            print(f"  File not found: {candidate}. Try again.")


def _load_yaml(params_path: Path) -> tuple:
    """Load a YAML run config. Returns (zip_path, output_dir_or_None, params_dict)."""
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
    output_dir = config.get("output_dir")
    raw_params = config.get("parameters") or {}
    return zip_path, output_dir, {k: str(v) for k, v in raw_params.items()}


def _load_log(log_path: Path, zip_arg: Optional[str]) -> tuple:
    """
    Load a GenePattern execution log. Returns (zip_path, output_dir_or_None, params_dict).
    zip_arg must be provided (log files don't embed a module zip path).
    """
    from gp_runner.log_parser import parse_execution_log

    if not zip_arg:
        print(
            "Error: --zip is required when the input is a GenePattern execution log.",
            file=sys.stderr,
        )
        sys.exit(1)

    info = parse_execution_log(str(log_path))
    if info.get("module_name"):
        print(f"Module from log: {info['module_name']}", file=sys.stderr)
    if info.get("server"):
        print(f"Original server: {info['server']}", file=sys.stderr)

    zip_path = _resolve(zip_arg)
    return zip_path, None, info["parameters"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a GenePattern module locally using Docker.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Input formats
-------------
YAML run config (run.yaml):
  module: path/to/module.zip
  output_dir: ./outputs          # optional, defaults to current directory
  parameters:
    raw.data: path/to/input.txt
    normalization.method: relative
    value.column: "4"

GenePattern execution log (gp_execution_log.txt) — requires --zip:
  The log produced by a GenePattern server run.  File-parameter URLs are
  downloaded automatically; if a URL is unreachable you will be prompted for
  a local file path or alternative URL.

Examples:
  gp-runner run.yaml
  gp-runner gp_execution_log.txt --zip path/to/module.zip
  gp-runner run.yaml --output-dir /tmp/results
  gp-runner run.yaml --parse-only
""",
    )
    parser.add_argument(
        "input_file",
        help="YAML run config or GenePattern execution log (gp_execution_log.txt)",
    )
    parser.add_argument(
        "--zip", "-z",
        dest="zip_path",
        help="Module zip file (required when input is a GenePattern execution log)",
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

    input_path = Path(args.input_file).expanduser().resolve()
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Detect format
    from gp_runner.log_parser import is_execution_log
    if is_execution_log(str(input_path)):
        zip_path, yaml_output_dir, raw_params = _load_log(input_path, args.zip_path)
    else:
        zip_path, yaml_output_dir, raw_params = _load_yaml(input_path)

    # Override zip path if --zip was given explicitly (even in YAML mode)
    if args.zip_path:
        zip_path = _resolve(args.zip_path)

    if not Path(zip_path).exists():
        print(f"Error: module zip not found: {zip_path}", file=sys.stderr)
        sys.exit(1)

    if args.parse_only:
        print(parse_gp_module(zip_path))
        return

    # Output directory: CLI arg > YAML value > cwd
    if args.output_dir:
        output_dir = str(Path(args.output_dir).expanduser().resolve())
    elif yaml_output_dir:
        output_dir = str(Path(str(yaml_output_dir)).expanduser().resolve())
    else:
        output_dir = str(Path.cwd())

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Resolve parameters: download URLs, resolve local paths
    with tempfile.TemporaryDirectory(prefix="gp-runner-dl-") as dl_dir:
        dl_path = Path(dl_dir)
        resolved_params: dict = {}
        for key, value in raw_params.items():
            if _is_url(value):
                resolved_params[key] = _resolve_file_param(key, value, dl_path)
            else:
                resolved_params[key] = _resolve(value)

        print(f"\nModule:           {zip_path}", file=sys.stderr)
        print(f"Output directory: {output_dir}", file=sys.stderr)
        print("Parameters:", file=sys.stderr)
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
