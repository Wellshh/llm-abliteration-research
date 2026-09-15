"""Run a resumable V pilot with a locked model; all formal tests stay closed."""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import tempfile
import time
from collections.abc import Mapping
from contextlib import nullcontext
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from minicpm_research.evaluation import summarize
from minicpm_research.runs import PhaseBudget, RunStore, atomic_json, digest, environment, file_hash, now, source_state
from minicpm_research.resources import canonical_gpu_uuid
from minicpm_research.tool_parser import GOLD_TO_EXPECTED, NATIVE_FORMAT_SHA256, evaluate_tool_turn
import minicpm_research.tool_parser as native_tool_parser
from minicpm_research.verifier import parse_verdict, validate_dataset


def validate_config(config: dict[str, Any]) -> None:
    if config.get("stage") != "T04" or config.get("split") != "pilot":
        raise ValueError("Only T04 pilot is enabled; formal splits are sealed")
    if config.get("condition") not in {"baseline", "identity_hook"}:
        raise ValueError("Only baseline/identity control is enabled before intervention selection")
    if config.get("dtype") != "bfloat16" or config.get("attention_backend") not in {"eager", "sdpa"}:
        raise ValueError("Primary precision must be bfloat16 with an explicit eager/sdpa backend")
    for key, maximum in {"budget_gib": 32, "max_prompt_tokens": 2048, "max_new_tokens": 128, "tool_max_new_tokens": 256, "chunk_size": 100, "cpu_threads": 4, "max_gpu_hours": 5}.items():
        value = config.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= maximum:
            raise ValueError(f"Invalid or over-budget setting: {key}")
    if config.get("reserve_gib") != 12:
        raise ValueError("The minimum full-card reserve is fixed at 12 GiB")


def encode_generation_prompt(tokenizer: Any, prompt: str) -> dict[str, Any]:
    """Encode only the two inputs accepted by the locked Llama causal model."""
    encoded = tokenizer(prompt, add_special_tokens=False, return_tensors="pt",
                        return_token_type_ids=False)
    if not isinstance(encoded, Mapping) or "input_ids" not in encoded:
        raise ValueError("tokenizer output must contain input_ids")
    unknown = set(encoded) - {"input_ids", "attention_mask"}
    if unknown:
        raise ValueError(f"tokenizer returned unsupported model inputs: {sorted(unknown)}")
    input_ids = encoded["input_ids"]
    if not hasattr(input_ids, "shape") or len(input_ids.shape) != 2 or input_ids.shape[0] != 1 or input_ids.shape[1] <= 0:
        raise ValueError("input_ids must have shape [1, sequence_length]")
    if "attention_mask" in encoded:
        mask = encoded["attention_mask"]
        if not hasattr(mask, "shape") or tuple(mask.shape) != tuple(input_ids.shape):
            raise ValueError("attention_mask shape must match input_ids")
    return encoded


def decode_generated_tokens(tokenizer: Any, token_ids: list[int], task: str, eos_ids: list[int]) -> str:
    """Preserve native tool markers for T while removing terminal EOS IDs by identity."""
    ids = list(token_ids)
    if task == "T":
        while ids and ids[-1] in eos_ids:
            ids.pop()
        return tokenizer.decode(ids, skip_special_tokens=False)
    return tokenizer.decode(ids, skip_special_tokens=True)


def build_token_anchor(tokenizer: Any, example: dict[str, Any]) -> dict[str, Any]:
    """Anchors from the SAME encoding path as generation, with consistency asserts.

    Review P2: T prompts must be rendered WITH their tool schemas; the saved anchor
    must equal the actual generation encoding (token IDs and length) or fail loudly.
    Anchors that do not match the real input cannot be used for position location.
    """
    from minicpm_research.model import render_prompt, token_anchors
    task = example["task"]
    tools = example.get("tools") if task == "T" else None
    prompt = render_prompt(tokenizer, example["messages"], tools=tools)
    encoded = encode_generation_prompt(tokenizer, prompt)
    ids = encoded["input_ids"][0].tolist()
    anchor = token_anchors(tokenizer, example["messages"], tools=tools)
    if anchor["prompt_token_ids"] != ids:
        raise ValueError(f"token anchor content mismatch for {example['example_id']}: anchors must equal the actual generation encoding")
    mask = encoded.get("attention_mask")
    anchor.update({"example_id": example["example_id"], "task": task, "family_id": example.get("family_id"),
                   "tools_present": tools is not None, "tools_sha256": digest(tools) if tools is not None else None,
                   "attention_mask": mask[0].tolist() if mask is not None else None,
                   "encoded_prompt_length": len(ids),
                   "assistant_boundary_index": len(ids) - 1})
    return anchor


