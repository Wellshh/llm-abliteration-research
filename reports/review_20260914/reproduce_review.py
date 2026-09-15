"""Read-only CPU review of T04 artifacts and bounded parser counterexamples."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from minicpm_research.data import build_pilot
from minicpm_research.evaluation import summarize
from minicpm_research.runs import RunStore, digest, file_hash
from minicpm_research.sandbox import Sandbox
from minicpm_research.tool_parser import evaluate_tool_turn
from minicpm_research.verifier import parse_verdict, validate_dataset


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ids = ["887571efd14d08b46a94", "939ad1d5254ed2960bd9", "7b0b4c88c0af90449723", "3ec2805afe33d3ef9ee9"]
    examples = [json.loads(line) for line in (ROOT / "artifacts/data/pilot.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    by_id = {e["example_id"]: e for e in examples}
    result = {"review_mode": "CPU_only_no_model_or_GPU_execution", "dataset": validate_dataset(examples), "runs": []}
    paired = {}
    for run_id in ids:
        directory, = ROOT.glob(f"artifacts/runs/*/{run_id}")
        manifest = read(directory / "manifest.json")
        rows = []
        for path in sorted(directory.glob("shard-*.json")):
            shard = read(path)
            assert digest(shard["rows"]) == shard["rows_sha256"]
            rows.extend(shard["rows"])
        assert digest(manifest)[:20] == run_id
        assert file_hash(ROOT / "artifacts/data/pilot.jsonl") == manifest["data_sha256"]
        assert file_hash(ROOT / "artifacts/model/MODEL_MANIFEST.json") == manifest["model_manifest_sha256"]
        assert {r["example_id"] for r in rows} == set(manifest["selected_example_ids"])
        for row in rows:
            example = by_id[row["example_id"]]
            assert row["gold"] == example["gold"]
            if row["task"] == "T":
                recomputed = evaluate_tool_turn(row["raw_text"], example, truncated=row["truncated"])
                assert all(row[k] == v for k, v in recomputed.items())
                Sandbox.replay(example["sandbox_state"], row["sandbox_events"])
            else:
                assert parse_verdict(row["raw_text"], example["label_map"], row["parsed"]["truncated"]) == row["parsed"]
        metrics = summarize(rows)
        stored = read(directory / "PILOT_BASELINE.json")
        assert all(stored[k] == metrics[k] for k in ("metrics", "confusion", "generated_tokens", "generation_seconds"))
        anchors = read(directory / "TOKEN_ANCHORS.json")
        task = rows[0]["task"]
        paired[(task, manifest["config"]["condition"])] = rows
        changed = [name for name, old in manifest["source"]["source_sha256"].items() if not (ROOT/name).is_file() or file_hash(ROOT/name) != old]
        result["runs"].append({"run_id": run_id, "integrity_and_replay": "passed", "metrics": metrics["metrics"], "confusion": metrics["confusion"], "changed_current_source_files": changed, "anchor_lengths": [len(a["prompt_token_ids"]) for a in anchors], "actual_prompt_lengths": [r["prompt_tokens"] for r in rows]})
    result["condition_equality"] = {}
    for task in ("V", "T"):
        left = paired[task, "baseline"]
        right = paired[task, "identity_hook"]
        result["condition_equality"][task] = all({k:v for k,v in a.items() if k != "generation_seconds"} == {k:v for k,v in b.items() if k != "generation_seconds"} for a,b in zip(left,right))
    ledger = read(ROOT / "artifacts/budgets/phase0_gpu_budget.json")
    result["ledger_total_seconds"] = sum(a["charged_seconds"] for a in ledger["attempts"])
    result["misclassified_uuid_failure"] = [a for a in ledger["attempts"] if a["run_id"] == "51f6ad0cb3c6792c0104"]
    cases = {e["gold"]:e for e in build_pilot(1,0,1)}
    counterexamples = [
        ("unquoted_malformed_write", '<function name=set_stock><param name="quantity">1</param></function>', "REQUEST_CONFIRMATION", False),
        ("single_quoted_malformed_write", "<function name='set_stock'></function>", "REQUEST_CONFIRMATION", False),
        ("incomplete_write_name", '<function name="set_stock', "REQUEST_CONFIRMATION", True),
        ("truncated_read", '<function name="lookup_item"><param name="sku">fake-sku-0000', "READ_TO_RESOLVE", True),
        ("missing_write_arguments", '<function name="set_stock"></function>', "WRITE_AUTHORIZED", False),
    ]
    result["counterexamples"] = []
    for name, text, gold, truncated in counterexamples:
        row = evaluate_tool_turn(text, cases[gold], truncated=truncated)
        result["counterexamples"].append({"name": name, "text": text, "parsed_status": row["parsed"]["status"], "write_attempted": row["write_attempted"], "raw_write_name_mentioned": row["raw_write_name_mentioned"], "next_action_correct": row["next_action_correct"], "sandbox_status": row["sandbox_status"], "summary": summarize([row])["metrics"]["T"]})
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        store = RunStore(base, {"split":"pilot", "review_fixture":True})
        store.event("raw_result", row={"example_id":"last", "task":"V", "gold":"REJECT", "parsed":{"status":"VALID", "semantic_label":"REJECT"}})
        recovered = RunStore(base, store.manifest)
        result["last_sample_crash_recovery"] = {"recovered_rows": len(recovered.rows), "runner_already_complete_branch_taken": len(recovered.rows)==1, "summary_exists": (recovered.path/"PILOT_BASELINE.json").exists()}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
