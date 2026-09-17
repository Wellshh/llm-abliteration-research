# B8-01 Execution Note — project-level TOKEN_ANCHORS.json + ENVIRONMENT.json

**Ticket:** B8-01 (plan §6.3 standalone Phase-0 artifacts)
**Date:** 2026-09-16
**Actor:** Research Lead (this session), under GOAL.md §4 immediate mission
**Git base:** HEAD `5e8f7698fa55173c27f896857324037e1de06c14` ("research architecture"), branch `dev`
**Discipline:** CPU-only; no GPU; no model weights loaded (tokenizer only); no S content acquired; no threshold changed; no historical artifact modified.

---

## OBSERVATION (what was directly measured / done)

- **Command:** `.venv/bin/python scripts/export_phase0_artifacts.py`
- **Precondition:** `artifacts/setup/TOKEN_ANCHORS.json` and `artifacts/setup/ENVIRONMENT.json` were ABSENT (the script `_atomic` refuses to overwrite existing outputs — confirmed before running).
- **First run:** exit 1, `KeyError: 'tokenizer_sha256'` at `build_anchor` (script line 143) — the script read a fabricated top-level `lock["tokenizer_sha256"]`.
- **Root cause (DERIVED):** `artifacts/model/MODEL_MANIFEST.json` has NO top-level `tokenizer_sha256` key. The tokenizer hashes live under `files["tokenizer.json"]["sha256"]` (= `3e065a55…`) and `files["tokenizer_config.json"]["sha256"]` (= `e9b10646…`). The script was committed in `5e8f769` but **never executed**, so the schema mismatch went undetected. Cross-check: `run_pilot.build_token_anchor` and `model.verify_lock` never reference `tokenizer_sha256` (they use `revision_sha` + `chat_template_sha256`), confirming the key was invented only by this exporter.
- **Fix applied (minimal, 2 sites):** in `scripts/export_phase0_artifacts.py`, both `lock_binding` constructions (`build_anchor` ~line 143 and `main` tokens_doc ~line 209) changed `lock["tokenizer_sha256"]` → `lock["files"]["tokenizer.json"]["sha256"]`, and added `tokenizer_config_sha256` ← `lock["files"]["tokenizer_config.json"]["sha256"]`. **No change** to anchor selection, position invariants, decode-replay, fail-closed S logic, no-overwrite guard, or any threshold/historical artifact.
- **Re-run:** exit 0. stdout: `{"status":"exported","anchors":24,"per_task":{"V":8,"T":8,"C":8},"s_status":"blocked","token_anchors_sha256":"a4bc59954e20b8a4","environment_sha256":"78331cfb155f319b"}`

## DERIVED RESULT (deterministic checks on the outputs)

- `artifacts/setup/TOKEN_ANCHORS.json` — sha256 prefix `a4bc59954e20b8a4`; schema `phase0_token_anchors_v1`; status `partial_S_blocked`; device `cpu_tokenizer_only_no_model_weights_no_gpu`.
  - Coverage: V 8/8 `complete`; T 8/8 `complete`; C 8/8 `complete_from_candidate_draft_not_frozen`; **S 0/8 `blocked`** (blocked_reason: `S_DATA_PROTOCOL_v3 proposed_not_approved; no licensed intake; exporter fails closed for S rather than duplicating V/T`; unblock_path: `protocol approval → steps 3-7 → accepted_items exist → re-export`).
  - 24 anchors: position-invariant violations **NONE** (`0 ≤ P_user < P_boundary == P_decision == encoded_prompt_length-1`); decode-replay round-trip mismatches **NONE**.
  - C anchors `source_status = candidate_draft_not_frozen_B9_01` (honest tag — C v2 is NOT frozen). V/T anchors `source_status = frozen_pilot_pool_batch2`.
  - lock_binding: model_manifest_sha256 `96985947…`, revision_sha `62b9b3bd…`, tokenizer_sha256 `3e065a55…`, tokenizer_config_sha256 `e9b10646…`, chat_template_sha256 `cc945752…`.
