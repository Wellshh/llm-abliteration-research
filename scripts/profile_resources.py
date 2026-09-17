"""B8-02: RESOURCE_PROFILE — prefill/decode-separated forward/s + allocator peak,
and measurement-based §14 budget re-estimation.

Three modes (plan §14 / §6.3 RESOURCE_PROFILE; audits RES-01/RES-05/RES-06):

  --device cpu          HARNESS VALIDATION ONLY, on a tiny random Llama (NOT
                        MiniCPM5). Proves the measurement structure + budget math
                        end-to-end without a GPU. Output is labelled
                        cpu_harness_validation_NOT_a_real_profile and may NOT be
                        named RESOURCE_PROFILE.json (it must never masquerade as a
                        real profile).

  --device cuda:0       the REAL measurement on the locked official MiniCPM5-2B.
                        GATED: requires --model-lock AND --execution-ticket <id>
                        AND live same-process admission (single-worker lock, >=60s
                        read-only audit, UUID bind, 32 GiB budget + 12 GiB reserve,
                        PhaseBudget, RuntimeResourceGuard) exactly like check_hooks.
                        Records torch.cuda allocator peak (RES-05) and times prefill
                        and decode in SEPARATE loops (RES-06). NOT authorized this
                        turn; do not run without an approved ticket.

  --budget-only         PURE CPU. Consumes an already-measured profile JSON + a plan
                        JSON and emits the §14 per-phase GPU-second re-estimate. A
                        real re-estimate requires a real_gpu_measurement profile —
                        and a profile's own labels are NOT sufficient: a real claim
                        is accepted only if the structural markers only the gated
                        cuda:0 path writes are present (live `admission`,
                        `budget_settlement`) and `model_manifest_sha256` re-verifies
                        against `--model-lock`. A cpu/illustrative profile is accepted
                        only with --illustrative and is then labelled
                        illustrative_not_a_real_reestimate.

All outputs are content-addressed, written atomically, and refuse to overwrite.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from minicpm_research.resource_profile import (  # noqa: E402
    DEFAULT_PRE_ADMISSION_AUDIT_S,
    PhasePlan,
    measure_prefill_decode,
    rates_from_profile,
    reestimate_phase_budgets,
)
from minicpm_research.runs import file_hash, source_state  # noqa: E402


def _atomic(path: Path, payload: dict[str, Any]) -> None:
    """Refuse to overwrite (preserve prior evidence); write atomically + fsync."""
    if path.exists():
        raise SystemExit(f"REFUSING to overwrite existing {path}; choose a new path to preserve earlier evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("x", encoding="utf-8") as h:
        json.dump(payload, h, ensure_ascii=False, indent=2)
        h.write("\n")
        h.flush()
        os.fsync(h.fileno())
    os.replace(tmp, path)


def _tiny_llama(device: str, dtype: str) -> Any:
    """Random tiny Llama — an IMPLEMENTATION control for the harness, NOT MiniCPM5."""
    import torch
    from transformers import LlamaConfig, LlamaForCausalLM
    config = LlamaConfig(vocab_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                         num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=512,
                         pad_token_id=0, bos_token_id=1, eos_token_id=2, attention_dropout=0.0)
    config._attn_implementation = "eager"
    torch.manual_seed(17)
    return LlamaForCausalLM(config).to(device=device, dtype=getattr(torch, dtype))


def _measure(args: argparse.Namespace) -> dict[str, Any]:
    """Run measure_prefill_decode on either the tiny CPU control or the locked model."""
    from minicpm_research.model import environment_versions
    prefill_lengths = [int(x) for x in str(args.prefill_lengths).split(",") if x.strip()]
    common = dict(device=args.device, prefill_lengths=prefill_lengths, decode_steps=args.decode_steps,
                  prefill_repeats=args.prefill_repeats, decode_repeats=args.decode_repeats, warmup=args.warmup)
    if args.device == "cuda:0":
        if not args.model_lock:
            raise SystemExit("cuda:0 real measurement requires --model-lock (the locked official checkpoint)")
        if not args.execution_ticket:
            raise SystemExit("cuda:0 real measurement is GATED: pass --execution-ticket <B8-02 id> (intent flag; resource gate=require_admission, approval gate=§F)")
        from minicpm_research.model import load_locked_model
        t_load0 = time.perf_counter()
        model, _ = load_locked_model(args.model_lock, device=args.device, dtype=args.dtype)
        load_s = time.perf_counter() - t_load0
        source = "locked_official_checkpoint"
    else:
        model = _tiny_llama(args.device, args.dtype)
        load_s = None
        source = "random_tiny_llama_harness_control_not_MiniCPM5"
    profile = measure_prefill_decode(model, model_load_seconds=load_s, **common)
    profile.update({"model_source": source, "ticket": "B8-02", "command": sys.argv,
                    "environment": environment_versions(),
                    "generated_at": datetime.now(timezone.utc).isoformat()})
    if args.model_lock:
        profile["model_manifest_sha256"] = file_hash(args.model_lock)
    return profile


def _budget_only(args: argparse.Namespace) -> dict[str, Any]:
    """Pure-CPU §14 budget re-estimate from a measured profile + a plan."""
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    plan_doc = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    real_claim = bool(profile.get("is_real_profile")) and profile.get("measurement_kind") == "real_gpu_measurement"
    real_claim_basis: dict[str, Any] | None = None
    if real_claim:
        # §12 round-2 audit (2026-09-17): a profile's SELF-DECLARED labels are not provenance —
        # hand-writing {"is_real_profile": true, "measurement_kind": "real_gpu_measurement"} into a
        # JSON file used to mint a real_gpu_measurement_based §14 re-estimate (the same
        # self-declared-label failure that D3 closed on the Level-B side). A real claim is now
        # accepted only on STRUCTURAL evidence that only the gated cuda:0 path produces:
        # live admission + budget settlement + a model binding re-verified against the lock file.
        missing = [k for k in ("admission", "budget_settlement")
                   if not isinstance(profile.get(k), dict) or not profile.get(k)]
        if missing:
            raise SystemExit(
                f"profile claims real_gpu_measurement but lacks the structural markers only the gated "
                f"cuda:0 path writes: {missing}. Refusing to emit a §14 re-estimate labelled real from a "
                "profile whose 'real' status is self-declared. Run the measurement under an approved §F "
                "ticket, or pass --illustrative to demonstrate the math (output is then labelled "
                "illustrative_not_a_real_reestimate).")
        if not args.model_lock:
            raise SystemExit("profile claims real_gpu_measurement: pass --model-lock so the recorded "
                             "model_manifest_sha256 can be re-verified against the lock file")
        bound = profile.get("model_manifest_sha256")
        actual = file_hash(args.model_lock)
        if not bound or bound != actual:
            raise SystemExit(f"profile claims real_gpu_measurement but its model_manifest_sha256 "
                             f"({str(bound)[:16]}…) does not match --model-lock on disk ({actual[:16]}…)")
        real_claim_basis = {
            "admission_present": True, "budget_settlement_present": True,
            "admission_gpu_uuid": (profile.get("admission") or {}).get("gpu_uuid"),
            "model_manifest_sha256_verified": actual,
            "note": "structural markers required in addition to the profile's own labels; labels alone are not provenance",
        }
    if not real_claim and not args.illustrative:
        raise SystemExit(
            "profile is not a real_gpu_measurement; a §14 re-estimate from it would be invalid. "
            "Re-run with --device cuda:0 under an approved ticket, or pass --illustrative to "
            "demonstrate the math (output will be labelled illustrative_not_a_real_reestimate).")
    planned_prefill_len = int(args.planned_prefill_len or max(int(p["prefill_length"]) for p in profile.get("prefill", [{"prefill_length": 1}])))
    rates = rates_from_profile(profile, planned_prefill_len)
    if rates["decode_forward_per_s"] is None:
        raise SystemExit("profile has no usable decode_forward_per_s")
    plans = [PhasePlan(phase=p["phase"], n_runs=int(p["n_runs"]),
                       prefill_tokens_per_run=int(p["prefill_tokens_per_run"]),
                       decode_tokens_per_run=int(p["decode_tokens_per_run"]),
                       attempts_per_run=float(p.get("attempts_per_run", 1.0)))
             for p in plan_doc["phases"]]
    result = reestimate_phase_budgets(
        plans,
        prefill_tokens_per_s=rates["prefill_tokens_per_s"],
        decode_forward_per_s=rates["decode_forward_per_s"],
        fixed_overhead_per_run_s=float(plan_doc.get("fixed_overhead_per_run_s", 12.5)),
        pre_admission_audit_s=float(plan_doc.get("pre_admission_audit_s", DEFAULT_PRE_ADMISSION_AUDIT_S)),
        rate_provenance=("real_gpu_measurement" if real_claim else "illustrative"),
    )
    result.update({
        "ticket": "B8-02", "mode": "budget_only",
        "real_claim_basis": real_claim_basis,
        "profile_source": str(args.profile), "profile_sha256": file_hash(Path(args.profile)),
        "plan_source": str(args.plan), "plan_sha256": file_hash(Path(args.plan)),
        "rates_derived": rates, "planned_prefill_len": planned_prefill_len,
        "source": source_state(REPO), "generated_at": datetime.now(timezone.utc).isoformat(),
    })
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--device", choices=["cpu", "cuda:0"], default="cpu")
    p.add_argument("--dtype", choices=["float32", "bfloat16"], default="float32")
    p.add_argument("--model-lock", type=Path)
    p.add_argument("--output", type=Path, default=Path("artifacts/setup/RESOURCE_PROFILE.json"))
    p.add_argument("--gpu-uuid", default="GPU-e5c246b7-afc2-cccd-e66d-fa1ca4eb089e")
    p.add_argument("--budget-gib", type=float, default=32)
    p.add_argument("--execution-ticket", help="REQUIRED for --device cuda:0: a B8-02 execution-ticket id. INTENT FLAG ONLY — not validated against an approval here; the real resource gate is require_admission and run authorization is enforced by the §F approval process (audit D2)")
    p.add_argument("--prefill-lengths", default="128,512,2048")
    p.add_argument("--decode-steps", type=int, default=32)
    p.add_argument("--prefill-repeats", type=int, default=5)
    p.add_argument("--decode-repeats", type=int, default=3)
    p.add_argument("--warmup", type=int, default=2)
    # budget-only mode
    p.add_argument("--budget-only", action="store_true", help="pure-CPU §14 re-estimate from --profile + --plan")
    p.add_argument("--profile", type=Path, help="measured profile JSON (for --budget-only)")
    p.add_argument("--plan", type=Path, help="phase plan JSON (for --budget-only)")
    p.add_argument("--planned-prefill-len", type=int, help="representative prompt length to pick the prefill rate at")
    p.add_argument("--illustrative", action="store_true", help="allow --budget-only from a non-real profile; labels output illustrative")
    args = p.parse_args(argv)

    if args.budget_only:
        if not (args.profile and args.plan):
            p.error("--budget-only requires --profile and --plan")
        if args.output.name == "RESOURCE_PROFILE.json":
            p.error("--budget-only output must not be named RESOURCE_PROFILE.json (it is a BUDGET_REESTIMATE, not a profile)")
        result = _budget_only(args)
        _atomic(args.output, result)
        print(json.dumps({"status": "budget_reestimated", "kind": result["reestimate_kind"],
                          "total_charged_compute_s": round(result["total_charged_compute_s"], 3),
                          "total_true_occupancy_s": round(result["total_true_occupancy_s"], 3),
                          "output": str(args.output.resolve())}, ensure_ascii=False))
        return 0

    # measurement modes
    if args.device == "cpu" and args.output.name == "RESOURCE_PROFILE.json":
        p.error("CPU harness-validation output must NOT be named RESOURCE_PROFILE.json; it is not a real profile (use e.g. RESOURCE_PROFILE_HARNESS_VALIDATION.json)")
    if args.device == "cpu" and args.model_lock:
        p.error("--model-lock with --device cpu is not supported here; the real measurement is the gated cuda:0 path")

    if args.device == "cuda:0":
        # Gated real measurement: full admission, mirroring check_hooks.py.
        # Gate BEFORE any admission work so an unticketed run fails fast (no 60s audit).
        if not args.model_lock:
            p.error("--device cuda:0 requires --model-lock (the locked official checkpoint)")
        if not args.execution_ticket:
            p.error("--device cuda:0 is GATED: pass --execution-ticket <B8-02 id> (intent flag; resource gate=require_admission, approval gate=§F packet)")
        import torch
        from minicpm_research.resources import (RuntimeResourceGuard, audit_resources, require_admission,
                                                research_lock_path, single_worker_lock)
        from minicpm_research.runs import PhaseBudget
        result: dict[str, Any] = {"status": "failed", "started_at": datetime.now(timezone.utc).isoformat(),
                                  "command": sys.argv, "device": args.device, "dtype": args.dtype}
        try:
            with single_worker_lock(research_lock_path()):
                audit = audit_resources(args.output.parent / (args.output.stem + "_resource_audit"), seconds=60)
                admission = require_admission(audit, args.gpu_uuid, args.budget_gib, REPO / "artifacts/reservation")
                os.environ.update(admission["cuda_environment"])
                if torch.cuda.device_count() != 1:
                    raise RuntimeError("CUDA visibility is not exactly one admitted GPU")
                props = torch.cuda.get_device_properties(0)
                if str(getattr(props, "uuid", "")).removeprefix("GPU-") != args.gpu_uuid.removeprefix("GPU-"):
                    raise RuntimeError("CUDA runtime UUID cannot be verified against the admitted UUID")
                torch.cuda.set_per_process_memory_fraction(args.budget_gib * 1024**3 / props.total_memory, 0)
                result["admission"] = admission
                budget = PhaseBudget(REPO / "artifacts/budgets/phase0_gpu_budget.json", 5 * 3600)
                budget.start(f"b802-{time.time_ns()}-{os.getpid()}", f"B8-02:{args.output.resolve()}")

                def resource_event(event: str, **fields: Any) -> None:
                    path = args.output.with_name(args.output.stem + "_resource_events.jsonl")
                    with path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "event": event, **fields}) + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())

                guard = RuntimeResourceGuard(REPO, admission=admission, budget=budget, event_sink=resource_event)
                with guard as active_guard:
                    active_guard.model_loaded = True
                    active_guard.sample()
                    result.update(_measure(args))
                    active_guard.check()
                budget.checkpoint(finish=True)
                result["budget_settlement"] = {"charged_seconds": budget.charged_seconds,
                                               "limit_seconds": budget.limit_seconds,
                                               "attempts": budget.state.get("attempts", [])}
                result["status"] = "completed"
        except Exception as exc:  # preserve evidence on failure
            result["status"] = "failed"
            result["error_type"] = type(exc).__name__
            result["error"] = str(exc)
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        _atomic(args.output, result)
        print(json.dumps({"status": result["status"], "output": str(args.output.resolve()), "error": result.get("error")}))
        return 0 if result["status"] == "completed" else 1

    # CPU harness-validation (no admission, no GPU, tiny control model)
    result = _measure(args)
    result["status"] = "harness_validation_completed"
    result["harness_note"] = ("CPU harness-validation on a tiny random Llama. NOT a real RESOURCE_PROFILE; "
                              "forward/s here do not describe MiniCPM5 on GPU. The real measurement is the "
                              "gated --device cuda:0 path under an approved B8-02 ticket.")
    _atomic(args.output, result)
    print(json.dumps({"status": result["status"], "measurement_kind": result["measurement_kind"],
                      "is_real_profile": result["is_real_profile"], "output": str(args.output.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
