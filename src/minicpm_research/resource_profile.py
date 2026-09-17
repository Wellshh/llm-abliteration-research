"""B8-02: prefill/decode-separated throughput + allocator-peak profiling, and
measurement-based Phase budget re-estimation (plan §14 / §6.3 RESOURCE_PROFILE).

Why this exists (audit RES-01/RES-05/RES-06):
  - RES-01: plan §14 requires all compute budgets be re-estimated from MEASURED
    token/s and forward/s, with prefill and decode measured SEPARATELY. No
    RESOURCE_PROFILE production code existed.
  - RES-05: the allocator peak must be ``torch.cuda.max_memory_allocated()`` /
    ``max_memory_reserved()``, NOT nvidia-smi process sampling
    (``sampled_own_gpu_memory_max_bytes`` is not a peak).
  - RES-06: aggregate tok/s conflates prefill and decode (V's ~8.9 tok/s is
    dominated by prompt prefill for only 2 decoded tokens) and cannot yield
    decode forward/s. This module times prefill and decode in SEPARATE loops.

Gating: the REAL measurement (forward/s on the locked official MiniCPM5-2B) is a
GPU run requiring an execution ticket + live admission — see
``scripts/profile_resources.py --device cuda:0``. The CPU path here is a
HARNESS-VALIDATION control on a tiny random Llama (NOT MiniCPM5); its numbers are
labelled ``cpu_harness_validation_NOT_a_real_profile`` and must never be cited as
a real RESOURCE_PROFILE. ``reestimate_phase_budgets`` is PURE-CPU math: given a
measured profile (or explicit rates) + planned token counts it produces the §14
per-phase GPU-second re-estimate; it does not itself require a GPU.
"""
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from typing import Any

# Plan §13 phase GPU-hour CAPS (application/stop budgets, NOT measured runtimes).
PHASE_CAP_HOURS: dict[str, float] = {"P0": 5, "P1": 10, "P2": 25, "P3": 40, "P4": 20, "P5": 20}
MAIN_TOTAL_CAP_HOURS: float = 120
# RES-04: charged_seconds is admitted-worker WALL time and EXCLUDES the mandatory
# >=60s pre-admission resource audit per attempt. True GPU occupancy adds it back.
DEFAULT_PRE_ADMISSION_AUDIT_S: float = 60.0
# Audit D1: a §14 re-estimate MUST declare where its rates came from; only a real GPU
# measurement may be labelled a real re-estimate. Enforced by CODE, not by convention/free-text.
VALID_RATE_PROVENANCE: tuple[str, ...] = ("real_gpu_measurement", "cpu_harness_validation", "illustrative")
_REESTIMATE_KIND = {"real_gpu_measurement": "real_gpu_measurement_based",
                    "illustrative": "illustrative_not_a_real_reestimate",
                    "cpu_harness_validation": "cpu_harness_validation_NOT_a_real_reestimate"}


def _sync(device: str) -> None:
    """Barrier so GPU timings are not asynchronous-launch artifacts."""
    if device.startswith("cuda"):
        import torch
        torch.cuda.synchronize()