def ensure_complete_run_summary(store: Any, device: str, attempt: str) -> bool:
    """Resume-path delivery (review P2): a fully-recovered run must end with its summary.

    Regenerates PILOT_BASELINE.json deterministically from committed rows when it is
    missing; NEVER overwrites an existing summary. device comes from the original run
    manifest, not from this resume invocation. No samples are regenerated, no model
    is loaded, and the completion event is appended for the audit trail.
    """
    summary_path = store.path / "PILOT_BASELINE.json"
    if summary_path.exists():
        return False
    report = summarize(list(store.rows.values()))
    report.update({"run_id": store.run_id, "gpu_execution": device == "cuda:0", "finished_at": now(),
                   "summary_regenerated_on_resume": True})
    atomic_json(summary_path, report)
    store.event("summary_regenerated_on_resume", attempt=attempt, examples=len(store.rows))
    return True


def _prompt_too_long_row(example: dict[str, Any], task: str, length: int) -> dict[str, Any]:
    """Retained protocol failure row; never silently truncate, never coerce to abstention."""
    if task == "T":
        return {"task": "T", "example_id": example["example_id"], "family_id": example["family_id"],
                "gold": example["gold"], "expected_action": GOLD_TO_EXPECTED[example["gold"]],
                "predicted_action": "INVALID", "next_action_correct": False,
                "raw_text": "", "truncated": False, "parsed": {"status": "PROMPT_TOO_LONG"},
                "write_attempted": False, "raw_write_name_mentioned": False,
                "sandbox_status": None, "sandbox_result": None, "sandbox_events": [],
                "prompt_tokens": length}
    return {"example_id": example["example_id"], "family_id": example["family_id"], "task": "V", "gold": example["gold"],
            "raw_text": "", "parsed": {"status": "PROMPT_TOO_LONG", "semantic_label": None}, "prompt_tokens": length}


def validate_hook_gate(path: Path, model_lock: Path, device: str, dtype: str, backend: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError("a passed real-checkpoint hook-validation report is required before model loading")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("role") == "characterization_not_validation" or report.get("exploratory_precision_control"):
        raise ValueError("exploratory characterization report is not a formal hook-validation credential and cannot unlock T04")
    if report.get("status") != "passed" or report.get("model_source") != "locked_official_checkpoint":
        raise ValueError("hook-validation report is not a passed locked-checkpoint report")
    if report.get("model_manifest_sha256") != file_hash(model_lock):
        raise ValueError("hook-validation report model manifest hash does not match this run")
    if report.get("device") != device or report.get("dtype") != dtype or report.get("attention_backend") != backend:
        raise ValueError("hook-validation report device/dtype/attention backend does not match this run")
    return {"path": str(path.resolve()), "report_sha256": file_hash(path), "model_manifest_sha256": report["model_manifest_sha256"],
            "device": device, "dtype": dtype, "attention_backend": backend}


SPLIT_GATE_STATUS = "passed_under_gate_split_v1"
SPLIT_GATE_STATUS_ENUM = {"passed_under_gate_split_v1", "failed_under_gate_split_v1", "blocked_under_gate_split_v1"}
SPLIT_GATE_TYPE = "evidence_aggregation_not_runtime_credential"
SPLIT_GATE_CONDITIONS = {
    "no_hook_identity_zero_self_patch",
    "kv_identity",
    "padding_position_decode_accounting",
    "prefill_and_decode_hook_coverage",
    "weight_hash_unchanged",
    "finite_values",
    "controlled_information_replacement_with_predeclared_target_toy_test",
}


def _repo_path(path: Path, label: str, repo_root: Path = ROOT) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} must resolve inside repository") from exc
    return resolved


def _load_split_yaml(path: Path) -> dict[str, Any]:
    """Load the amendment through PyYAML's safe loader; fail closed if absent."""
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise ValueError("PyYAML is required to validate the approved amendment") from exc
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("amendment YAML root must be a mapping")
    return data


def _validate_declared_evidence(value: Any, label: str) -> None:
    refs = value if isinstance(value, list) else [value]
    for ref in refs:
        if not isinstance(ref, str):
            raise ValueError(f"{label} evidence reference must be a string")
        for item in ref.split(";"):
            rel = item.strip().split(":", 1)[0]
            if not rel or rel.startswith("http"):
                raise ValueError(f"{label} evidence reference is not a repository path")
            _repo_path(ROOT / rel, f"{label} evidence")
            if not (ROOT / rel).resolve().is_file():
                raise ValueError(f"{label} evidence path does not exist: {rel}")


