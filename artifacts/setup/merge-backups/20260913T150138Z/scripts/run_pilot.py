"""Run a resumable V pilot with a locked model; all formal tests stay closed."""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import tempfile
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from minicpm_research.evaluation import summarize
from minicpm_research.runs import PhaseBudget, RunStore, atomic_json, environment, file_hash, now, source_state
from minicpm_research.tool_parser import GOLD_TO_EXPECTED, evaluate_tool_turn
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
    if args.dry_run:
        print(json.dumps({"mode": "dry_run", "validation": validation, "tasks": list(tasks),
                          "selected_examples": len(selected),
                          "selected_families": {t: len(f) for t, f in family_ids_by_task.items()},
                          "model_inference": "未运行", "gpu_execution": "未运行",
                          "T_model_evaluation": "code_ready_not_run" if "T" in tasks else "not_selected",
                          "native_tool_parser": "implemented_unit_validated_real_model_output_pending_gpu",
                          "metrics": None}, ensure_ascii=False))
        return 0
    manifest = {"schema_version": 1, "config": config, "device": args.device,
                "selected_example_ids": [e["example_id"] for e in selected], "data_sha256": file_hash(args.data),
                "model_manifest_sha256": file_hash(args.model_lock), "source": source_state(ROOT), "environment": environment(),
                "T_model_evaluation": "code_ready_not_run", "native_tool_parser": "native_xml_v1_unit_validated", "intervention": {"condition": config["condition"], "weights_mutated": False}}
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
            print(json.dumps({"status": "already_complete", "run_id": store.run_id, "path": str(store.path)}))
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
                actual_uuid = str(properties.uuid)
                if actual_uuid != config["gpu_uuid"]:
                    raise ResourceError("CUDA runtime UUID differs from admitted UUID")
                torch.cuda.set_per_process_memory_fraction(admission["budget_bytes"] / properties.total_memory, 0)
            from minicpm_research.model import load_locked_model, render_prompt, token_anchors
            from minicpm_research.hooks import PostBlockHooks
            model, tokenizer = load_locked_model(args.model_lock, device=args.device, dtype=config["dtype"], attention_backend=config["attention_backend"])
            guard.model_loaded = True
            guard.sample()
            guard_handle = model.register_forward_pre_hook(lambda *unused: guard.check())
            atomic_json(store.path / "TOKEN_ANCHORS.json", [token_anchors(tokenizer, e["messages"]) for e in selected[:24]])
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
                encoded = tokenizer(prompt, add_special_tokens=False, return_tensors="pt")
                length = encoded["input_ids"].shape[-1]
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
                    text = tokenizer.decode(generated, skip_special_tokens=True)
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
