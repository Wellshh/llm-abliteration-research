"""CPU-only independent verification of batch 6 sidecars; never starts a model."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
os.environ["CUDA_VISIBLE_DEVICES"] = ""
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from minicpm_research.runs import file_hash, now
from run_pilot import build_token_anchor


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    assert sys.platform == "linux", "run on the authoritative research checkout"
    expected_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    erratum_path = ROOT / "reports/T04_RESOURCE_MEASURABILITY_SUMMARY_20260914.ATTEMPT_CLASSIFICATION_ERRATUM.json"
    erratum = read(erratum_path)
    summary_path = ROOT / erratum["annotates"]
    assert file_hash(summary_path) == erratum["annotated_sha256"]
    original_bytes = subprocess.check_output(["git", "show", f"HEAD:{erratum['annotates']}"], cwd=ROOT)
    assert original_bytes == summary_path.read_bytes()
    ledger = read(ROOT / "artifacts/budgets/phase0_gpu_budget.json")
    attempts = {a["attempt_id"]: a for a in ledger["attempts"]}
    assert len(attempts) == len(ledger["attempts"])
    classification = erratum["corrected_attempt_classification"]
    run = ROOT / "artifacts/runs/t04-baseline-V" / classification["run_id"]
    for item in classification["attempts"]:
        aid = item["attempt_id"]
        admitted = (run / f"admission-{aid}.json").is_file()
        assert admitted == item["admission_json_present"] == (aid in attempts)
        assert read(run / f"failure-{aid}.json") == item["failure_json"]
        assert (run / f"audit-{aid}").is_dir() == item["audit_dir_present"]
        assert item["classification"] == ("post_admission_setup_failure" if admitted else "pre_admission")
        assert item["charged_seconds"] == (attempts[aid]["charged_seconds"] if admitted else 0)
    authoritative = {"887571efd14d08b46a94", "939ad1d5254ed2960bd9", "7b0b4c88c0af90449723", "3ec2805afe33d3ef9ee9"}
    superseded = {"e40e1134fd4d256d9b45", "f4e278b2ef66a5b5a7fc"}
    buckets = dict.fromkeys(("T03_hooks", "T04_authoritative", "T04_superseded_t", "T04_setup_failure_post_admission", "T04_pre_admission"), 0.0)
    for item in attempts.values():
        rid = item["run_id"]
        if rid.startswith("T03:"):
            bucket = "T03_hooks"
        elif rid in authoritative:
            bucket = "T04_authoritative"
        elif rid in superseded:
            bucket = "T04_superseded_t"
        else:
            assert rid in {"51f6ad0cb3c6792c0104", "27a5f2edf23fa9fd17c4"}
            bucket = "T04_setup_failure_post_admission"
        buckets[bucket] += item["charged_seconds"]
    assert all(value == erratum["corrected_itemization_from_ledger"][key] for key, value in buckets.items())
    total = sum(a["charged_seconds"] for a in attempts.values())
    assert sum(buckets.values()) == total == erratum["corrected_itemization_from_ledger"]["TOTAL"] == read(summary_path)["budget"]["P0_total_charged_seconds"]

    lock = read(ROOT / "artifacts/model/MODEL_MANIFEST.json")
    # Verify tokenizer/template inputs only; no model weights are loaded or changed.
    model_dir = Path(lock["local_dir"])
    for name, metadata in lock["files"].items():
        if not name.endswith(".safetensors"):
            assert file_hash(model_dir / name) == metadata["sha256"]
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    examples = {e["example_id"]: e for e in (json.loads(line) for line in (ROOT / "artifacts/data/pilot.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())}
    verified_anchors = []
    for rid in sorted(authoritative):
        directory, = ROOT.glob(f"artifacts/runs/*/{rid}")
        if not directory.parent.name.endswith("T"):
            continue
        sidecar = read(directory / "TOKEN_ANCHORS_ERRATUM_CPU_REAUDIT.json")
        assert file_hash(ROOT / sidecar["erratum_for"]) == sidecar["erratum_for_sha256"]
        rows = {r["example_id"]: r for p in directory.glob("shard-*.json") for r in read(p)["rows"]}
        for anchor in sidecar["corrected_anchors"]:
            eid = anchor["example_id"]
            rebuilt = build_token_anchor(tokenizer, examples[eid])
            assert rebuilt == anchor, eid
            assert rebuilt["encoded_prompt_length"] == rows[eid]["prompt_tokens"]
        assert {a["example_id"] for a in sidecar["corrected_anchors"]} == set(rows)
        verified_anchors.append({"run_id": rid, "lengths": [a["encoded_prompt_length"] for a in sidecar["corrected_anchors"]], "full_anchor_cpu_equality": True})

    replay_command = [sys.executable, "reports/review_20260914/reproduce_review.py"]
    replay = subprocess.run(replay_command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
    (OUT / "historical_replay.stdout.json").write_text(replay.stdout, encoding="utf-8")
    (OUT / "historical_replay.stderr.log").write_text(replay.stderr, encoding="utf-8")
    assert replay.returncode == 0, replay.stderr
    git_checks = subprocess.run(["git", "-c", "core.whitespace=cr-at-eol", "diff", "--check"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert git_checks.returncode == 0, git_checks.stdout
    original_changes = subprocess.check_output(["git", "diff", "--name-only", "--", "artifacts/runs", "artifacts/budgets", "reports/T04_RESOURCE_MEASURABILITY_SUMMARY_20260914.json"], cwd=ROOT, text=True)
    assert not original_changes.strip(), original_changes
    evidence = {"type": "batch6_independent_cpu_closeout", "at": now(), "base_commit": expected_head,
        "gpu_execution": "not_run", "model_weights_loaded": False,
        "summary_sha256": file_hash(summary_path), "erratum_sha256": file_hash(erratum_path),
        "attempt_classification_verified": True, "ledger_buckets": buckets, "ledger_total_seconds": total,
        "token_anchors": verified_anchors, "historical_replay_command": replay_command,
        "historical_replay_exit_code": replay.returncode, "diff_check_exit_code": git_checks.returncode,
        "diff_check_note": "cr-at-eol permits the existing CRLF source file; no source normalization performed",
        "original_run_and_budget_artifacts_changed": False}
    (OUT / "verification.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == "__main__":
    main()