def validate_split_gate(amendment: Path, approval_sidecar: Path, aggregation: Path,
                        config: dict[str, Any], model_lock: Path | None = None,
                        repo_root: Path = ROOT) -> dict[str, Any]:
    amendment = _repo_path(amendment, "amendment", repo_root)
    approval_sidecar = _repo_path(approval_sidecar, "approval sidecar", repo_root)
    aggregation = _repo_path(aggregation, "aggregation", repo_root)
    model_lock = _repo_path(model_lock or (repo_root / "artifacts/model/MODEL_MANIFEST.json"), "model lock", repo_root)
    amendment_data = _load_split_yaml(amendment)
    sidecar = json.loads(approval_sidecar.read_text(encoding="utf-8"))
    aggregate = json.loads(aggregation.read_text(encoding="utf-8"))
    if amendment_data.get("status") != "approved_data_after_amendment" or amendment_data.get("effective") is not True:
        raise ValueError("split amendment is not approved and effective")
    if amendment_data.get("historical_status", {}).get("historical_T03_bf16_gate") != "failed":
        raise ValueError("split amendment does not preserve historical BF16 failure")
    split = amendment_data.get("split_gates", {})
    hook = split.get("T03_HOOK", {})
    numerics = split.get("T03_NUMERICS", {})
    if hook.get("status") not in SPLIT_GATE_STATUS_ENUM or hook.get("status") != SPLIT_GATE_STATUS or numerics.get("status") != "failed_limit_recorded":
        raise ValueError("split amendment gate states are invalid")
    if hook.get("status_enum") != list(SPLIT_GATE_STATUS_ENUM) and set(hook.get("status_enum", [])) != SPLIT_GATE_STATUS_ENUM:
        raise ValueError("split amendment status enum is invalid")
    _validate_declared_evidence(amendment_data.get("basis_observed_data_after", {}).get("evidence", []), "amendment")
    declared_conditions = hook.get("required_conditions")
    if not isinstance(declared_conditions, list) or len(declared_conditions) != len(set(declared_conditions)):
        raise ValueError("split amendment required_conditions must be unique")
    aggregate_conditions = aggregate.get("conditions")
    if not isinstance(aggregate_conditions, list):
        raise ValueError("split aggregation conditions must be a list")
    if any(not isinstance(item, dict) for item in aggregate_conditions):
        raise ValueError("split aggregation conditions must contain mappings")
    names = [item.get("condition") for item in aggregate_conditions]
    if any(not isinstance(name, str) for name in names):
        raise ValueError("split aggregation condition names must be strings")
    if len(names) != len(set(names)) or set(names) != set(declared_conditions) or set(names) != SPLIT_GATE_CONDITIONS:
        raise ValueError("split gate condition sets do not match exactly")
    for item in aggregate_conditions:
        if item.get("status") != "passed_under_split_gate":
            raise ValueError("split aggregation condition status is invalid")
        _validate_declared_evidence(item.get("evidence"), f"condition {item.get('condition')}")
    if aggregate.get("type") != SPLIT_GATE_TYPE or aggregate.get("status") != SPLIT_GATE_STATUS or aggregate.get("effective") is not True:
        raise ValueError("split aggregation is not an effective passed split gate")
    if aggregate.get("historical_T03_bf16_gate") != "failed" or aggregate.get("T03_NUMERICS") != "failed_limit_recorded":
        raise ValueError("split aggregation does not preserve historical numeric state")
    if aggregate.get("does_not_unlock_T04_automatically") is not True:
        raise ValueError("split aggregation must not unlock T04 automatically")
    if aggregate.get("scope", {}).get("fp32_characterization_is_validation_credential") is not False:
        raise ValueError("FP32 characterization cannot be a split credential")
    scope = aggregate.get("scope", {})
    if scope.get("T04_requires_separate_explicit_approval") is not True or scope.get("gpu_execution_this_turn") is not False or scope.get("T04_execution_this_turn") is not False:
        raise ValueError("split aggregation execution scope is invalid")
    if aggregate.get("scope", {}).get("new_full_cache_threshold", "missing") is not None:
        raise ValueError("split aggregation must not define a new full/cache threshold")
    if aggregate.get("does_not_rewrite_complete_T03_as_passed") is not True:
        raise ValueError("split aggregation must preserve complete T03 historical status")
    historical = amendment_data.get("historical_status", {})
    if historical.get("original_numeric_control_is_immutable") is not True or historical.get("threshold_retroactive_change") is not False or historical.get("fp32_is_formal_credential") is not False:
        raise ValueError("amendment historical protections are invalid")
    if numerics.get("new_full_cache_pass_threshold", "missing") is not None or numerics.get("bf16_primary_failure_preserved") is not True or numerics.get("fp32_role") != "characterization_only":
        raise ValueError("amendment numerical gate protections are invalid")
    conditional = amendment_data.get("conditional_T04", {})
    if conditional.get("unlocked_automatically") is not False or conditional.get("requires_separate_explicit_approval") is not True or conditional.get("allowed_conditions") != ["baseline", "identity_hook"] or conditional.get("intervention_selection") != "forbidden" or conditional.get("split") != "pilot_only" or conditional.get("results_may_change_threshold") is not False:
        raise ValueError("conditional T04 restrictions are invalid")
    declared_sidecar = sidecar.get("amendment_path")
    if declared_sidecar != "reports/T03_GATE_SPLIT_AMENDMENT_v1.yaml":
        raise ValueError("approval sidecar amendment path mismatch")
    if amendment != _repo_path(repo_root / declared_sidecar, "declared amendment", repo_root):
        raise ValueError("amendment path mismatch")
    if amendment_data.get("approval_sidecar") != "reports/T03_GATE_SPLIT_AMENDMENT_v1_APPROVAL.json":
        raise ValueError("amendment approval_sidecar declaration mismatch")
    if approval_sidecar != _repo_path(repo_root / amendment_data["approval_sidecar"], "declared approval sidecar", repo_root):
        raise ValueError("approval sidecar path mismatch")
    if str(sidecar.get("amendment_sha256", "")).lower() != file_hash(amendment).lower():
        raise ValueError("approval sidecar amendment SHA256 mismatch")
    if hook.get("candidate_evidence") != "reports/T03_HOOK_GATE_v1.json":
        raise ValueError("amendment candidate_evidence declaration mismatch")
    if sidecar.get("evidence_candidate") != "reports/T03_HOOK_GATE_v1.json":
        raise ValueError("approval sidecar evidence declaration mismatch")
    if sidecar.get("approval_record", {}).get("root_review") != "approved":
        raise ValueError("approval sidecar is not root-approved")
    if sidecar.get("freeze", {}).get("effective") is not True:
        raise ValueError("approval sidecar is not frozen/effective")
    sh = sidecar.get("historical_status", {})
    if sh.get("historical_T03_bf16_gate") != "failed" or sh.get("T03_NUMERICS") != "failed_limit_recorded" or sh.get("does_not_unlock_T04_automatically") is not True:
        raise ValueError("approval sidecar historical status is invalid")
    declared_aggregation = sidecar.get("aggregation_path")
    if declared_aggregation != "reports/T03_HOOK_GATE_v1.json" or aggregation != _repo_path(repo_root / declared_aggregation, "declared aggregation", repo_root):
        raise ValueError("approval sidecar aggregation path mismatch")
    if str(sidecar.get("aggregation_sha256", "")).lower() != file_hash(aggregation).lower():
        raise ValueError("approval sidecar aggregation SHA256 mismatch")
    if aggregate.get("amendment") != amendment_data.get("approval_sidecar", "").replace("_APPROVAL.json", ".yaml"):
        raise ValueError("aggregation amendment declaration mismatch")
    if aggregate.get("approval_sidecar") != "reports/T03_GATE_SPLIT_AMENDMENT_v1_APPROVAL.json":
        raise ValueError("aggregation approval sidecar declaration mismatch")
    lock_manifest = json.loads(model_lock.read_text(encoding="utf-8"))
    model_binding = aggregate.get("model_lock", {})
    if model_binding.get("path") != "artifacts/model/MODEL_MANIFEST.json" or str(model_binding.get("sha256", "")).lower() != file_hash(model_lock).lower():
        raise ValueError("split aggregation model lock mismatch")
    if model_lock != _repo_path(repo_root / model_binding["path"], "declared model lock", repo_root):
        raise ValueError("model lock path mismatch")
    if model_binding.get("revision_sha") != lock_manifest.get("revision_sha") or model_binding.get("chat_template_sha256") != lock_manifest.get("chat_template_sha256"):
        raise ValueError("split aggregation model revision/template mismatch")
    if config.get("split") != "pilot" or config.get("condition") not in {"baseline", "identity_hook"}:
        raise ValueError("split gate permits pilot baseline or identity_hook only")
    if config.get("dtype") != "bfloat16" or config.get("attention_backend") != "eager":
        raise ValueError("split gate requires BF16 eager")
    return {"mode": "split_v1", "aggregation_path": str(aggregation),
            "aggregation_sha256": file_hash(aggregation), "amendment_path": str(amendment),
            "amendment_sha256": file_hash(amendment), "approval_sidecar_path": str(approval_sidecar),
            "approval_sidecar_sha256": file_hash(approval_sidecar), "status": SPLIT_GATE_STATUS,
            "historical_T03_bf16_gate": "failed", "T03_NUMERICS": "failed_limit_recorded"}