- `artifacts/setup/ENVIRONMENT.json` — sha256 prefix `78331cfb155f319b`; schema `phase0_environment_v1`.
  - python 3.12.1; torch 2.6.0 / transformers 4.56.2 / tokenizers 0.22.2 / safetensors 0.6.2 / huggingface-hub 0.34.4; torch_cuda_build_version 12.4; platform Linux-4.18.0-553.5.1.el8_10.
  - `gpu_execution_in_this_export = false`; primary_attention_backend eager; primary_dtype bfloat16; compile_enabled false.
  - model: repo_id openbmb/MiniCPM5-2B, revision 62b9b3bd…, provenance `mirror_file_hashes_verified`, official_hub_reverification `pending_network_access`, model_manifest_sha256 96985947….
  - gpu_authorization: primary UUID GPU-e5c246b7… (index 3), backup index 5, forbidden [0,1,2,4,6,7], max_formal_workers 1, budget 32 GiB, reserve 12 GiB.
  - source.git_commit `5e8f7698…`.
  - tf32_state_at_export: `cuda_matmul_allow_tf32=false`, `cudnn_allow_tf32=true`, `float32_matmul_precision=highest` (ambient torch state at export; no GPU compute occurred).
  - nvidia: `driver_version=null`, `cuda_version_nvidia_smi=null`, source_kind `historical_read_only_audit` (the `_driver_from_latest_audit` parser did not find a "Driver Version" line in the historical RESOURCE_AUDIT format).

## INTERPRETATION (explanations consistent with the above)

- The two §6.3 standalone Phase-0 artifacts (project-level TOKEN_ANCHORS.json, ENVIRONMENT.json) now EXIST and are batch-10 P1–P8 precondition material. They are **partial**: S anchors are fail-closed (0), C anchors come from an unfrozen candidate.
- The defect was a pure schema-key mismatch in never-executed code, not a scientific or measurement error. The fix aligns the exporter with the actual manifest schema.

## SUPPORTED CLAIM (what can be asserted given controls/sample/scope)

- Within this CPU-tokenizer-only export: the project-level TOKEN_ANCHORS.json contains 24 V/T/C anchors that satisfy the exporter's own position and decode-replay invariants, and the export did NOT fabricate S content (S=0, blocked) and did NOT run any GPU/model compute.
- The exporter's fabricated-key defect is fixed and the script now runs to completion exit 0.

## UNRESOLVED ALTERNATIVES / LIMITATIONS (honest caveats)

- **C anchors are from `candidate_draft_not_frozen` data.** Labeling C coverage "complete" (even qualified as "complete_from_candidate_draft_not_frozen") could be mistaken downstream for frozen-C completeness. C is NOT frozen; these anchors are provisional and must be re-derived after a C freeze.
- **P_decision == P_boundary** is asserted to be "the state before generating the decision". This is plausible for single-token-start V/C label decisions but its meaning for T native tool calls (which begin with a multi-token `<function` opener) is not established by this export. The Skeptic agent is challenging this.
- **decode_replay.round_trip_ids_equal** may be a weak/trivially-true check (detokenize→retokenize under the same locked tokenizer). Under independent review.
- **ENVIRONMENT.json `nvidia.driver_version=null`** — an environment record with null driver/CUDA-version may not fully satisfy the §6.3 "independent ENVIRONMENT.json" intent. The historical-audit parser needs the audit's actual nvidia-smi format.
- **tf32 ambient state** (cudnn_allow_tf32=true) is recorded as-is; the project's FP32 characterization required TF32 OFF. For a CPU-tokenizer-only export this does not affect any computation, but the recorded ambient state should not be read as the project's FP32-run configuration.
- **provenance = mirror_file_hashes_verified** (huggingface.co unreachable). Official-Hub re-verification remains `pending_network_access`.
- **Independent audit PENDING.** Per GOAL §12, this lead-executed export is being independently verified this session by the Reproducibility & Audit Reviewer (hash/invariant/leakage recomputation, test-count reconciliation) and the Skeptical/Red-Team Scientist (falsification of the derivation and the fix). This note is the lead's record; it does NOT pre-claim their verdict.

## PROVENANCE / REPRODUCIBILITY

- Uncommitted changes this session: `scripts/export_phase0_artifacts.py` (the 2-site fix) + new files `artifacts/setup/TOKEN_ANCHORS.json`, `artifacts/setup/ENVIRONMENT.json`. Worktree also carries the pre-existing `M artifacts/reservation/gpu3_reservation.jsonl` (append-only heartbeat).
- **Not committed** — commit requires root-specified scope per repository discipline; deferred to the user.
- Reproduce: `cd <repo> && .venv/bin/python scripts/export_phase0_artifacts.py` (refuses to overwrite the now-existing outputs; delete-and-rerun or use a fresh audit dir to regenerate).
- Exact fix diff: `git diff scripts/export_phase0_artifacts.py` against HEAD `5e8f769`.

