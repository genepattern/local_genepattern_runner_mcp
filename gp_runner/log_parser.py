"""Parse a GenePattern server execution log (gp_execution_log.txt)."""

from pathlib import Path
from typing import Dict, Optional


def parse_execution_log(log_path: str) -> Dict:
    """
    Parse a GenePattern execution log file.

    Returns a dict with:
        module_name  – e.g. 'tfsites.NormalizeTfDNAAffinityData'
        server       – GP server base URL, or None
        parameters   – {param_name: raw_value}  (URLs preserved as-is)
    """
    result: Dict = {"module_name": None, "server": None, "parameters": {}}
    in_params = False

    for raw in Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line.startswith("#"):
            continue
        content = line[1:].strip()

        if content.startswith("Module:"):
            # "Module: tfsites.NormalizeTfDNAAffinityData urn:lsid:..."
            parts = content[len("Module:"):].strip().split()
            result["module_name"] = parts[0] if parts else None

        elif "server:" in content:
            # "# ET(ms): 64897    server:  https://cloud.genepattern.org/gp/"
            idx = content.index("server:")
            result["server"] = content[idx + len("server:"):].strip()

        elif content.startswith("Parameters:"):
            in_params = True

        elif in_params and "=" in content:
            # "   raw.data = https://...s3...txt # file size \t1383935"
            key, _, rest = content.partition("=")
            key = key.strip()
            # Strip trailing "# ..." comment (note: URLs may contain #fragment with no spaces)
            value = rest.split(" # ")[0].strip()
            if key:
                result["parameters"][key] = value

    return result


def is_execution_log(file_path: str) -> bool:
    """Return True if the file looks like a GenePattern execution log."""
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    return stripped.startswith("# Job:")
    except OSError:
        pass
    return False