def validate_t04_execution_approval(path: Path, config: dict[str, Any], hook_gate: dict[str, Any],
                                    actual_config_path: Path, actual_data_path: Path,
                                    task: str, max_families: int, device: str, actual_output_dir: Path,
                                    repo_root: Path = ROOT) -> dict[str, Any]:
    approval = _repo_path(path, "T04 execution approval", repo_root)
    if not approval.is_file():
        raise ValueError("T04 execution approval is required before non-dry-run split execution")
    data = json.loads(approval.read_text(encoding="utf-8"))
    if data.get("status") != "approved" or data.get("effective") is not True:
        raise ValueError("T04 execution approval is pending or ineffective")
    bindings = data.get("bindings", {})
    required = {
        "amendment_sha256": hook_gate.get("amendment_sha256"),
        "aggregation_sha256": hook_gate.get("aggregation_sha256"),
        "approval_sidecar_sha256": hook_gate.get("approval_sidecar_sha256"),
    }
    for key, expected in required.items():
        if str(bindings.get(key, "")).lower() != str(expected).lower():
            raise ValueError(f"T04 approval {key} mismatch")
    if bindings.get("amendment_path") != "reports/T03_GATE_SPLIT_AMENDMENT_v1.yaml" or bindings.get("aggregation_path") != "reports/T03_HOOK_GATE_v1.json" or bindings.get("approval_sidecar_path") != "reports/T03_GATE_SPLIT_AMENDMENT_v1_APPROVAL.json":
        raise ValueError("T04 approval gate paths mismatch")
    config_path = bindings.get("config_path")
    if not isinstance(config_path, str):
        raise ValueError("T04 approval config path invalid")
    config_file = _repo_path(repo_root / config_path, "T04 approval config", repo_root)
    if config_file != _repo_path(actual_config_path, "actual config", repo_root):
        raise ValueError("T04 approval config path does not match CLI config")
    if not config_file.is_file() or str(bindings.get("config_sha256", "")).lower() != file_hash(config_file).lower():
        raise ValueError("T04 approval config binding mismatch")
    if bindings.get("condition") != config.get("condition") or bindings.get("condition") not in {"baseline", "identity_hook"}:
        raise ValueError("T04 approval condition mismatch")
    if bindings.get("task") != task or bindings.get("task") not in {"V", "T", "both"} or bindings.get("max_families") != max_families or max_families != 1:
        raise ValueError("T04 approval task/max_families restriction mismatch")
    data_path = bindings.get("data_path")
    if not isinstance(data_path, str) or _repo_path(repo_root / data_path, "T04 approval data", repo_root) != _repo_path(actual_data_path, "actual data", repo_root):
        raise ValueError("T04 approval data path does not match CLI data")
    data_file = _repo_path(actual_data_path, "actual data", repo_root)
    if str(bindings.get("data_sha256", "")).lower() != file_hash(data_file).lower():
        raise ValueError("T04 approval data binding mismatch")
    if bindings.get("device") != device or bindings.get("device") != "cuda:0" or bindings.get("gpu_uuid") != config.get("gpu_uuid"):
        raise ValueError("T04 approval device/GPU binding mismatch")
    output_dir = bindings.get("output_dir")
    if not isinstance(output_dir, str) or Path(output_dir).is_absolute():
        raise ValueError("T04 approval output directory must be repository-relative")
    if _repo_path(repo_root / output_dir, "T04 approval output", repo_root) != _repo_path(actual_output_dir, "actual output", repo_root):
        raise ValueError("T04 approval output directory does not match CLI output")
    if not isinstance(bindings.get("approval_id"), str) or bindings.get("execution_scope") != "single_content_addressed_run_allow_resume":
        raise ValueError("T04 approval execution scope is invalid")
    record = data.get("approval_record", {})
    if not record.get("approved_at") or record.get("approval_semantics") != "user_approved_t04_execution_after_final_ticket":
        raise ValueError("T04 approval record is missing explicit user approval")
    return {"path": str(approval), "sha256": file_hash(approval), "status": "approved",
            "approved_at": record["approved_at"], "condition": bindings["condition"],
            "task": bindings["task"], "max_families": bindings["max_families"],
            "approval_id": bindings["approval_id"], "execution_scope": bindings["execution_scope"]}

