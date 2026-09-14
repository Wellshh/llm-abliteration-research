"""T03 numerical controls. CPU by default; CUDA requires live same-process admission."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
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


def run_checks(model: Any, device: str = "cpu") -> dict[str, Any]:
    import torch
    from minicpm_research.hooks import PatchSpec, PostBlockHooks
    model.eval()
    inputs = {"input_ids": torch.tensor([[0, 0, 5, 6], [7, 8, 9, 10]], device=device),
              "attention_mask": torch.tensor([[0, 0, 1, 1], [1, 1, 1, 1]], device=device)}
    inputs["position_ids"] = (inputs["attention_mask"].cumsum(-1) - 1).clamp(min=0)
    direction = torch.zeros(model.config.hidden_size, device=device)
    direction[0] = 1
    before = weight_digest(model)
    result: dict[str, Any] = {}
    diff = lambda left, right: float((left.float() - right.float()).abs().max().item())
    with torch.inference_mode():
        baseline = model(**inputs, use_cache=False).logits
        repeated = model(**inputs, use_cache=False).logits
        result["baseline_repeat_max_abs"] = diff(baseline, repeated)
        tolerance = result["baseline_repeat_max_abs"] + 1e-6
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
            if result[key] > tolerance:
                raise AssertionError(f"{key} exceeds observed repeat tolerance: {result[key]}")
        standalone = model(input_ids=inputs["input_ids"][:1, 2:], attention_mask=torch.ones(1, 2, device=device, dtype=torch.long),
                           position_ids=torch.tensor([[0, 1]], device=device), use_cache=False).logits
        result["left_padding_batch_last_logit_max_abs"] = diff(baseline[:1, -1], standalone[:, -1])
        dtype = next(model.parameters()).dtype
        batch_tolerance = 64 * torch.finfo(dtype).eps
        if result["left_padding_batch_last_logit_max_abs"] > batch_tolerance:
            raise AssertionError("left-padding/batch comparison exceeds dtype-scaled tolerance")
        next_token = baseline[:, -1].argmax(-1, keepdim=True)
        extended_mask = torch.cat((inputs["attention_mask"], torch.ones(2, 1, device=device, dtype=torch.long)), dim=-1)
        decode_inputs = {"input_ids": next_token, "attention_mask": extended_mask,
                         "position_ids": inputs["attention_mask"].sum(-1, keepdim=True),
                         "cache_position": torch.tensor([4], device=device), "use_cache": True}
        prefill = model(**inputs, use_cache=True)
        baseline_decode = model(**decode_inputs, past_key_values=prefill.past_key_values).logits
        with PostBlockHooks(model) as identity:
            hooked_prefill = model(**inputs, use_cache=True)
            hooked_decode = model(**decode_inputs, past_key_values=hooked_prefill.past_key_values).logits
        result["kv_identity_max_abs"] = diff(baseline_decode, hooked_decode)
        if result["kv_identity_max_abs"] > tolerance or identity.decode_forward_count != 1:
            raise AssertionError("identity hook did not preserve real KV-cache decode")
        full_ids = torch.cat((inputs["input_ids"], next_token), dim=-1)
        full = model(input_ids=full_ids, attention_mask=extended_mask,
                     position_ids=(extended_mask.cumsum(-1) - 1).clamp(min=0), use_cache=False).logits
        result["kv_vs_full_last_logit_max_abs"] = diff(full[:, -1:], baseline_decode)
        if result["kv_vs_full_last_logit_max_abs"] > batch_tolerance:
            raise AssertionError("KV-cache and full-sequence outputs disagree")
        with PostBlockHooks(model, direction, .5) as projected:
            projected_prefill = model(**inputs, use_cache=True)
            projected_decode = model(**decode_inputs, past_key_values=projected_prefill.past_key_values).logits
        result["projection_logit_max_abs"] = diff(baseline_decode, projected_decode)
        result["projection_hook_manifest"] = projected.manifest()
        expected_tokens = (6 + 2) * model.config.num_hidden_layers
        if projected.projected_valid_tokens != expected_tokens or projected.decode_forward_count != 1:
            raise AssertionError("projection failed valid prefill/decode token accounting")
        if result["projection_logit_max_abs"] <= tolerance:
            raise AssertionError("nonzero projection produced no detectable logit change")
    after = weight_digest(model)
    result.update({"weights_before_sha256": before, "weights_after_sha256": after,
                   "repeat_tolerance": tolerance, "batch_cache_dtype_tolerance": batch_tolerance,
                   "status": "passed", "device": device, "model_class": type(model).__name__,
                   "measured_parameters": sum(p.numel() for p in model.parameters())})
    if before != after:
        raise AssertionError("model state changed during runtime-hook controls")
    return result


def execute(args: Any) -> dict[str, Any]:
    import torch
    torch.set_num_threads(4)
    torch.manual_seed(17)
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
    result = run_checks(model, args.device)
    from minicpm_research.model import environment_versions
    result.update({"model_source": source, "environment": environment_versions(),
                   "finished_at": datetime.now(timezone.utc).isoformat()})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=["cpu", "cuda:0"], default="cpu")
    parser.add_argument("--dtype", choices=["float32", "bfloat16"], default="float32")
    parser.add_argument("--model-lock", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/hooks/HOOK_VALIDATION.json"))
    parser.add_argument("--gpu-uuid", default="GPU-e5c246b7-afc2-cccd-e66d-fa1ca4eb089e")
    parser.add_argument("--budget-gib", type=float, default=32)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; select a new path to preserve earlier validation evidence")
    if args.model_lock and args.dtype != "bfloat16":
        parser.error("official checkpoint validation requires --dtype bfloat16")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {"status": "failed", "started_at": datetime.now(timezone.utc).isoformat(),
                              "command": sys.argv, "device": args.device}
    try:
        from minicpm_research.resources import single_worker_lock
        lock = single_worker_lock(REPO / "artifacts/locks/gpu-worker.lock") if args.device == "cuda:0" else nullcontext()
        with lock:
            if args.device == "cuda:0":
                from minicpm_research.resources import audit_resources, require_admission
                audit = audit_resources(args.output.parent / (args.output.stem + "_resource_audit"), seconds=60)
                admission = require_admission(audit, args.gpu_uuid, args.budget_gib, REPO / "artifacts/reservation")
                os.environ.update(admission["cuda_environment"])
                result["admission"] = admission
            result.update(execute(args))
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    with tmp.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, args.output)
    print(json.dumps({"status": result["status"], "output": str(args.output.resolve()), "error": result.get("error")}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
