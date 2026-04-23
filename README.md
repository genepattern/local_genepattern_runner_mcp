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

The CLI accepts two input formats: a **YAML run config** or a **GenePattern execution log**.
The format is detected automatically from the file content.

### Format 1 — YAML run config

```yaml
module: path/to/module.zip          # required — relative to cwd or absolute
output_dir: ./my-outputs            # optional — defaults to current directory

parameters:
  param-name-1: value1
  param-name-2: path/to/input.txt   # file paths are resolved automatically
  param-name-3: "4"                 # quote numeric strings to keep them as strings
```

### Format 2 — GenePattern execution log (`gp_execution_log.txt`)

When you run a job on the public GenePattern server, a log file is generated that records
every parameter and input used.  You can re-run the same job locally by passing that log
directly to the CLI.  Because the log does not embed a module zip path you must also supply
`--zip`.

File-parameter values in the log are server URLs.  The CLI will attempt to download each
one automatically.  If a URL is unreachable you will be prompted interactively to supply
a local file path or an alternative URL.

```
# Job: 689853
# User: ted
# Submitted: 2026-04-06 18:57:59.0
...
# Module: tfsites.NormalizeTfDNAAffinityData urn:lsid:genepattern.org:module.analysis:00441:4
# Parameters:
#    raw.data = https://datasets-tfsites-org.s3.amazonaws.com/...CrebA_8mers.txt # file size 1383935
#    core.binding.site.definition = NTGNNNNA
#    DNA.sequence.column = 1
#    normalization.method = relative
#    value.column = 4
#    header.present = TRUE
```

### Running the CLI

```bash
# YAML format (recommended — no activation needed)
uv run python runner/cli.py path/to/run.yaml

# Execution log format — module zip must be provided with --zip
uv run python runner/cli.py gp_execution_log.txt --zip path/to/module.zip

# Override the output directory
uv run python runner/cli.py path/to/run.yaml --output-dir /tmp/my-results

# Parse the module manifest and print parameter info without running
uv run python runner/cli.py path/to/run.yaml --parse-only

# Or after installing the package with: uv pip install -e .
gp-runner path/to/run.yaml
gp-runner gp_execution_log.txt --zip path/to/module.zip
```

---

### Example 1: YAML input — NormalizeTfDNAAffinityData

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

Run from the project root:

```bash
uv run python runner/cli.py test_data/normalize_tf_dna_affinity/run.yaml
```

---

### Example 2: GenePattern execution log input

```bash
uv run python runner/cli.py \
  test_data/normalize_tf_dna_affinity/gp_execution_log.txt \
  --zip test_data/normalize_tf_dna_affinity/tfsites.NormalizeTfDNAAffinityData.zip \
  --output-dir test_outputs/normalize_tf_dna_affinity
```

If the S3 URL in the log is publicly accessible, the input file is downloaded automatically.
If it is not accessible (e.g. requires authentication or has expired), you will be prompted:

```
  Downloading https://datasets-tfsites-org.s3.amazonaws.com/.../CrebA_8mers.txt ... failed (HTTP 403)

  Could not retrieve 'raw.data' from:
    https://datasets-tfsites-org.s3.amazonaws.com/.../CrebA_8mers.txt
  Enter a local file path or URL for 'raw.data' (or press Enter to skip): /path/to/local/CrebA_8mers.txt
```

---

### CLI reference

```
usage: cli.py [-h] [--zip ZIP_PATH] [--output-dir OUTPUT_DIR] [--parse-only] input_file

positional arguments:
  input_file            YAML run config or GenePattern execution log (auto-detected)

options:
  -h, --help            show this help message and exit
  --zip, -z ZIP_PATH    Module zip file (required when input is an execution log)
  --output-dir, -o      Output directory (overrides output_dir in YAML; defaults to cwd)
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
│   ├── docker_runner.py     # executes modules in Docker
│   └── log_parser.py        # parses GenePattern server execution logs
├── runner/
│   ├── server.py            # MCP server entry point
│   ├── tools.py             # MCP tool definitions (parse, run, get-content)
│   └── cli.py               # terminal CLI entry point
├── test_data/
│   └── normalize_tf_dna_affinity/
│       ├── run.yaml                              # example YAML run config
│       ├── gp_execution_log.txt                  # example execution log
│       ├── 01-input_ets-raw-pbm-data.txt         # example input file
│       └── tfsites.NormalizeTfDNAAffinityData.zip
├── pyproject.toml
├── uv.lock
└── requirements.txt
```
