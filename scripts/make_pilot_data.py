"""Generate deterministic pilot JSONL plus an auditable, idempotent manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minicpm_research.data import build_pilot
from minicpm_research.verifier import validate_dataset


def _write_once(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"Refusing to overwrite different content: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        # Hard-link publication is atomic and cannot overwrite another writer.
        os.link(temporary, path)
    except FileExistsError:
        if not path.exists() or path.read_bytes() != content:
            raise
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/data/pilot.jsonl"))
    parser.add_argument("--seed", type=int, default=20260910)
    parser.add_argument("--verdict-families", type=int, default=120)
    parser.add_argument("--tool-families", type=int, default=60)
    args = parser.parse_args()
    try:
        examples = build_pilot(args.seed, args.verdict_families, args.tool_families)
        report = validate_dataset(examples)
        content = "".join(json.dumps(example, ensure_ascii=False, sort_keys=True) + "\n" for example in examples).encode("utf-8")
        source_root = Path(__file__).resolve().parents[1] / "src" / "minicpm_research"
        manifest = {"schema_version": "pilot-v1", "seed": args.seed, "verdict_families": args.verdict_families,
            "tool_families": args.tool_families, "data_sha256": hashlib.sha256(content).hexdigest(),
            "source_sha256": {name: hashlib.sha256((source_root / name).read_bytes()).hexdigest() for name in ("data.py", "verifier.py", "sandbox.py")},
            "validation": report, "scope": "synthetic_V_T_pilot_only", "sealed_test_created": False,
            "safety_manipulation_check": "NOT_IMPLEMENTED_pending_licensed_S_and_independent_audit",
            "C_controls": "NOT_IMPLEMENTED", "human_gold_audit": "pending_two_independent_reviewers",
            "native_tool_parser_validation": "native_xml_v1_implemented_unit_validated; real_model_output_validation_pending_gpu", "label_tokenization": "A_B_C_single_token_in_locked_template_anchor_context",
            "length_and_negation_matching": "requires_pilot_audit", "unseen_formal_templates": "not_created_pilot_only",
            "gpu_execution": "未运行"}
        _write_once(args.output, content)
        manifest_path = args.output.with_suffix(args.output.suffix + ".manifest.json")
        _write_once(manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        print(json.dumps({"output": str(args.output), "manifest": str(manifest_path), **report}, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as error:
        print(f"pilot generation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
