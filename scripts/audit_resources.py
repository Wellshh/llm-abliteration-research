"""T00 read-only CLI. No CUDA allocation or reservation lifecycle action."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minicpm_research.resources import ResourceError, audit_resources


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--seconds", type=float, default=60,
                        help="60 seconds minimum for formal admission; 0 is an inspection-only snapshot")
    parser.add_argument("--interval-seconds", type=float, default=5)
    args = parser.parse_args()
    try:
        report = audit_resources(args.output_dir, seconds=args.seconds,
                                 interval_seconds=args.interval_seconds)
    except (OSError, ValueError, ResourceError) as exc:
        print(f"Resource audit failed: {exc}", file=sys.stderr)
        return 2
    errors = [error for sample in report["samples"] for error in sample["errors"]]
    errors += ["Initial nvidia-smi command failed" for command in report["initial_commands"]
               if command["exit_code"] != 0]
    print(json.dumps({"report": str((args.output_dir / "RESOURCE_AUDIT.json").resolve()),
                      "samples": len(report["samples"]), "errors": errors,
                      "formal_sampling_complete": report["formal_sampling_complete"],
                      "gpu_experiment_run": False}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
