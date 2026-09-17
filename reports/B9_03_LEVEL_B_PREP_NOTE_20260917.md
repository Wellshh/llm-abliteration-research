# B9-03 Level-B Builder — Prep Note (tooling ready; content gated on freeze)

**Ticket:** B9-03 (Level B pre-freeze FULL in-round gold audit) · **Date:** 2026-09-17
**Actor:** Research Lead, under GOAL.md §4 ("prepare everything that can be prepared without accessing blocked content") + audit finding AUD-03.
**Status:** **Tooling COMPLETE + fixture-tested. NO Level-B content emitted** (correctly — it is blocked on the C freeze + round-allocation + PREREG v2 approval). No GPU, no model, no S content, no historical-artifact change.

---

## What Level B is (and is not)

- **Level A** (`artifacts/audit/gold_audit_v2/`, built by `scripts/make_audit_packages.py`): stratified **deterministic spot** sample of the data pool; `unlocks_runs=false`, `proves_in_round_files_audited=false`.
- **Level B** (this tooling): **100% full audit of the FINAL in-round prompt/gold files** after a round data freeze; **required before any round execution**. It does **not exist as a package yet** because the frozen in-round files do not exist yet.

## What was built (unblocked prep)

| File | Role |
|---|---|
| `scripts/make_audit_package_level_b.py` | Level-B builder. **Separate script** so the committed Level-A generator (`make_audit_packages.py`) stays byte-unchanged (verified: sha `c7c1a481…` still matches `gold_audit_v2/manifest.json`'s recorded `generator_script.sha256`). **Single-sources the blinding contract** by importing `FORBIDDEN_IN_ITEMS` / `BLINDED_ITEM_KEYS` / `_prompt_text` / `_answer_space` / `_write` from the Level-A module, so Level B blinds **identically**. |
| `tests/test_audit_package_level_b.py` | 10 CPU-only fixture tests (synthetic frozen manifest). |

**Fail-closed gate (the critical property):** `build_level_b` **refuses** (SystemExit) unless the input in-round manifest has `schema=round_in_manifest_frozen_v1`, `freeze_status=="frozen"`, a complete `freeze_record` (`frozen_at` + `data_sha256`), and a non-empty `in_round_examples` list where every example has the required fields and `in_round_eligible != false`. Therefore **Level-B content cannot be produced before the freeze** — the tooling structurally enforces the gate that AUD-02/§G require.

**Honest acceptance flags:** the built package records `level_B_structural_coverage_complete=true` (100% of in-round examples), but `human_signoff_complete=false` and `unlocks_runs=false` — 100% *structural* coverage is prepared; **runs are NOT unlocked until both human reviewers sign and disagreements are adjudicated** (human tasks; `mode=agent_prepared_materials_only`).

**Test result:** `tests.test_audit_package_level_b` 10/10 pass — full coverage (6/6 fixture examples, fraction 1.0), blinding identical to Level A (items carry only `{code,task,prompt,answer_space}`; sealed `example_id`/`family_id` never leak into reviewer blobs), sealed-key bijection, refuse-overwrite, and all six fail-closed refusals (unfrozen status, missing freeze_record, empty examples, missing fields, not-in-round-eligible, wrong schema). **Full CPU suite: 218 tests, OK (skipped=1)** — was 208 before this (+10); zero regressions.

## What remains GATED

- **Emitting the real Level-B package** requires the FROZEN in-round manifest, which requires: PREREG v2 approval (§B) → C-v2 freeze with a resolved round allocation (§C, the 12-over-5 incompatibility) → the round's final in-round prompt/gold files. Until then, `build_level_b` correctly refuses.
- **Human signing/adjudication** (§G): R1/R2 sheets are generated blank; two independent human reviewers must complete and sign them. The builder cannot sign, fabricate, or substitute.

## Provenance / reproducibility

- Uncommitted at note time: `scripts/make_audit_package_level_b.py`, `tests/test_audit_package_level_b.py`, this note.
- Reproduce tests: `CUDA_VISIBLE_DEVICES='' PYTHONPATH=src .venv/bin/python -m unittest tests.test_audit_package_level_b -v`.
- The builder is import-safe and side-effect-free at module load; `build_level_b(manifest, out, seed)` is the testable entry point; `main()` is the thin CLI (`--in-round-manifest`, `--out`, `--seed`).
- Independent review pending (GOAL §12): this lead-implemented tooling is queued for independent re-verification alongside B8-01 v2 and B8-02.
