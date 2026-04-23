# GenePattern Local Module Runner (MCP + CLI)

Run GenePattern modules locally in Docker containers, either from the terminal via a YAML-driven CLI or as an MCP server for AI assistants (Claude, Cursor, etc.).

> **Note on Docker image architecture:** All GenePattern modules are run as `linux/amd64` containers. This matches the architecture used by the public GenePattern server, where modules have historically been developed and distributed. On Apple Silicon Macs (M1/M2/M3) Docker Desktop automatically emulates amd64 via Rosetta 2; on Linux and Intel Macs no emulation is needed.

## Prerequisites

- **Docker** – must be running ([install](https://docs.docker.com/get-docker/))
- **Python 3.10+**
- **uv** – fast Python package manager ([install](https://docs.astral.sh/uv/getting-started/installation/))

---

## Installation

```bash
git clone <repo-url>
cd local_genepattern_runner_mcp

# Install all dependencies (uses uv.lock for exact versions)
uv sync
```

> **Note:** If you add new dependencies after cloning, re-run `uv sync` to update your environment.

---

## CLI Usage

The CLI reads a YAML file that specifies the module zip, parameters, and optional output directory.

### YAML format

```yaml
module: path/to/module.zip          # required — relative to cwd or absolute
output_dir: ./my-outputs            # optional — defaults to current directory

parameters:
  param-name-1: value1
  param-name-2: path/to/input.txt   # file paths are resolved automatically
  param-name-3: "4"                 # quote numeric strings to keep them as strings
```

### Running the CLI

```bash
# Using uv run (recommended — no activation needed)
uv run python runner/cli.py path/to/run.yaml

# Or after installing the package
uv pip install -e .
gp-runner path/to/run.yaml

# Override the output directory at the command line
uv run python runner/cli.py path/to/run.yaml --output-dir /tmp/my-results

# Parse the module manifest and print parameter info without running
uv run python runner/cli.py path/to/run.yaml --parse-only
```

### Example: NormalizeTfDNAAffinityData

This example uses the test data included in the repository (identical to `test_run_gp_module.py`).

**YAML file** (`test_data/normalize_tf_dna_affinity/run.yaml`):

```yaml
module: test_data/normalize_tf_dna_affinity/tfsites.NormalizeTfDNAAffinityData.zip

output_dir: test_outputs/normalize_tf_dna_affinity

parameters:
  raw.data: test_data/normalize_tf_dna_affinity/01-input_ets-raw-pbm-data.txt
  core.binding.site.definition: NNGGAWNN
  DNA.sequence.column: "1"
  normalization.method: relative
  value.column: "4"
  header.present: "FALSE"
```

Run it from the project root:

```bash
uv run python runner/cli.py test_data/normalize_tf_dna_affinity/run.yaml
```

Expected output (stderr shows progress, stdout shows results):

```
Module:           /path/to/tfsites.NormalizeTfDNAAffinityData.zip
Output directory: /path/to/test_outputs/normalize_tf_dna_affinity
Parameters:
  raw.data: /path/to/01-input_ets-raw-pbm-data.txt
  core.binding.site.definition: NNGGAWNN
  ...

Success (exit code: 0)

Output files (3) written to: /path/to/test_outputs/normalize_tf_dna_affinity
  result.txt  (12,345 bytes)
  ...
```

### CLI reference

```
usage: cli.py [-h] [--output-dir OUTPUT_DIR] [--parse-only] params_file

positional arguments:
  params_file           YAML file with 'module', optional 'output_dir', and 'parameters'

options:
  -h, --help            show this help message and exit
  --output-dir, -o      Output directory (overrides output_dir in YAML)
  --parse-only          Print module parameter info as JSON without running
```

---

## MCP Server

The MCP server exposes three tools to AI assistants:

| Tool | Description |
|------|-------------|
| `parse_gp_module` | Parse a module zip and return its parameter schema as JSON |
| `run_gp_module` | Run a module in Docker and return results + output file list |
| `get_output_file_content` | Fetch an output file's content (text, base64, HTML) |

### Installing into Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "genepattern-runner": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/local_genepattern_runner_mcp",
        "python",
        "runner/server.py"
      ]
    }
  }
}
```

Restart Claude Desktop. The three GenePattern tools will appear in the tools panel.

### Installing into Cursor

Open **Cursor → Settings → MCP** (or edit `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "genepattern-runner": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/local_genepattern_runner_mcp",
        "python",
        "runner/server.py"
      ]
    }
  }
}
```

### Installing into Windsurf

Edit `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "genepattern-runner": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/local_genepattern_runner_mcp",
        "python",
        "runner/server.py"
      ]
    }
  }
}
```

### Installing into Claude Code (CLI)

```bash
claude mcp add genepattern-runner \
  uv -- run \
  --directory /absolute/path/to/local_genepattern_runner_mcp \
  python runner/server.py
```

### Installing into any MCP-compatible client (generic)

The server speaks the standard MCP protocol over stdio. Configure your client to run:

```
uv run --directory /absolute/path/to/local_genepattern_runner_mcp python runner/server.py
```

or, if you have the package installed in a virtual environment:

```
/path/to/venv/bin/python /absolute/path/to/local_genepattern_runner_mcp/runner/server.py
```

---

## About uv.lock

The `uv.lock` file together with `pyproject.toml` is all that is needed to reproduce the exact Python environment. Running `uv sync` reads both files and installs the pinned dependency tree. You do **not** need to run `pip install` separately.

---

## Project layout

```
local_genepattern_runner_mcp/
├── gp_runner/
│   ├── manifest_parser.py   # parses GenePattern module manifests
│   └── docker_runner.py     # executes modules in Docker
├── runner/
│   ├── server.py            # MCP server entry point
│   ├── tools.py             # MCP tool definitions (parse, run, get-content)
│   └── cli.py               # terminal CLI entry point
├── test_data/
│   └── normalize_tf_dna_affinity/
│       ├── run.yaml                              # example CLI run config
│       ├── 01-input_ets-raw-pbm-data.txt         # example input file
│       └── tfsites.NormalizeTfDNAAffinityData.zip
├── pyproject.toml
├── uv.lock
└── requirements.txt
```