def measure_prefill_decode(
    model: Any,
    *,
    device: str,
    prefill_lengths: list[int],
    decode_steps: int = 32,
    prefill_repeats: int = 5,
    decode_repeats: int = 3,
    warmup: int = 2,
    model_load_seconds: float | None = None,
) -> dict[str, Any]:
    """Time prefill and decode forward passes SEPARATELY (RES-06) and capture the
    CUDA allocator peak (RES-05).

    Device-agnostic: on ``cuda`` this is a real measurement (cuda.synchronize around
    each timed region); on ``cpu`` it is a harness-validation control whose numbers
    are NOT a real profile. The model is only ever run in inference_mode; weights are
    never mutated. Fixed input ids (seeded) keep the harness deterministic.
    """
    import torch

    if not prefill_lengths or any(int(L) < 1 for L in prefill_lengths):
        raise ValueError("prefill_lengths must be a non-empty list of positive ints")
    if decode_steps < 1 or prefill_repeats < 1 or decode_repeats < 1 or warmup < 0:
        raise ValueError("decode_steps/prefill_repeats/decode_repeats must be >=1 and warmup >=0")

    model.eval()
    vocab = int(model.config.vocab_size)
    is_cuda = device.startswith("cuda")
    measurement_kind = "real_gpu_measurement" if is_cuda else "cpu_harness_validation_NOT_a_real_profile"
    gen = torch.Generator(device="cpu").manual_seed(17)

    def _ids(n: int) -> torch.Tensor:
        return torch.randint(0, vocab, (1, int(n)), generator=gen).to(device)

    if is_cuda:
        torch.cuda.reset_peak_memory_stats()

    prefill: list[dict[str, Any]] = []
    decode: list[dict[str, Any]] = []
    with torch.inference_mode():
        for _ in range(warmup):
            model(input_ids=_ids(min(prefill_lengths)), use_cache=False)
        _sync(device)

        # --- prefill: full-sequence forward, no cache, timed per length ---
        for L in prefill_lengths:
            L = int(L)
            ids = _ids(L)
            mask = torch.ones(1, L, device=device, dtype=torch.long)
            _sync(device)
            t0 = time.perf_counter()
            for _ in range(prefill_repeats):
                model(input_ids=ids, attention_mask=mask, use_cache=False)
            _sync(device)
            dt = time.perf_counter() - t0
            prefill.append({
                "prefill_length": L, "repeats": prefill_repeats, "seconds": dt,
                "forward_per_s": (prefill_repeats / dt) if dt > 0 else None,
                "tokens_per_s": (prefill_repeats * L / dt) if dt > 0 else None,
            })

        # --- decode: prefill once at the longest length, then time single-token
        #     cached decode steps (1 forward == 1 token). Separate loop => the
        #     decode forward/s is NOT contaminated by prefill cost (RES-06). ---
        ref_L = max(int(L) for L in prefill_lengths)
        for _ in range(decode_repeats):
            ids = _ids(ref_L)
            mask = torch.ones(1, ref_L, device=device, dtype=torch.long)
            out = model(input_ids=ids, attention_mask=mask, use_cache=True)
            cache = out.past_key_values
            _sync(device)
            t0 = time.perf_counter()
            for step in range(decode_steps):
                pos = ref_L + step
                next_id = torch.randint(0, vocab, (1, 1), generator=gen).to(device)
                mask = torch.cat((mask, torch.ones(1, 1, device=device, dtype=torch.long)), dim=-1)
                out = model(input_ids=next_id, attention_mask=mask,
                            position_ids=torch.tensor([[pos]], device=device),
                            cache_position=torch.tensor([pos], device=device),
                            past_key_values=cache, use_cache=True)
                cache = out.past_key_values
            _sync(device)
            dt = time.perf_counter() - t0
            decode.append({"decode_steps": decode_steps, "start_cache_length": ref_L,
                           "end_cache_length": ref_L + decode_steps, "seconds": dt,
                           "forward_per_s": (decode_steps / dt) if dt > 0 else None})

    if is_cuda:
        allocator: dict[str, Any] = {
            "allocator_peak_allocated_bytes": int(torch.cuda.max_memory_allocated()),
            "allocator_peak_reserved_bytes": int(torch.cuda.max_memory_reserved()),
            "memory_metric": "torch.cuda.max_memory_allocated/reserved (allocator peak, NOT nvidia-smi process sampling — RES-05)",
        }
    else:
        allocator = {
            "allocator_peak_allocated_bytes": None, "allocator_peak_reserved_bytes": None,
            "memory_metric": "cuda allocator peak unavailable on a cpu harness-validation run",
        }

    decode_fps = [d["forward_per_s"] for d in decode if d.get("forward_per_s") is not None]
    return {
        "schema": "resource_profile_prefill_decode_v1",
        "measurement_kind": measurement_kind,
        "is_real_profile": is_cuda,
        "device": device,
        "dtype": str(next(model.parameters()).dtype),
        "attention_backend": str(getattr(model.config, "_attn_implementation", "eager")),
        "timing_method": "cuda.synchronize+perf_counter" if is_cuda else "perf_counter_no_cuda_sync",
        "prefill": prefill,
        "decode": decode,
        "decode_forward_per_s_median": (statistics.median(decode_fps) if decode_fps else None),
        "decode_rate_caveat": ("decode_forward_per_s is measured from start_cache_length over decode_steps; the KV cache "
                               "grows during decode and across longer contexts, so this rate is CONTEXT-SPECIFIC. A budget "
                               "that applies it uniformly to longer decode is optimistic (audit D4)."),
        "allocator": allocator,
        "model_load_seconds": model_load_seconds,
        "model_class": type(model).__name__,
        "measured_parameters": sum(p.numel() for p in model.parameters()),
    }