---

## v2 AUDIT-DRIVEN CORRECTION (2026-09-16, same session)

The independent team audit (Reproducibility & Audit Reviewer + Skeptical/Red-Team Scientist, GOAL §12) **confirmed the v1 export factually correct and byte-for-byte reproducible**, and **confirmed the lead's `tokenizer_sha256` fix correct and behavior-preserving** (skeptic F-10). It nonetheless identified defects/overclaim-risks that must be closed **before first commit** (any change re-hashes the artifacts). v1 (`a4bc5995…`/`78331cfb…`) was an uncommitted session draft, never relied upon; it was deleted and regenerated as v2 — no historical artifact was touched.

Fixes applied to `scripts/export_phase0_artifacts.py` (all independently justified per GOAL §4):

| Audit id | Sev | Fix |
|---|---|---|
| **F-03** | MAJOR | `_driver_from_latest_audit` parsed nvidia-smi `-q` "Key : Value" lines by splitting one line on 3 spaces → silently yielded `driver_version=null`. Rewritten with regex `Driver Version\s*:\s*(\S+)` / `CUDA Version\s*:\s*(\S+)` over the whole stdout. **ENVIRONMENT.json now records driver_version=`550.54.14`, cuda_version_nvidia_smi=`12.4`** (source: artifacts/audits/20260912-readonly/RESOURCE_AUDIT.json). ENVIRONMENT.json is now fit-for-purpose as the §6.3 independent artifact. |
| **F-B8-LOCK-02** | minor | `lock_binding` bound only 2 of 3 tokenizer files and mislabeled `tokenizer.json`'s hash as `tokenizer_sha256`. Renamed → `tokenizer_file_sha256`, **added `special_tokens_map_sha256`** (`82d96d7a…` — governs the native markers central to the T04 token-aware decode fix), kept `tokenizer_config_sha256`. Full tokenizer identity now bound. |
| **F-06** | minor | Added per-anchor `decision_tokenarity` (`single_token_start_label` for V/C, `multi_token_native_tool_call` for T); `P_decision` definition now states that for T the action is distributed over multiple generated tokens, so `P_decision==P_boundary` is the FIRST-generated-token locus, NOT a single-token decision locus. |
| **F-07 / F-B8-CANCH-03** | minor | C coverage status `complete_from_candidate_draft_not_frozen` → `provisional_8of8_from_candidate_draft_not_frozen__reexport_after_freeze` (the word "complete" over-claimed unfrozen candidate data). |
| **F-08** | info | `decode_replay.note` now states the round-trip is a low-value/near-tautological sanity check and that the MEANINGFUL assertion is `run_pilot.build_token_anchor`'s two-path equality (anchor ids == generation encoding path). |
| **F-09** | minor | `P_user` definition now honest: STRUCTURAL anchor (last token before the final user-turn terminator; may land on punctuation/JSON, not guaranteed semantically decision-relevant). |
| **F-11** | info | `tf32_state_at_export.note` added: ambient state at a CPU-only export, no GPU compute occurred; the T03 FP32 characterization's TF32-off config is NOT represented here. |

**v2 re-export:** exit 0, 24 anchors (V8/T8/C8), S fail-closed (0, blocked). New hashes: `TOKEN_ANCHORS.json` sha256 prefix **`ecdac639ab8a42aa`**, `ENVIRONMENT.json` sha256 prefix **`5b8b5bf6cf96d68b`**.

**v2 lead re-verification (all PASS):** position-invariant violations NONE; decode-replay mismatches NONE; `decision_tokenarity` correct per task; lock_binding has all 4 tokenizer/template hashes + no stale `tokenizer_sha256`; C status relabeled; driver/CUDA version populated; device `cpu_tokenizer_only_no_model_weights_no_gpu`; `gpu_execution_in_this_export=false`; S coverage 0/blocked.

**Still pending (not lead's to close):** independent re-verification of v2 by the Audit Reviewer (v1 was verified; v2 carries the 7 fixes above); commit for durability (F-B8-REPRO-01 — see APPROVAL_PACKETS); re-export of C anchors after a C freeze (F-B8-CANCH-03).

