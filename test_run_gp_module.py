#!/usr/bin/env python3
"""Direct test script for runner.tools.run_gp_module."""

import json
from pathlib import Path

from runner.tools import run_gp_module


def main() -> None:
    zip_path = "/Users/liefeld/GenePattern/modules/tfsites.NormalizeTfDNAAffinityData/build/tfsites.NormalizeTfDNAAffinityData.zip"

    param_values = {
        "raw.data": "/Users/liefeld/GenePattern/modules/tfsites.NormalizeTfDNAAffinityData/gpunit/data/01-input_ets-raw-pbm-data.txt",
        "core.binding.site.definition": "NNGGAWNN",
        "DNA.sequence.column": "1",
        "normalization.method": "relative",
        "value.column": "4",
        "header.present": "FALSE",
    }

    output_dir = Path("/Users/liefeld/projects/gp-runner/test_outputs/normalize_tf_dna_affinity")
    output_dir.mkdir(parents=True, exist_ok=True)

    result_json = run_gp_module(
        zip_path=zip_path,
        param_values_json=json.dumps(param_values),
        output_dir=str(output_dir),
    )

    try:
        parsed = json.loads(result_json)
        print(json.dumps(parsed, indent=2))
    except json.JSONDecodeError:
        print(result_json)


if __name__ == "__main__":
    main()


