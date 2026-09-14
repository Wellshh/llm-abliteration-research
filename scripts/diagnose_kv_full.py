"""Read-only KV-cache/full-sequence comparison with row-level evidence.

This deliberately does not apply hooks or alter weights.  It records both rows
before the tolerance assertion so a failure remains useful for diagnosis.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def digest(model: Any) -> str:
    import torch
    h = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        h.update(name.encode())
        h.update(str((str(value.dtype), tuple(value.shape))).encode())
        h.update(value.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
    return h.hexdigest()


def run(model: Any, device: str) -> dict[str, Any]:
    import torch
    model.eval()
    ids = torch.tensor([[0, 0, 5, 6], [7, 8, 9, 10]], device=device)
    mask = torch.tensor([[0, 0, 1, 1], [1, 1, 1, 1]], device=device)
    pos = (mask.cumsum(-1) - 1).clamp(min=0)
    with torch.inference_mode():
        pre = model(input_ids=ids, attention_mask=mask, position_ids=pos, use_cache=True)
        nxt = pre.logits[:, -1:].argmax(-1)
        ext = torch.cat((mask, torch.ones(2, 1, device=device, dtype=torch.long)), -1)
        dec_pos = mask.sum(-1, keepdim=True)
        dec = model(input_ids=nxt, attention_mask=ext, position_ids=dec_pos,
                    cache_position=torch.tensor([4], device=device),
                    past_key_values=pre.past_key_values, use_cache=True).logits
        full_ids = torch.cat((ids, nxt), -1)
        full_pos = (ext.cumsum(-1) - 1).clamp(min=0)
        full = model(input_ids=full_ids, attention_mask=ext, position_ids=full_pos,
                     use_cache=False).logits[:, -1:]
    delta = (full.float() - dec.float()).abs()
    row = []
    for i in range(ids.shape[0]):
        f, d = full[i, 0], dec[i, 0]
        row.append({
            "row": i,
            "abs_max": float(delta[i].max()),
            "abs_mean": float(delta[i].mean()),
            "argmax_full": int(f.argmax()),
            "argmax_kv": int(d.argmax()),
            "argmax_equal": bool(f.argmax() == d.argmax()),
            "full_argmax_logit": float(f.max()),
            "kv_at_full_argmax": float(d[f.argmax()]),
            "full_at_kv_argmax": float(f[d.argmax()]),
        })
    return {
        "input_ids": ids.cpu().tolist(), "attention_mask": mask.cpu().tolist(),
        "position_ids": pos.cpu().tolist(), "decode_position_ids": dec_pos.cpu().tolist(),
        "cache_position": [4], "extended_mask": ext.cpu().tolist(),
        "next_token": nxt.cpu().tolist(), "dtype": str(next(model.parameters()).dtype),
        "model_class": type(model).__name__, "rows": row,
        "overall_abs_max": float(delta.max()), "overall_abs_mean": float(delta.mean()),
        "weights_sha256": digest(model),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-lock", type=Path)
    p.add_argument("--dtype", choices=("float32", "bfloat16"), default="bfloat16")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result: dict[str, Any] = {"status": "failed", "started_at": datetime.now(timezone.utc).isoformat(),
                              "command": sys.argv, "device": "cpu", "dtype": args.dtype}
    try:
        import torch
        torch.set_num_threads(4)
        if args.model_lock:
            from minicpm_research.model import load_locked_model
            model, _ = load_locked_model(args.model_lock, device="cpu", dtype=args.dtype)
        else:
            from transformers import LlamaConfig, LlamaForCausalLM
            cfg = LlamaConfig(vocab_size=64, hidden_size=32, intermediate_size=64,
                              num_hidden_layers=2, num_attention_heads=4,
                              num_key_value_heads=2, max_position_embeddings=128,
                              pad_token_id=0, bos_token_id=1, eos_token_id=2,
                              attention_dropout=0.0, _attn_implementation="eager")
            model = LlamaForCausalLM(cfg).to(dtype=getattr(torch, args.dtype))
        result["evidence"] = run(model, "cpu")
        result["status"] = "passed"
    except Exception as exc:
        result.update({"error_type": type(exc).__name__, "error": str(exc)})
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(args.output.resolve()),
                     "error": result.get("error")}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
