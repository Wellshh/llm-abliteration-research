"""T03 numerical controls. CPU by default; CUDA requires live same-process admission."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def weight_digest(model: Any) -> str:
    import torch
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode())
        digest.update(str((str(value.dtype), tuple(value.shape))).encode())
        digest.update(value.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def _precision_backend_state() -> dict[str, Any]:
    """Record the actual matmul/TF32 precision backend so 'FP32' is auditable.

    Nominal FP32 can silently use TF32 (~10-bit mantissa) on CUDA; the exploratory
    FP32 control disables it. BF16 matmuls use the BF16 tensor-core path and are
    unaffected by these flags, but the state is recorded for every run.
    """
    import torch
    return {"cuda_matmul_allow_tf32": bool(torch.backends.cuda.matmul.allow_tf32),
            "cudnn_allow_tf32": bool(torch.backends.cudnn.allow_tf32),
            "float32_matmul_precision": str(torch.get_float32_matmul_precision())}


def run_checks(model: Any, device: str = "cpu", precision_context: dict[str, Any] | None = None,
               exploratory: bool = False) -> dict[str, Any]:
    import torch
    from transformers.cache_utils import DynamicCache
    from minicpm_research.hooks import PatchSpec, PostBlockHooks
    from minicpm_research.model import environment_versions
    model.eval()
    inputs = {"input_ids": torch.tensor([[0, 0, 5, 6], [7, 8, 9, 10]], device=device),
              "attention_mask": torch.tensor([[0, 0, 1, 1], [1, 1, 1, 1]], device=device)}
    inputs["position_ids"] = (inputs["attention_mask"].cumsum(-1) - 1).clamp(min=0)
    direction = torch.zeros(model.config.hidden_size, device=device)
    direction[0] = 1
    before = weight_digest(model)
    result: dict[str, Any] = {}
    diff = lambda left, right: float((left.float() - right.float()).abs().max().item())
    # Every numerical control's value+threshold+passed is accumulated here so it rides
    # in the recoverable diagnostic. In exploratory mode a failed numerical control is
    # RECORDED and execution CONTINUES to collect A/B/C; the BF16 formal path still
    # raises (original behavior). Resource errors / non-finite values still stop both.
    numerical_controls: dict[str, Any] = {}
    def _gate(name: str, value: float, threshold: float, *, passed: bool | None = None, extra: dict[str, Any] | None = None) -> bool:
        # A non-finite control value is a genuine numerical breakdown (NaN/Inf), NOT a
        # tolerance failure: it stops BOTH modes. A finite value over threshold is the
        # only kind exploratory mode records-and-continues past.
        if not math.isfinite(value):
            raise AssertionError(f"non-finite value in numerical control '{name}'; stopping (a breakdown, not a tolerance failure)")
        ok = (value <= threshold) if passed is None else bool(passed)
        entry: dict[str, Any] = {"value": value, "threshold": threshold, "passed": ok}
        if extra:
            entry.update(extra)
        numerical_controls[name] = entry
        return ok
    with torch.inference_mode():
        baseline = model(**inputs, use_cache=False).logits
        repeated = model(**inputs, use_cache=False).logits
        result["baseline_repeat_max_abs"] = diff(baseline, repeated)
        if not math.isfinite(result["baseline_repeat_max_abs"]):
            raise AssertionError("non-finite baseline/repeat logits; stopping (a breakdown, not a tolerance failure)")
        tolerance = result["baseline_repeat_max_abs"] + 1e-6
        numerical_controls["baseline_repeat_max_abs"] = {"value": result["baseline_repeat_max_abs"],
            "derived_hook_tolerance": tolerance,
            "note": "repeat-run noise baseline; identity/zero_alpha/self_patch/kv_identity tolerance = value + 1e-6"}
        with PostBlockHooks(model):
            result["identity_max_abs"] = diff(baseline, model(**inputs, use_cache=False).logits)
        with PostBlockHooks(model, direction, 0):
            result["zero_alpha_max_abs"] = diff(baseline, model(**inputs, use_cache=False).logits)
        with PostBlockHooks(model, capture_positions={0: [(0, 3)]}) as donor:
            model(**inputs, use_cache=False)
        patch = PatchSpec(0, ((0, 3),), donor.captures[0][(0, 3)].unsqueeze(0), donor_id="same_input_baseline")
        with PostBlockHooks(model, patches=[patch]):
            result["self_patch_max_abs"] = diff(baseline, model(**inputs, use_cache=False).logits)
        for key in ("identity_max_abs", "zero_alpha_max_abs", "self_patch_max_abs"):
            _gate(key, result[key], tolerance)
        failed = [k for k in ("identity_max_abs", "zero_alpha_max_abs", "self_patch_max_abs") if not numerical_controls[k]["passed"]]
        if failed and not exploratory:
            raise AssertionError(f"{failed[0]} exceeds observed repeat tolerance: {result[failed[0]]}")
        standalone = model(input_ids=inputs["input_ids"][:1, 2:], attention_mask=torch.ones(1, 2, device=device, dtype=torch.long),
                           position_ids=torch.tensor([[0, 1]], device=device), use_cache=False).logits
        result["left_padding_batch_last_logit_max_abs"] = diff(baseline[:1, -1], standalone[:, -1])
        dtype = next(model.parameters()).dtype
        batch_tolerance = 64 * torch.finfo(dtype).eps
        _gate("left_padding_batch_last_logit_max_abs", result["left_padding_batch_last_logit_max_abs"], batch_tolerance)
        if not numerical_controls["left_padding_batch_last_logit_max_abs"]["passed"] and not exploratory:
            raise AssertionError("left-padding/batch comparison exceeds dtype-scaled tolerance")
        # Fixed next tokens make the A/B/C comparison deterministic and
        # cross-device reproducible (argmax can differ between CPU and GPU).
        # Clamped to the actual vocab so the tiny control model stays valid; the
        # locked official checkpoint (vocab 130560) uses [[49],[350]] verbatim.
        next_token = torch.tensor([[49], [350]], device=device, dtype=torch.long).clamp(max=model.config.vocab_size - 1)
        extended_mask = torch.cat((inputs["attention_mask"], torch.ones(2, 1, device=device, dtype=torch.long)), dim=-1)
        decode_inputs = {"input_ids": next_token, "attention_mask": extended_mask,
                         "position_ids": inputs["attention_mask"].sum(-1, keepdim=True),
                         "cache_position": torch.tensor([4], device=device), "use_cache": True}
        prefill = model(**inputs, use_cache=True)
        prefill_cache_len = int(prefill.past_key_values.get_seq_length())  # captured before decode mutates the cache in place
        baseline_decode = model(**decode_inputs, past_key_values=prefill.past_key_values).logits
        with PostBlockHooks(model) as identity:
            hooked_prefill = model(**inputs, use_cache=True)
            hooked_decode = model(**decode_inputs, past_key_values=hooked_prefill.past_key_values).logits
        result["kv_identity_max_abs"] = diff(baseline_decode, hooked_decode)
        _gate("kv_identity_max_abs", result["kv_identity_max_abs"], tolerance,
              passed=(result["kv_identity_max_abs"] <= tolerance and identity.decode_forward_count == 1),
              extra={"decode_forward_count": identity.decode_forward_count})
        if not numerical_controls["kv_identity_max_abs"]["passed"] and not exploratory:
            raise AssertionError("identity hook did not preserve real KV-cache decode")
        full_ids = torch.cat((inputs["input_ids"], next_token), dim=-1)
        full = model(input_ids=full_ids, attention_mask=extended_mask,
                     position_ids=(extended_mask.cumsum(-1) - 1).clamp(min=0), use_cache=False).logits
        result["kv_vs_full_last_logit_max_abs"] = diff(full[:, -1:], baseline_decode)
        _gate("kv_vs_full_last_logit_max_abs", result["kv_vs_full_last_logit_max_abs"], batch_tolerance)
        # ---- Real A/B/C comparison: A=full sequence, B=prefill+decode, C=token-by-token ----
        # C feeds the four input tokens one at a time through a single persistent
        # cache, then decodes the same fixed next token. It never reuses B's
        # tensors; per-step cache length and the full call sequence are recorded so
        # a degenerate or copied C is detectable. (ERRATUM: the prior C_tokenwise_cache
        # copied B's rows and was not an independent token-by-token comparison.)
        A_last = full[:, -1]                 # [rows, vocab] full-sequence reference (no cache)
        B_last = baseline_decode[:, 0]       # [rows, vocab] 4-token prefill + cached decode
        rows = inputs["input_ids"].shape[0]
        seq_len = inputs["input_ids"].shape[1]
        decode_cache_position = torch.tensor([seq_len], device=device)
        c_cache = DynamicCache()
        c_steps: list[dict[str, Any]] = []
        for t in range(seq_len):
            step_pos = inputs["position_ids"][:, t:t + 1]
            step_out = model(input_ids=inputs["input_ids"][:, t:t + 1],
                             attention_mask=inputs["attention_mask"][:, :t + 1],
                             position_ids=step_pos, cache_position=torch.tensor([t], device=device),
                             past_key_values=c_cache, use_cache=True)
            c_cache = step_out.past_key_values
            step_finite = bool(torch.isfinite(step_out.logits).all())
            if not step_finite:
                # A non-finite intermediate C step is a breakdown even if a later step looks
                # finite (the cache could carry it forward): stop in BOTH modes, do not merely record.
                raise AssertionError(f"non-finite logits at token-by-token C step {t} (cache_position {t}); stopping (a breakdown, not a tolerance failure)")
            c_steps.append({"step": t, "kind": "prefill_token", "token_column": t, "cache_position": t,
                            "mask_prefix_length": t + 1, "position_ids": step_pos.detach().cpu().tolist(),
                            "cache_len_after": int(c_cache.get_seq_length()), "cache_type": type(c_cache).__name__,
                            "logits_finite": step_finite})
        c_decode = model(input_ids=next_token, attention_mask=extended_mask,
                         position_ids=decode_inputs["position_ids"], cache_position=decode_cache_position,
                         past_key_values=c_cache, use_cache=True).logits
        c_steps.append({"step": seq_len, "kind": "decode_next", "cache_position": seq_len,
                        "mask_prefix_length": seq_len + 1,
                        "position_ids": decode_inputs["position_ids"].detach().cpu().tolist(),
                        "cache_len_after": int(c_cache.get_seq_length()), "cache_type": type(c_cache).__name__,
                        "logits_finite": bool(torch.isfinite(c_decode).all())})
        C_last = c_decode[:, 0]              # [rows, vocab] token-by-token cache + decode
        if not bool(torch.isfinite(A_last).all() and torch.isfinite(B_last).all() and torch.isfinite(C_last).all()):
            # Non-finite output is a genuine breakdown, not a tolerance failure: stop in BOTH modes.
            raise AssertionError("non-finite logits in batched A/B/C; stopping (a breakdown, not a tolerance failure)")

        def _pair(left: Any, right: Any, row: int, ln: str, rn: str) -> dict[str, Any]:
            delta = (left[row].float() - right[row].float()).abs()
            idx = int(delta.argmax())
            return {"pair": f"{ln}-{rn}", "row": row, "abs_max": float(delta.max()), "abs_mean": float(delta.mean()),
                    "max_diff_vocab_index": idx, f"{ln}_logit_at_max": float(left[row, idx]),
                    f"{rn}_logit_at_max": float(right[row, idx]), f"argmax_{ln}": int(left[row].argmax()),
                    f"argmax_{rn}": int(right[row].argmax()), "argmax_equal": bool(left[row].argmax() == right[row].argmax())}

        pair_defs = {"A-B": (A_last, B_last, "A", "B"), "A-C": (A_last, C_last, "A", "C"), "B-C": (B_last, C_last, "B", "C")}
        batched_pairwise = {name: [_pair(left, right, row, ln, rn) for row in range(rows)]
                            for name, (left, right, ln, rn) in pair_defs.items()}

        # Single-row variants isolate batch / left-padding / kernel-shape effects
        # from the cache mechanism itself (each row run alone at batch size 1).
        single_row = []
        for r in range(rows):
            s_ids, s_mask, s_pos = inputs["input_ids"][r:r + 1], inputs["attention_mask"][r:r + 1], inputs["position_ids"][r:r + 1]
            s_ext, s_dec_pos, s_nxt = extended_mask[r:r + 1], decode_inputs["position_ids"][r:r + 1], next_token[r:r + 1]
            s_A = model(input_ids=torch.cat((s_ids, s_nxt), -1), attention_mask=s_ext,
                        position_ids=(s_ext.cumsum(-1) - 1).clamp(min=0), use_cache=False).logits[:, -1]
            s_pre = model(input_ids=s_ids, attention_mask=s_mask, position_ids=s_pos, use_cache=True)
            s_pre_len = int(s_pre.past_key_values.get_seq_length())  # before decode mutates the cache in place
            s_B = model(input_ids=s_nxt, attention_mask=s_ext, position_ids=s_dec_pos, cache_position=decode_cache_position,
                        past_key_values=s_pre.past_key_values, use_cache=True).logits[:, 0]
            s_cache = DynamicCache()
            s_lens: list[int] = []
            for t in range(seq_len):
                so = model(input_ids=s_ids[:, t:t + 1], attention_mask=s_mask[:, :t + 1], position_ids=s_pos[:, t:t + 1],
                           cache_position=torch.tensor([t], device=device), past_key_values=s_cache, use_cache=True)
                if not bool(torch.isfinite(so.logits).all()):
                    raise AssertionError(f"non-finite logits in single-row token-by-token C (source_row {r}, step {t}); stopping (a breakdown, not a tolerance failure)")
                s_cache = so.past_key_values
                s_lens.append(int(s_cache.get_seq_length()))
            s_C = model(input_ids=s_nxt, attention_mask=s_ext, position_ids=s_dec_pos, cache_position=decode_cache_position,
                        past_key_values=s_cache, use_cache=True).logits[:, 0]
            if not bool(torch.isfinite(s_A).all() and torch.isfinite(s_B).all() and torch.isfinite(s_C).all()):
                raise AssertionError(f"non-finite logits in single-row A/B/C (source_row {r}); stopping (a breakdown, not a tolerance failure)")
            single_row.append({"source_row": r, "A-B": _pair(s_A, s_B, 0, "A", "B"), "A-C": _pair(s_A, s_C, 0, "A", "C"),
                               "B-C": _pair(s_B, s_C, 0, "B", "C"), "b_prefill_cache_len": s_pre_len,
                               "b_post_decode_cache_len": int(s_pre.past_key_values.get_seq_length()),
                               "c_cache_lengths_per_step": s_lens})

        diag: dict[str, Any] = {
            "schema": "kv_full_abc_v2_real_tokenwise_C",
            "fixed_input_ids": inputs["input_ids"].detach().cpu().tolist(),
            "attention_mask": inputs["attention_mask"].detach().cpu().tolist(),
            "position_ids": inputs["position_ids"].detach().cpu().tolist(),
            "extended_mask": extended_mask.detach().cpu().tolist(),
            "decode_position_ids": decode_inputs["position_ids"].detach().cpu().tolist(),
            "decode_cache_position": decode_cache_position.detach().cpu().tolist(),
            "next_token_fixed": next_token.detach().cpu().tolist(),
            "next_token_selection": "fixed_[[49],[350]]_clamped_to_vocab_size",
            "vocab_size": int(model.config.vocab_size),
            "cache_type": type(prefill.past_key_values).__name__,
            "prefill_cache_len": prefill_cache_len,
            "b_post_decode_cache_len": int(prefill.past_key_values.get_seq_length()),
            "cache_update_is_in_place": True,
            "C_call_sequence": c_steps,
            "batched_pairwise": batched_pairwise,
            "single_row": single_row,
            "numerical_controls": numerical_controls,
            "dtype": str(next(model.parameters()).dtype),
            "attention_backend": str(getattr(model.config, "_attn_implementation", "eager")),
            "environment": environment_versions(),
            "precision_backend": precision_context if precision_context is not None else _precision_backend_state(),
            "config": {"num_hidden_layers": model.config.num_hidden_layers, "hidden_size": model.config.hidden_size,
                       "num_attention_heads": model.config.num_attention_heads,
                       "num_key_value_heads": getattr(model.config, "num_key_value_heads", None)},
            "original_threshold": float(batch_tolerance),
            "original_threshold_formula": "64 * torch.finfo(dtype).eps",
            "original_t03_judgment": "failed",
            "original_evidence_ref": "artifacts/hooks/HOOK_VALIDATION_GPU_DIAG_LUNA2_20260914.json",
            "erratum_ref": "artifacts/hooks/HOOK_VALIDATION_GPU_DIAG_LUNA2_ERRATUM_20260914.json",
        }
        if device.startswith("cuda"):
            diag["peak_memory_allocated"] = int(torch.cuda.max_memory_allocated())
            diag["peak_memory_reserved"] = int(torch.cuda.max_memory_reserved())
        result["kv_full_diagnostics"] = diag
        if not numerical_controls["kv_vs_full_last_logit_max_abs"]["passed"] and not exploratory:
            diag["weights_before_sha256"] = before
            diag["weights_after_sha256"] = weight_digest(model)
            raise AssertionError("KV-cache and full-sequence outputs disagree; structured_diagnostics=" + json.dumps(diag, sort_keys=True))
        with PostBlockHooks(model, direction, .5) as projected:
            projected_prefill = model(**inputs, use_cache=True)
            projected_decode = model(**decode_inputs, past_key_values=projected_prefill.past_key_values).logits
        result["projection_logit_max_abs"] = diff(baseline_decode, projected_decode)
        result["projection_hook_manifest"] = projected.manifest()
        expected_tokens = (6 + 2) * model.config.num_hidden_layers
        _gate("projection_token_accounting", float(projected.projected_valid_tokens), float(expected_tokens),
              passed=(projected.projected_valid_tokens == expected_tokens and projected.decode_forward_count == 1),
              extra={"projected_valid_tokens": projected.projected_valid_tokens, "expected_tokens": expected_tokens,
                     "decode_forward_count": projected.decode_forward_count})
        if not numerical_controls["projection_token_accounting"]["passed"] and not exploratory:
            raise AssertionError("projection failed valid prefill/decode token accounting")
        _gate("projection_logit_max_abs", result["projection_logit_max_abs"], tolerance,
              passed=(result["projection_logit_max_abs"] > tolerance),
              extra={"expectation": "nonzero projection MUST exceed tolerance (a detectable logit change)"})
        if not numerical_controls["projection_logit_max_abs"]["passed"] and not exploratory:
            raise AssertionError("nonzero projection produced no detectable logit change")
    after = weight_digest(model)
    result.update({"weights_before_sha256": before, "weights_after_sha256": after,
                   "repeat_tolerance": tolerance, "batch_cache_dtype_tolerance": batch_tolerance,
                   "numerical_controls": numerical_controls,
                   "status": "characterization_completed" if exploratory else "passed",
                   "device": device, "model_class": type(model).__name__,
                   "measured_parameters": sum(p.numel() for p in model.parameters())})
    if before != after:
        raise AssertionError("model state changed during runtime-hook controls")
    return result


def execute(args: Any) -> dict[str, Any]:
    import torch
    torch.set_num_threads(4)
    torch.manual_seed(17)
    exploratory_fp32 = bool(getattr(args, "exploratory_precision_control", False)) and args.dtype == "float32"
    precision_default = _precision_backend_state()  # state at THIS process's entry (PyTorch defaults); NOT the historical BF16 run's recorded settings
    if exploratory_fp32:
        # Nominal FP32 must not silently use TF32 (~10-bit mantissa); force true FP32 matmuls.
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.set_float32_matmul_precision("highest")
    precision_context = {
        "default_at_entry": precision_default,
        "active_during_run": _precision_backend_state(),
        "tf32_disabled_for_fp32_control": exploratory_fp32,
        "entry_state_note": ("default_at_entry is the TF32/matmul-precision state observed at THIS process's entry "
                             "(PyTorch defaults); it is NOT proof of the historical BF16 run's settings. The BF16 primary "
                             "diagnostic (HOOK_VALIDATION_GPU_ABC_REAL_C_20260914.json) predates precision_backend recording, "
                             "so its TF32 state is not in that artifact and must be referenced from its own contemporaneous "
                             "record. BF16 matmuls use the BF16 tensor-core path and are unaffected by TF32 flags."),
    }
    if args.device == "cuda:0":
        if torch.cuda.device_count() != 1:
            raise RuntimeError("CUDA visibility is not exactly one admitted GPU")
        properties = torch.cuda.get_device_properties(0)
        actual_uuid = str(getattr(properties, "uuid", ""))
        if actual_uuid.removeprefix("GPU-") != args.gpu_uuid.removeprefix("GPU-"):
            raise RuntimeError("CUDA runtime UUID cannot be verified against the admitted UUID")
        torch.cuda.set_per_process_memory_fraction(args.budget_gib * 1024**3 / properties.total_memory, 0)
    if args.model_lock:
        from minicpm_research.model import load_locked_model
        model, _ = load_locked_model(args.model_lock, device=args.device, dtype=args.dtype)
        source = "locked_official_checkpoint"
    else:
        from transformers import LlamaConfig, LlamaForCausalLM
        config = LlamaConfig(vocab_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                             num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=128,
                             pad_token_id=0, bos_token_id=1, eos_token_id=2, attention_dropout=0.0)
        config._attn_implementation = "eager"
        model = LlamaForCausalLM(config).to(device=args.device, dtype=getattr(torch, args.dtype))
        source = "random_tiny_llama_implementation_control_not_MiniCPM5"
    guard = getattr(args, "resource_guard", None)
    handle = None
    if guard:
        guard.model_loaded = True
        guard.sample()
        handle = model.register_forward_pre_hook(lambda *unused: guard.check())
    try:
        result = run_checks(model, args.device, precision_context=precision_context, exploratory=exploratory_fp32)
        if guard:
            guard.check()
    finally:
        if handle is not None:
            handle.remove()
    from minicpm_research.model import environment_versions
    result.update({"model_source": source, "environment": environment_versions(),
                   "finished_at": datetime.now(timezone.utc).isoformat()})
    return result


def _recover_diagnostics(result: dict[str, Any], exc: BaseException) -> None:
    """Preserve structured KV diagnostics embedded in a failure; never lose evidence.

    A failed numerical control is a retained result, not a deleted one. The full
    A/B/C diagnostic travels inside the AssertionError so it survives even though
    run_checks raised before returning its result dict.
    """
    result["status"] = "failed"
    result["error_type"] = type(exc).__name__
    result["error"] = str(exc)
    marker = "structured_diagnostics="
    if marker in str(exc):
        try:
            result["diagnostic_status"] = "completed"
            result["kv_full_diagnostics"] = json.loads(str(exc).split(marker, 1)[1])
        except json.JSONDecodeError:
            result["diagnostic_status"] = "failed_to_parse"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=["cpu", "cuda:0"], default="cpu")
    parser.add_argument("--dtype", choices=["float32", "bfloat16"], default="float32")
    parser.add_argument("--model-lock", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/hooks/HOOK_VALIDATION.json"))
    parser.add_argument("--gpu-uuid", default="GPU-e5c246b7-afc2-cccd-e66d-fa1ca4eb089e")
    parser.add_argument("--budget-gib", type=float, default=32)
    parser.add_argument("--exploratory-precision-control", action="store_true",
                        help="characterization-only FP32 control vs the BF16 primary; NOT a hook-validation credential, never unlocks T04")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; select a new path to preserve earlier validation evidence")
    if args.model_lock and args.dtype != "bfloat16":
        # The BF16 primary guard is unchanged; FP32 on the locked checkpoint is allowed
        # ONLY as an explicitly-flagged characterization control that cannot be a credential.
        if not args.exploratory_precision_control:
            parser.error("official checkpoint validation requires --dtype bfloat16")
        if args.dtype != "float32":
            parser.error("exploratory precision control only supports --dtype float32 against the bfloat16 primary")
        if args.output.name.startswith("HOOK_VALIDATION"):
            parser.error("exploratory characterization output must not be named HOOK_VALIDATION*; it is not a formal hook-validation credential")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    from minicpm_research.model import environment_versions
    result: dict[str, Any] = {"status": "failed", "started_at": datetime.now(timezone.utc).isoformat(),
                              "command": sys.argv, "device": args.device, "dtype": args.dtype,
                              "attention_backend": "eager", "environment": environment_versions()}
    if args.exploratory_precision_control:
        result.update({"role": "characterization_not_validation", "exploratory_precision_control": True,
                       "authoritative_t03_status": "failed_bf16_primary_unchanged", "does_not_unlock_t04": True})
    if args.model_lock:
        from minicpm_research.runs import file_hash
        result["model_manifest_sha256"] = file_hash(args.model_lock)
    try:
        from minicpm_research.resources import RuntimeResourceGuard, research_lock_path, single_worker_lock
        from minicpm_research.runs import PhaseBudget
        lock = single_worker_lock(research_lock_path()) if sys.platform == "linux" or args.device == "cuda:0" else nullcontext()
        with lock:
            admission = None
            budget = None
            if args.device == "cuda:0":
                from minicpm_research.resources import audit_resources, require_admission
                audit = audit_resources(args.output.parent / (args.output.stem + "_resource_audit"), seconds=60)
                admission = require_admission(audit, args.gpu_uuid, args.budget_gib, REPO / "artifacts/reservation")
                os.environ.update(admission["cuda_environment"])
                result["admission"] = admission
                budget = PhaseBudget(REPO / "artifacts/budgets/phase0_gpu_budget.json", 5 * 3600)
                budget.start(f"hooks-{time.time_ns()}-{os.getpid()}", f"T03:{args.output.resolve()}")
            def resource_event(event: str, **fields: Any) -> None:
                path = args.output.with_name(args.output.stem + "_resource_events.jsonl")
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "event": event, **fields}) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
            guard = RuntimeResourceGuard(REPO, admission=admission, budget=budget, event_sink=resource_event) if sys.platform == "linux" else nullcontext()
            try:
                with guard as active_guard:
                    args.resource_guard = active_guard
                    result.update(execute(args))
            finally:
                if budget is not None:
                    budget.checkpoint(finish=True)
                    result["budget_settlement"] = {"charged_seconds": budget.charged_seconds,
                                                   "limit_seconds": budget.limit_seconds,
                                                   "attempts": budget.state.get("attempts", [])}
    except Exception as exc:
        _recover_diagnostics(result, exc)
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    with tmp.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, args.output)
    print(json.dumps({"status": result["status"], "output": str(args.output.resolve()), "error": result.get("error")}))
    return 0 if result["status"] in {"passed", "characterization_completed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
