"""B8-01: project-level Phase 0 standalone artifacts (plan §6.3).

Emits artifacts/setup/TOKEN_ANCHORS.json and artifacts/setup/ENVIRONMENT.json.
CPU-only: loads the LOCKED tokenizer (no model weights, no GPU). S anchors are
NOT fabricated - with S blocked the export is explicitly PARTIAL and fail-closed
(no V/T duplication into the S section). Refuses to overwrite existing outputs.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from minicpm_research.runs import digest, file_hash, source_state

OUT_ANCHORS = ROOT / "artifacts/setup/TOKEN_ANCHORS.json"
OUT_ENV = ROOT / "artifacts/setup/ENVIRONMENT.json"
PER_TASK = 8
C_CATEGORIES_SORTED = ("negation_understanding", "stance_neutral_objective",
                       "surface_refusal_words_non_refusal", "user_stance_agree_vs_oppose",
                       "yes_no_questions")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _atomic(path: Path, payload: Any) -> None:
    if path.exists():
        raise SystemExit(f"REFUSING to overwrite existing {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("x", encoding="utf-8") as h:
        json.dump(payload, h, ensure_ascii=False, indent=1)
        h.write("\n")
        h.flush()
        os.fsync(h.fileno())
    os.replace(tmp, path)


def select_anchor_examples() -> list[tuple[dict[str, Any], str, str]]:
    """Deterministic: (example, source_file, source_status) for V/T (8 each) and C (8)."""
    picked: list[tuple[dict[str, Any], str, str]] = []
    pilot = _read_jsonl(ROOT / "artifacts/data/pilot.jsonl")
    for task in ("V", "T"):
        fams = sorted({e["family_id"] for e in pilot if e["task"] == task})
        if len(fams) < PER_TASK:
            raise ValueError(f"task {task}: need {PER_TASK} families, found {len(fams)}")
        for fid in fams[:PER_TASK]:
            first = sorted((e for e in pilot if e["family_id"] == fid), key=lambda e: e["example_id"])[0]
            picked.append((first, "artifacts/data/pilot.jsonl", "frozen_pilot_pool_batch2"))
    c_rows = _read_jsonl(ROOT / "artifacts/data/pilot_c_v2.jsonl")
    c_by_cat: dict[str, list[dict[str, Any]]] = {c: [] for c in C_CATEGORIES_SORTED}
    for e in c_rows:
        if e["variant_kind"] in ("primary_map_1", "stance_agree"):
            c_by_cat[e["category"]].append(e)
    for cat in c_by_cat:
        c_by_cat[cat].sort(key=lambda e: e["example_id"])
    n = 0
    passes = 0
    while n < PER_TASK and passes < PER_TASK:
        for cat in C_CATEGORIES_SORTED:
            if passes < len(c_by_cat[cat]) and n < PER_TASK:
                picked.append((c_by_cat[cat][passes], "artifacts/data/pilot_c_v2.jsonl", "candidate_draft_not_frozen_B9_01"))
                n += 1
        passes += 1
    if n != PER_TASK:
        raise ValueError(f"C anchor selection produced {n} != {PER_TASK}")
    return picked


def build_anchor(tokenizer: Any, example: dict[str, Any], source_file: str, source_status: str,
                 lock: dict[str, Any], source_sha_cache: dict[str, str]) -> dict[str, Any]:
    """One anchor with P_user / P_boundary / P_decision and decode replay, asserted
    against the actual generation encoding path (run_pilot.build_token_anchor)."""
    import run_pilot
    from minicpm_research.model import render_prompt, token_anchors
    if source_file not in source_sha_cache:
        source_sha_cache[source_file] = file_hash(ROOT / source_file)
    task = example["task"]
    tools = example.get("tools") if task == "T" else None
    base = run_pilot.build_token_anchor(tokenizer, example)  # asserts anchor ids == generation encoding
    ids = base["prompt_token_ids"]
    # assistant-prefix split: template WITHOUT the generation prompt
    gen_kwargs: dict[str, Any] = {"tokenize": False, "add_generation_prompt": False, "enable_thinking": False}
    if tools is not None:
        gen_kwargs["tools"] = tools
    no_gen = tokenizer.apply_chat_template(example["messages"], **gen_kwargs)
    ids_no_gen = tokenizer.encode(no_gen, add_special_tokens=False)
    if ids[:len(ids_no_gen)] != ids_no_gen:
        raise ValueError(f"full prompt does not extend the no-generation-prompt rendering for {example['example_id']}")
    # Locate the LAST role terminator in the no-gen rendering (the pinned template
    # may append trailing whitespace after it); P_user is the token before it.
    terminator_index = None
    for i in range(len(ids_no_gen) - 1, -1, -1):
        if "im_end" in tokenizer.decode([ids_no_gen[i]]):
            terminator_index = i
            break
    if terminator_index is None or terminator_index == 0:
        raise ValueError(f"no role terminator found in no-gen rendering for {example['example_id']}; P_user derivation refused")
    p_user = terminator_index - 1
    if any(marker in tokenizer.decode([ids_no_gen[p_user]]) for marker in ("im_end", "im_start")):
        raise ValueError(f"P_user candidate is a role marker for {example['example_id']}; derivation refused")
    p_boundary = len(ids) - 1               # end of the full assistant prefix; predicts the first generated token
    assistant_prefix_ids = ids[len(ids_no_gen):]
    assistant_prefix_text = tokenizer.decode(assistant_prefix_ids)
    if "assistant" not in assistant_prefix_text:
        raise ValueError(f"assistant prefix does not contain the assistant role marker for {example['example_id']}")
    # decode replay: detokenize->retokenize round trip of the full prompt
    replay_ids = tokenizer.encode(tokenizer.decode(ids, skip_special_tokens=False), add_special_tokens=False)
    anchors_ctx = token_anchors(tokenizer, example["messages"], tools=tools)
    return {
        "example_id": example["example_id"], "family_id": example["family_id"], "task": task,
        "category": example.get("category"), "variant_kind": example.get("variant_kind"),
        "source_file": source_file, "source_sha256": source_sha_cache[source_file], "source_status": source_status,
        "tools_present": base["tools_present"], "tools_sha256": base["tools_sha256"],
        "prompt_token_ids": ids,
        "attention_mask": base["attention_mask"],
        "encoded_prompt_length": base["encoded_prompt_length"],
        "P_user": p_user,
        "P_boundary": p_boundary,
        "P_decision": p_boundary,
        "position_definitions": {
            "P_user": "last real user-content token (index), before the closing role marker of the final user turn",
            "P_boundary": "last token of the full assistant prefix; its hidden state predicts the first generated token",
            "P_decision": "state before generating the decision; for these single-token-start decisions it coincides with P_boundary (plan §6.1)",
        },
        "assistant_prefix": {"token_span": [len(ids_no_gen), len(ids) - 1], "token_ids": assistant_prefix_ids,
                              "decoded_text": assistant_prefix_text},
        "decode_replay": {"round_trip_ids_equal": replay_ids == ids,
                           "note": "detokenize(retokenize(prompt)) == prompt ids under the locked tokenizer"},
        "label_contexts": anchors_ctx.get("label_contexts") if task in ("V", "C") else None,
        "label_contexts_note": ("A/B/C single-token continuation contexts for label tasks" if task in ("V", "C")
                                 else "T decisions are native tool calls / contract text, not single-letter labels"),
        "lock_binding": {"revision_sha": lock["revision_sha"], "tokenizer_sha256": lock["tokenizer_sha256"],
                          "chat_template_sha256": lock["chat_template_sha256"]},
    }


def _driver_from_latest_audit() -> dict[str, Any]:
    """Extract driver/CUDA version from the most recent read-only RESOURCE_AUDIT (no new GPU query)."""
    audits = sorted(ROOT.glob("artifacts/runs/*/*/audit-*/RESOURCE_AUDIT.json"), key=lambda p: p.stat().st_mtime)
    audits += sorted(ROOT.glob("artifacts/hooks/*_resource_audit/RESOURCE_AUDIT.json"), key=lambda p: p.stat().st_mtime)
    audits += sorted(ROOT.glob("artifacts/audits/*/RESOURCE_AUDIT.json"), key=lambda p: p.stat().st_mtime)
    for path in reversed(audits):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            for cmd in doc.get("initial_commands", []):
                if "-q" in cmd.get("argv", []) and "Driver Version" in cmd.get("stdout", ""):
                    line = next(l for l in cmd["stdout"].splitlines() if "Driver Version" in l)
                    parts = {kv.split(":")[0].strip(): kv.split(":")[1].strip() for kv in line.strip().split("   ") if ":" in kv}
                    return {"driver_version": parts.get("Driver Version"), "cuda_version_nvidia_smi": parts.get("CUDA Version"),
                            "source_audit": str(path.relative_to(ROOT)), "source_kind": "historical_read_only_audit"}
        except (OSError, ValueError, StopIteration, KeyError):
            continue
    return {"driver_version": None, "cuda_version_nvidia_smi": None,
            "source_audit": None, "source_kind": "no_historical_audit_found; no new GPU query issued"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-lock", type=Path, default=ROOT / "artifacts/model/MODEL_MANIFEST.json")
    parser.add_argument("--force-status", choices=("partial_S_blocked",), default="partial_S_blocked")
    args = parser.parse_args(argv)

    import torch
    from minicpm_research.model import environment_versions, verify_lock
    from minicpm_research.resources import AUTHORIZED_GPUS, BACKUP_GPU_UUID, PRIMARY_GPU_UUID
    lock = json.loads(args.model_lock.read_text(encoding="utf-8"))
    snapshot = verify_lock(lock)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)

    sha_cache: dict[str, str] = {}
    anchors = [build_anchor(tokenizer, ex, src, status, lock, sha_cache) for ex, src, status in select_anchor_examples()]
    per_task: dict[str, int] = {}
    for a in anchors:
        per_task[a["task"]] = per_task.get(a["task"], 0) + 1
    for a in anchors:
        if not (0 <= a["P_user"] < a["P_boundary"] == a["P_decision"] == a["encoded_prompt_length"] - 1):
            raise ValueError(f"position invariant violated for {a['example_id']}")
        if not a["decode_replay"]["round_trip_ids_equal"]:
            raise ValueError(f"decode replay mismatch for {a['example_id']}")

    tokens_doc = {
        "schema": "phase0_token_anchors_v1",
        "ticket": "B8-01",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "partial_S_blocked",
        "fail_closed": "S anchors are NOT fabricated and NOT filled from V/T; with S blocked the export is explicitly partial",
        "coverage": {
            "V": {"required_min": PER_TASK, "anchors": per_task.get("V", 0), "status": "complete"},
            "T": {"required_min": PER_TASK, "anchors": per_task.get("T", 0), "status": "complete"},
            "C": {"required_min": PER_TASK, "anchors": per_task.get("C", 0), "status": "complete_from_candidate_draft_not_frozen"},
            "S": {"required_min": PER_TASK, "anchors": 0,
                   "status": "blocked",
                   "blocked_reason": "S_DATA_PROTOCOL_v3 proposed_not_approved; no licensed intake; per B8-01 the exporter fails closed for S rather than duplicating V/T",
                   "unblock_path": "protocol approval -> steps 3-7 -> accepted_items exist -> re-export"},
        },
        "lock_binding": {"model_manifest_sha256": file_hash(args.model_lock), "revision_sha": lock["revision_sha"],
                          "tokenizer_sha256": lock["tokenizer_sha256"], "chat_template_sha256": lock["chat_template_sha256"],
                          "snapshot_path": str(snapshot)},
        "device": "cpu_tokenizer_only_no_model_weights_no_gpu",
        "anchors": anchors,
    }
    _atomic(OUT_ANCHORS, tokens_doc)

    src_state = source_state(ROOT)
    env = environment_versions()
    tf32 = {"cuda_matmul_allow_tf32": bool(torch.backends.cuda.matmul.allow_tf32),
            "cudnn_allow_tf32": bool(torch.backends.cudnn.allow_tf32),
            "float32_matmul_precision": str(torch.get_float32_matmul_precision())}
    driver = _driver_from_latest_audit()
    forbidden = sorted(set(range(8)) - {AUTHORIZED_GPUS[PRIMARY_GPU_UUID], AUTHORIZED_GPUS[BACKUP_GPU_UUID]})
    env_doc = {
        "schema": "phase0_environment_v1",
        "ticket": "B8-01",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": env["python"],
        "platform": platform.platform(),
        "packages": {k: env[k] for k in ("torch", "transformers", "tokenizers", "safetensors", "huggingface-hub")},
        "torch_cuda_build_version": torch.version.cuda,
        "nvidia": driver,
        "primary_attention_backend": "eager",
        "primary_dtype": "bfloat16",
        "tf32_state_at_export": tf32,
        "compile_enabled": False,
        "model": {"repo_id": lock["repo_id"], "revision_sha": lock["revision_sha"],
                   "provenance": lock["provenance"], "official_hub_reverification": "pending_network_access",
                   "model_manifest_sha256": file_hash(args.model_lock)},
        "gpu_authorization": {"primary_uuid": PRIMARY_GPU_UUID, "primary_physical_index": AUTHORIZED_GPUS[PRIMARY_GPU_UUID],
                               "backup_uuid": BACKUP_GPU_UUID, "backup_physical_index": AUTHORIZED_GPUS[BACKUP_GPU_UUID],
                               "forbidden_physical_indices": forbidden,
                               "max_formal_workers": 1, "budget_gib_per_gpu": 32, "reserve_gib": 12,
                               "authorization_valid_until": "administrator_explicit_revocation"},
        "source": {"git_commit": src_state.get("git_commit"), "git_scope_note": src_state.get("git_scope_note"),
                    "source_sha256_count": len(src_state.get("source_sha256", {})),
                    "uncommitted_source_changes_present": bool((src_state.get("git_status") or "").strip())},
        "secrets_scan": {"env_variables_embedded": 0, ".env_read": False,
                          "note": "no environment variable values, SSH config, tokens or account credentials are embedded; hub endpoints are public URLs"},
        "gpu_execution_in_this_export": False,
    }
    _atomic(OUT_ENV, env_doc)
    print(json.dumps({"status": "exported", "anchors": len(anchors), "per_task": per_task,
                      "s_status": "blocked", "token_anchors_sha256": file_hash(OUT_ANCHORS)[:16],
                      "environment_sha256": file_hash(OUT_ENV)[:16]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