def rates_from_profile(profile: dict[str, Any], planned_prefill_len: int) -> dict[str, float | None]:
    """Pick representative prefill tokens/s (at the measured length closest to the
    planned prompt length) and decode forward/s (median) from a measured profile."""
    prefill_rows = [p for p in profile.get("prefill", []) if p.get("tokens_per_s") is not None]
    if not prefill_rows:
        raise ValueError("profile has no usable prefill tokens_per_s")
    closest = min(prefill_rows, key=lambda p: abs(int(p["prefill_length"]) - int(planned_prefill_len)))
    decode_fps = profile.get("decode_forward_per_s_median")
    if decode_fps is None:
        decode_vals = [d["forward_per_s"] for d in profile.get("decode", []) if d.get("forward_per_s") is not None]
        decode_fps = statistics.median(decode_vals) if decode_vals else None
    return {
        "prefill_tokens_per_s": float(closest["tokens_per_s"]),
        "prefill_length_used": int(closest["prefill_length"]),
        "decode_forward_per_s": (float(decode_fps) if decode_fps is not None else None),
    }


@dataclass(frozen=True)
class PhasePlan:
    """Planned workload for one phase (semantic-family/run counts, NOT generation calls)."""
    phase: str
    n_runs: int
    prefill_tokens_per_run: int
    decode_tokens_per_run: int
    attempts_per_run: float = 1.0  # >1 models auditable infra-failure retries

    def __post_init__(self) -> None:
        if self.phase not in PHASE_CAP_HOURS:
            raise ValueError(f"unknown phase {self.phase!r}; expected one of {sorted(PHASE_CAP_HOURS)}")
        if self.n_runs < 0 or self.prefill_tokens_per_run < 0 or self.decode_tokens_per_run < 0:
            raise ValueError("counts/tokens must be non-negative")
        if self.attempts_per_run < 1.0:
            raise ValueError("attempts_per_run must be >= 1.0")