def validate_parser_template(model_lock: Path) -> None:
    lock = json.loads(model_lock.read_text(encoding="utf-8"))
    if lock.get("chat_template_sha256") != NATIVE_FORMAT_SHA256:
        raise ValueError("native parser template hash does not match locked model template")

def parser_code_sha256() -> str:
    return file_hash(Path(native_tool_parser.__file__).resolve())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/pilot.json")
    parser.add_argument("--data", type=Path, default=ROOT / "artifacts/data/pilot.jsonl")
    parser.add_argument("--model-lock", type=Path, default=ROOT / "artifacts/model/MODEL_MANIFEST.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/runs")
    parser.add_argument("--device", choices=("cpu", "cuda:0"), default="cuda:0")
    parser.add_argument("--max-families", type=int, default=12, help="whole families per task, in deterministic file order")
    parser.add_argument("--task", choices=("V", "T", "both"), default="both", help="which pilot task families to run")
    parser.add_argument("--dry-run", action="store_true", help="validate inputs without a model or any model metrics")
    gate_group = parser.add_mutually_exclusive_group()
    gate_group.add_argument("--hook-validation", type=Path, help="passed real-checkpoint hook report required for model runs")
    gate_group.add_argument("--hook-gate-split", action="store_true", help="use the approved T03 split-gate aggregation")
    parser.add_argument("--amendment", type=Path, default=ROOT / "reports/T03_GATE_SPLIT_AMENDMENT_v1.yaml")
    parser.add_argument("--approval-sidecar", type=Path, default=ROOT / "reports/T03_GATE_SPLIT_AMENDMENT_v1_APPROVAL.json")
    parser.add_argument("--hook-gate-aggregation", type=Path, default=ROOT / "reports/T03_HOOK_GATE_v1.json")
    parser.add_argument("--t04-execution-approval", type=Path, help="explicit user approval required for non-dry-run split execution")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    validate_config(config)
    if args.max_families <= 0:
        raise ValueError("max-families must be positive")
    examples = [json.loads(line) for line in args.data.read_text(encoding="utf-8").splitlines() if line.strip()]
    validation = validate_dataset(examples)
    if any(example.get("split") != "pilot" for example in examples):
        raise ValueError("Refusing non-pilot input")
    tasks = ("V", "T") if args.task == "both" else (args.task,)
    selected: list[dict[str, Any]] = []
    family_ids_by_task: dict[str, list[str]] = {}
    for task in tasks:
        fids = list(dict.fromkeys(e["family_id"] for e in examples if e["task"] == task))[:args.max_families]
        family_ids_by_task[task] = fids
        selected.extend(e for e in examples if e["task"] == task and e["family_id"] in fids)
    if not selected:
        raise ValueError("No pilot examples selected")
    if args.hook_gate_split:
        hook_gate = validate_split_gate(args.amendment, args.approval_sidecar, args.hook_gate_aggregation, config, args.model_lock)
    elif args.hook_validation is not None:
        hook_gate = validate_hook_gate(args.hook_validation, args.model_lock, args.device, config["dtype"], config["attention_backend"])
    else:
        hook_gate = None
    execution_approval: dict[str, Any] | str | None = None
    if args.hook_gate_split and not args.dry_run:
        if args.t04_execution_approval is None:
            raise ValueError("--t04-execution-approval is required for non-dry-run split execution")
        execution_approval = validate_t04_execution_approval(args.t04_execution_approval, config, hook_gate,
                                                             args.config, args.data, args.task, args.max_families,
                                                             args.device, args.output_dir)
    elif args.hook_gate_split:
        execution_approval = "required_before_run"
    if args.dry_run:
        print(json.dumps({"mode": "dry_run", "validation": validation, "tasks": list(tasks),
                          "selected_examples": len(selected),
                          "selected_families": {t: len(f) for t, f in family_ids_by_task.items()},
                          "model_inference": "未运行", "gpu_execution": "未运行",
                          "T_model_evaluation": "code_ready_not_run" if "T" in tasks else "not_selected",
                          "native_tool_parser": "implemented_unit_validated_real_model_output_pending_gpu",
                          "gate_validation": hook_gate,
                          "execution_approval": execution_approval,
                          "metrics": None}, ensure_ascii=False))
        return 0
    if hook_gate is None:
        hook_gate = validate_hook_gate(ROOT / "artifacts/hooks/HOOK_VALIDATION.json", args.model_lock, args.device, config["dtype"], config["attention_backend"])
    if "T" in tasks:
        validate_parser_template(args.model_lock)
    manifest = {"schema_version": 1, "config": config, "device": args.device,
                "selected_example_ids": [e["example_id"] for e in selected], "data_sha256": file_hash(args.data),
                "model_manifest_sha256": file_hash(args.model_lock), "source": source_state(ROOT), "environment": environment(),
                "T_model_evaluation": "code_ready_not_run", "native_tool_parser": "native_xml_v1_unit_validated", "native_tool_template_sha256": NATIVE_FORMAT_SHA256,
                "hook_validation": hook_gate, "execution_approval": execution_approval,
                "native_tool_parser_code_sha256": parser_code_sha256(), "intervention": {"condition": config["condition"], "weights_mutated": False}}
    from minicpm_research.resources import (GIB, ResourceError, RuntimeResourceGuard, audit_resources, capture_snapshot, require_admission, research_lock_path, single_worker_lock)
    lock_path = research_lock_path()
    # CPU runs use the same Linux lock so the same manifest never has two writers.
    if sys.platform != "linux":
        raise ValueError("Model runs are supported on the Linux research server; local dry-run is portable")
    with single_worker_lock(lock_path):
        store = RunStore(args.output_dir, manifest)
        if not set(store.rows).issubset({e["example_id"] for e in selected}):
            raise ValueError("Completed shards contain unexpected sample IDs")
        if len(store.rows) == len(selected):
            # Review P2: a crash after the last raw_result/shard but before the summary
            # must still deliver PILOT_BASELINE.json on resume (regenerate if missing,
            # never overwrite), and the completion path must leave an audit event.
            resume_attempt = f"resume-{time.time_ns()}-{os.getpid()}"
            regenerated = ensure_complete_run_summary(store, store.manifest.get("device", args.device), resume_attempt)
            store.event("already_complete_verified", attempt=resume_attempt, examples=len(store.rows),
                        summary_regenerated=regenerated)
            print(json.dumps({"status": "already_complete", "run_id": store.run_id, "path": str(store.path),
                              "summary_regenerated": regenerated,
                              "summary_present": (store.path / "PILOT_BASELINE.json").exists()}))
            return 0
        stop = {"requested": False}
        def request_stop(signum: int, frame: Any) -> None:
            stop["requested"] = True
        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)
        started = time.monotonic()
        attempt = f"{time.time_ns()}-{os.getpid()}"
        store.event("attempt_started", attempt=attempt, pid=os.getpid(), gpu_execution=args.device == "cuda:0")
        admission = None
        budget = None
        guard = None
        guard_handle = None
        try:
            if args.device == "cuda:0":
                audit = audit_resources(store.path / f"audit-{attempt}", seconds=60)
                admission = require_admission(audit, config["gpu_uuid"], config["budget_gib"], ROOT / "artifacts/reservation")
                os.environ.update(admission["cuda_environment"])
                atomic_json(store.path / f"admission-{attempt}.json", admission)
                budget = PhaseBudget(ROOT / "artifacts/budgets/phase0_gpu_budget.json", config["max_gpu_hours"] * 3600)
                budget.start(attempt, store.run_id)
            else:
                atomic_json(store.path / f"cpu-audit-{attempt}.json", capture_snapshot(ROOT))
            guard = RuntimeResourceGuard(ROOT, admission=admission, event_sink=store.event, budget=budget)
            guard.__enter__()
            os.environ["OMP_NUM_THREADS"] = str(config["cpu_threads"])
            os.environ["TOKENIZERS_PARALLELISM"] = "false"
            import torch
            torch.set_num_threads(config["cpu_threads"])
            torch.manual_seed(config["seed"])
            if admission:
                if torch.cuda.device_count() != 1:
                    raise ResourceError("Expected exactly one visible GPU")
                properties = torch.cuda.get_device_properties(0)
                actual_uuid = canonical_gpu_uuid(str(properties.uuid))
                if actual_uuid != canonical_gpu_uuid(config["gpu_uuid"]):
                    raise ResourceError("CUDA runtime UUID differs from admitted UUID")
                torch.cuda.set_per_process_memory_fraction(admission["budget_bytes"] / properties.total_memory, 0)
            from minicpm_research.model import load_locked_model, render_prompt
            from minicpm_research.hooks import PostBlockHooks
            model, tokenizer = load_locked_model(args.model_lock, device=args.device, dtype=config["dtype"], attention_backend=config["attention_backend"])
            guard.model_loaded = True
            guard.sample()
            guard_handle = model.register_forward_pre_hook(lambda *unused: guard.check())
            # Review P2: anchors are built from the SAME encoding path as generation
            # (T prompts rendered WITH tools) and asserted equal to it, so saved
            # anchor positions describe the real generation input.
            anchors = [build_token_anchor(tokenizer, e) for e in selected[:24]]
            atomic_json(store.path / "TOKEN_ANCHORS.json", anchors)
            anchor_lengths = {a["example_id"]: a["encoded_prompt_length"] for a in anchors}
            pending: list[dict[str, Any]] = []
            def pressure_check() -> None:
                guard.check()
                snapshot = capture_snapshot(ROOT)
                store.event("resource_sample", snapshot=snapshot)
                if snapshot.get("host", {}).get("disk_free_bytes", 0) < 15 * GIB:
                    raise ResourceError("Disk below 15 GiB; stopping at saved sample boundary")
                if admission:
                    if snapshot.get("errors"):
                        raise ResourceError("Resource sampler failed")
                    card = next(g for g in snapshot["gpus"] if g["uuid"] == config["gpu_uuid"])
                    if card["memory_free_bytes"] < 12 * GIB:
                        raise ResourceError("Full-card free memory below 12 GiB")
                    own = [p for p in snapshot["processes"] if p["pid"] == os.getpid() and p["gpu_uuid"] == config["gpu_uuid"]]
                    if any(p.get("used_memory_bytes", p.get("used_gpu_memory_bytes", 0)) > admission["budget_bytes"] for p in own):
                        raise ResourceError("Own GPU memory exceeds process budget")
            pressure_check()
            last_check = time.monotonic()
            for example in selected:
                if example["example_id"] in store.rows:
                    continue
                if stop["requested"] or time.monotonic() - started >= config["max_gpu_hours"] * 3600:
                    store.commit(pending)
                    store.event("stopped_at_boundary", reason="signal_or_time_budget")
                    return 3
                task = example["task"]
                tools = example.get("tools") if task == "T" else None
                prompt = render_prompt(tokenizer, example["messages"], tools=tools)
                encoded = encode_generation_prompt(tokenizer, prompt)
                length = encoded["input_ids"].shape[-1]
                if example["example_id"] in anchor_lengths and anchor_lengths[example["example_id"]] != length:
                    raise ValueError(f"generation prompt length {length} diverged from saved token anchor "
                                     f"{anchor_lengths[example['example_id']]} for {example['example_id']}")
                max_new = config["tool_max_new_tokens"] if task == "T" else config["max_new_tokens"]
                if length > config["max_prompt_tokens"]:
                    # No silent prompt truncation; this is a retained protocol failure.
                    row = _prompt_too_long_row(example, task, length)
                else:
                    encoded = {key: tensor.to(args.device) for key, tensor in encoded.items()}
                    timer = time.monotonic()
                    context = PostBlockHooks(model) if config["condition"] == "identity_hook" else nullcontext()
                    with torch.inference_mode(), context:
                        output = model.generate(**encoded, do_sample=False, max_new_tokens=max_new, use_cache=True,
                                                pad_token_id=tokenizer.pad_token_id)
                    generated = output[0, length:].tolist()
                    seconds = time.monotonic() - timer
                    eos = model.generation_config.eos_token_id
                    eos_ids = eos if isinstance(eos, list) else [eos]
                    truncated = len(generated) >= max_new and (not generated or generated[-1] not in eos_ids)
                    text = decode_generated_tokens(tokenizer, generated, task, eos_ids)
                    if task == "T":
                        row = evaluate_tool_turn(text, example, truncated=truncated)
                        row.update({"raw_token_ids": generated, "prompt_tokens": length,
                                    "generated_tokens": len(generated), "generation_seconds": seconds})
                    else:
                        row = {"example_id": example["example_id"], "family_id": example["family_id"], "task": "V", "gold": example["gold"],
                               "raw_text": text, "raw_token_ids": generated, "parsed": parse_verdict(text, example["label_map"], truncated=truncated),
                               "prompt_tokens": length, "generated_tokens": len(generated), "generation_seconds": seconds}
                store.event("raw_result", attempt=attempt, row=row)
                pending.append(row)
                if len(pending) >= config["chunk_size"] or time.monotonic() - last_check >= 30:
                    store.commit(pending)
                    pending = []
                    pressure_check()
                    last_check = time.monotonic()
            store.commit(pending)
            report = summarize(list(store.rows.values()))
            report.update({"run_id": store.run_id, "gpu_execution": args.device == "cuda:0", "finished_at": now()})
            atomic_json(store.path / "PILOT_BASELINE.json", report)
            store.event("attempt_completed", attempt=attempt, examples=len(store.rows), elapsed_seconds=time.monotonic() - started)
            print(json.dumps({"status": "complete", "run_id": store.run_id, "path": str(store.path), "examples": len(store.rows)}))
            return 0
        except BaseException as exc:
            store.event("attempt_failed", attempt=attempt, error_type=type(exc).__name__, error=str(exc), elapsed_seconds=time.monotonic() - started)
            atomic_json(store.path / f"failure-{attempt}.json", {"status": "failed", "error_type": type(exc).__name__, "error": str(exc), "completed_examples": len(store.rows)})
            raise
        finally:
            if guard_handle is not None:
                guard_handle.remove()
            if guard is not None:
                guard.__exit__(*sys.exc_info())
            if budget is not None:
                budget.checkpoint(finish=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"pilot failed: {error}", file=sys.stderr)
        raise SystemExit(1)