def reestimate_phase_budgets(
    plans: list[PhasePlan],
    *,
    prefill_tokens_per_s: float,
    decode_forward_per_s: float,
    fixed_overhead_per_run_s: float,
    rate_provenance: str,
    pre_admission_audit_s: float = DEFAULT_PRE_ADMISSION_AUDIT_S,
) -> dict[str, Any]:
    """PURE-CPU §14 budget re-estimation from MEASURED rates.

    For each phase: per-run compute = fixed_overhead + prefill_tokens/prefill_tps +
    decode_tokens/decode_fps. Two totals are reported and must not be conflated:
      - ``charged_compute_s``: admitted-worker wall (load+compute+idle), EXCLUDES the
        pre-admission audit — this is what PhaseBudget charges (RES-04).
      - ``true_occupancy_s``: charged + per-attempt pre-admission audit (>=60s) — the
        real GPU-occupancy wall a §14 cap should be checked against.
    A non-finite or non-positive rate is a hard error (fail closed), never silently
    back-filled. This function does NOT require a GPU; it consumes an already-measured
    profile's rates.
    """
    for name, val in (("prefill_tokens_per_s", prefill_tokens_per_s),
                      ("decode_forward_per_s", decode_forward_per_s),
                      ("fixed_overhead_per_run_s", fixed_overhead_per_run_s),
                      ("pre_admission_audit_s", pre_admission_audit_s)):
        if not isinstance(val, (int, float)) or isinstance(val, bool) or not (val > 0) or val != val or val in (float("inf"),):
            raise ValueError(f"{name} must be a finite positive number, got {val!r}")
    if rate_provenance not in VALID_RATE_PROVENANCE:
        raise ValueError(f"rate_provenance must be one of {VALID_RATE_PROVENANCE}, got {rate_provenance!r}")

    per_phase: list[dict[str, Any]] = []
    total_charged = 0.0
    total_occupancy = 0.0
    for plan in plans:
        prefill_s = plan.prefill_tokens_per_run / prefill_tokens_per_s
        decode_s = plan.decode_tokens_per_run / decode_forward_per_s
        compute_per_run = fixed_overhead_per_run_s + prefill_s + decode_s
        charged = plan.n_runs * compute_per_run
        occupancy = plan.n_runs * (compute_per_run + plan.attempts_per_run * pre_admission_audit_s)
        cap_s = PHASE_CAP_HOURS[plan.phase] * 3600.0
        total_charged += charged
        total_occupancy += occupancy
        per_phase.append({
            "phase": plan.phase, "n_runs": plan.n_runs,
            "prefill_tokens_per_run": plan.prefill_tokens_per_run,
            "decode_tokens_per_run": plan.decode_tokens_per_run,
            "attempts_per_run": plan.attempts_per_run,
            "prefill_s_per_run": prefill_s, "decode_s_per_run": decode_s,
            "fixed_overhead_per_run_s": fixed_overhead_per_run_s,
            "compute_s_per_run": compute_per_run,
            "charged_compute_s": charged, "true_occupancy_s": occupancy,
            "cap_s": cap_s, "cap_hours": PHASE_CAP_HOURS[plan.phase],
            "charged_within_cap": charged <= cap_s,
            "occupancy_within_cap": occupancy <= cap_s,
            "charged_utilization_of_cap": charged / cap_s if cap_s else None,
        })
    main_cap_s = MAIN_TOTAL_CAP_HOURS * 3600.0
    return {
        "schema": "resource_budget_reestimate_v1",
        "rate_provenance": rate_provenance,
        "reestimate_kind": _REESTIMATE_KIND[rate_provenance],
        "is_real_reestimate": rate_provenance == "real_gpu_measurement",
        "rates_used": {"prefill_tokens_per_s": prefill_tokens_per_s,
                       "decode_forward_per_s": decode_forward_per_s,
                       "fixed_overhead_per_run_s": fixed_overhead_per_run_s,
                       "pre_admission_audit_s": pre_admission_audit_s},
        "per_phase": per_phase,
        "total_charged_compute_s": total_charged,
        "total_true_occupancy_s": total_occupancy,
        "main_total_cap_s": main_cap_s,
        "total_charged_within_main_cap": total_charged <= main_cap_s,
        "total_occupancy_within_main_cap": total_occupancy <= main_cap_s,
        "caveats": [
            "rates MUST come from a real_gpu_measurement profile (RES-06); cpu_harness_validation rates are NOT valid for a §14 re-estimate",
            "charged_compute_s excludes the >=60s pre-admission audit (RES-04); true_occupancy_s includes it",
            "fixed_overhead_per_run_s should be the measured model-load+tokenize+anchor overhead (~12.5s/run observed in T04, RES-02), not assumed",
            "caps are application/stop budgets, not measured runtimes nor delivery commitments",
        ],
    }
