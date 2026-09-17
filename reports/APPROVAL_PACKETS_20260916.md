# APPROVAL PACKETS — gated decisions (2026-09-16 session)

**Purpose (GOAL §4/§11/§16):** For each branch where a human/root approval or human review is the **only** remaining dependency, this file specifies **exactly what is requested, why, the evidence, the decision needed, the consequences, and what remains blocked**. The lead has completed every non-blocked prerequisite it can; these packets stop *only* the blocked branch and do **not** bypass any gate.
**Discipline:** No approval, signature, or audit outcome is fabricated or pre-recorded here. Every packet is `status: PENDING_HUMAN_ROOT_DECISION`. Approving a packet's *text* (e.g. a protocol sidecar) authorizes only what it explicitly says — never an unstated download, GPU run, or freeze.
**Companion records:** `CURRENT_STATE_20260916.{md,json}` (authoritative state), `B8_01_EXECUTION_NOTE_20260916.md` (B8-01), `DOCUMENTATION_DRIFT_ERRATA_20260916.md` (drift).

---

## §A — COMMIT scope + git hygiene (audit F-B8-REPRO-01, F-HEARTBEAT-07, F-COMMIT-08, E-3)

**WHAT IS REQUESTED:** Root-specified commit scope (repository discipline: commits need root to specify scope) for this session's B8-01 evidence + synthesis docs, plus two git-hygiene decisions.

**WHY:** B8-01 v2 is currently **working-tree-only** — the export fix is uncommitted and `TOKEN_ANCHORS.json`/`ENVIRONMENT.json` are untracked, so a clean checkout of HEAD `5e8f769` **KeyErrors** and cannot regenerate them (F-B8-REPRO-01, major). GOAL §16 requires leaving the repo reproducible "from the committed code and preserved artifacts alone."

**EVIDENCE / proposed scope (one ticket-referenced commit):**
- `scripts/export_phase0_artifacts.py` (B8-01 defect fix + 7 audit corrections)
- `artifacts/setup/TOKEN_ANCHORS.json` (sha256 `ecdac639ab8a42aa…`), `artifacts/setup/ENVIRONMENT.json` (sha256 `5b8b5bf6cf96d68b…`)
- `reports/B8_01_EXECUTION_NOTE_20260916.md`, `reports/CURRENT_STATE_20260916.{md,json}`, `reports/DOCUMENTATION_DRIFT_ERRATA_20260916.md`, `reports/APPROVAL_PACKETS_20260916.md`
- Proposed message: `B8-01: phase0 token-anchor + environment export (fix lock_binding tokenizer hash, driver parse); add authoritative current-state record, drift errata, approval packets`
- **Exclude** `.claude/settings.local.json` (gitignored) and decide on `artifacts/reservation/*.jsonl` (below).

**DECISIONS NEEDED:**
1. **Approve the commit** (commit is in the harness `ask` list → it will prompt; approving the prompt = the per-command approval). Or specify a different scope.
2. **F-HEARTBEAT-07:** `artifacts/reservation/gpu{3,5}_reservation.jsonl` are git-tracked append-only heartbeat logs → the live-appended gpu3 log makes the worktree **permanently dirty**. Decide: `gitignore artifacts/reservation/*.jsonl` (+ takeover `.smi`/`.time`) and `git rm --cached` them (keep as untracked runtime logs), **or** accept the permanently-dirty worktree.
3. **F-COMMIT-08 / E-3:** Commit `5e8f769` bundled 67 files / 16,394 insertions under a vague message with no ticket, and its provenance/authorization is unresolved (created ~3 min after a handoff that said "no commit"). Decide whether it stands as-is; adopt ticket-referenced messages and separate data/code/report commits going forward.

**REMAINS BLOCKED AFTER:** Nothing scientific — this is durability/hygiene only. (B8-01 v2 still needs independent re-verification by the Audit Reviewer; that is a read-only follow-up, not a gate.)

---

## §B — PREREG revision v2 approval (**KEYSTONE**) (construct/stats C-08, C-09, C-11, C-12)

**WHAT IS REQUESTED:** Human/main-session approval of `reports/PREREGISTRATION_PHASE0_REVISION_v2.yaml` via its sidecar `reports/PREREGISTRATION_PHASE0_REVISION_v2_APPROVAL.json` (currently `pending_approval`, `approval_record=null`, `freeze.effective=false`).

**WHY:** This single decision **gates** the C-data freeze, Round-1 eligibility, and activation of the S/C round gates. `run_pilot.py` runtime-refuses Round-1 without it. v1 was superseded **pre-approval** (its single overall-intent T gate must NOT be used; v2 demotes it to `supplementary_not_gating`).

**EVIDENCE (verified by construct/stats auditor):**
- All PREREG v2 T/V integer implications **recomputed correct**: format_valid T 48/48, V 36/36; gate_A ≥16/24; gate_B ≥18/36; PE3 ≤3/36; strict ≥20/48; V decisive ≥18/24. contrast_model parameter threshold arithmetic correct (`≥ 2×2,516,756,480 = 5,033,512,960`).
- `contrast_model_rule` well-specified + deterministic (max_switches 1; frozen filters; ascending measured-param ordering, lexicographic repo_id tie-break; loop never reopened).
- `family-clustered` bootstrap is the **correct** dependence unit for Round 1 (fixes the pilot's n=1-family limitation where clustering is impossible → `not_estimable`).

**ISSUE THE APPROVER MUST RESOLVE BEFORE/WITH APPROVAL:**
- **C-08 (major):** the T gate decision rule (`margin≥0.15` AND family-clustered percentile-bootstrap one-sided 95% lower bound of difference > 0) is **statistically fragile and underpowered at Round-1 sizes**. The percentile bootstrap is unreliable at small cluster counts. **Pre-declare** a small-sample-corrected interval (BCa, or a t/reference-distribution interval, or wild cluster bootstrap) **OR** explicitly record that the percentile interval is used with a stated power caveat. Power does **not** become adequate at Round-1 sizes either (cluster-bootstrap simulation) — the approver should accept this as a *revision-protocol* gate (pass/fail for proceeding to a larger round), not a confirmatory power claim.

**DECISION NEEDED:** Approve v2 as-written, approve with the C-08 correction, or reject/revise. **Do not** edit v1 (preserved). Any change to v2 is a new versioned revision.

**REMAINS BLOCKED AFTER APPROVAL:** Round-1 still needs the Round-1 data-freeze record + all batch-10 P1–P8 (incl. B8-02 GPU measurement §F, project-level anchors ✓ done, dry-run, CLI-bound approval, GPU3 reservation takeover, per-worker 60s audit, ≥44 GiB free). S/C gates stay inert until their own data chains complete.

---

## §C — C-v2 data freeze (B9-01) (construct/stats C-01…C-07, C-13; draft packet from the auditor)

**WHAT IS REQUESTED:** Approval to **FREEZE** `artifacts/data/pilot_c_v2.jsonl` (160 rows / 40 families, sha256 `e66fbd2659ef745a13280decf610f84aa4375630a66981b79c077a643f8cf302`) as the Phase-0 C control pool, together with its round family-lists, making the C round gates evaluable. **This packet does NOT request approval to run any model.**

**WHY / GATING:** Freeze is gated on (1) **PREREG v2 approval (§B)** and (2) **B9-03 human gold audit (§G)**. Until both land, C gates stay inert (no runnable code path applies a C gate — verified by grep of evaluation.py/runs.py/run_pilot.py).

**EVIDENCE (verified PASS by construct/stats auditor):**
- C-01: `pilot_c_v2.jsonl` sha256 matches manifest **and** is byte-identical to a fresh deterministic `build_c_pilot()` run.
- C-02: gold verifier **independent at implementation level** — `verifier._verify_c` recomputes the verdict from (rule,claim,evidence), never reads stored gold (corruption leaves output unchanged 160/160).
- C-04: family splitting + namespace disjointness verified (C vs historical V/T overlap empty for family_id/world_id/example_id; combined 760-row `validate_dataset` gold_verified=true, cross_split_leakage=false).
- C-05: degenerate projections independently reproduced — all four constant strategies macro=0.500 on both rounds, user_follower=0.5; **constants cannot pass macro≥0.75**.
- C-13: `label_swap_consistency` measured in **decoded-semantic space** (never raw letters).

**DECISIONS THE APPROVER MUST MAKE:**
- **C-06 (12-over-5 allocation incompatibility, quantified):** equal per-category counts need `5k=12 → k=2.4` (non-integer); two-sided gold balance needs `k` even. A round size of 12 over 5 categories **cannot** satisfy both. Options: **(A) 10 families/round** (exact equal-count 2/category + two-sided balance, lower n — RECOMMENDED for cleanliness); **(B) 15 families/round** (3/category, odd total complicates two-sided balance); **(C) keep 12 with pre-declared UNEQUAL per-category counts** (e.g. 3,3,2,2,2) and two-sided balance maintained within each category (RECOMMENDED if n=12 is required). Pick one and freeze it.
- **C-07 (major, semantic_accuracy ambiguity):** `c_round_gate.semantic_accuracy` says "aggregation: PRIMARY = macro average … min: 0.75" (compensatory) while `integer_rule` implies a per-category floor. **State ONE:** (a) gate = macro≥0.75 only (integer_rule is then a reporting note, not a floor); or (b) gate = every category ≥0.75 (per-category floor). Must be disambiguated **before** freeze.
- **C-03 caveat:** "independent verifier" is implementation-level, **not** a substitute for human gold review — B9-03 R1/R2 (§G) remains a hard prerequisite.
- **C-05 caveat:** the degenerate projection covers only the 5 frozen strategies; it does not exclude an unforeseen surface-correlated heuristic (content-level audit is delegated to B9-03). Keep the repo's **narrow** wording ("constant answers cannot pass"); do **not** inflate to "non-gameable" as a proof (skeptic F-12 concurs).
- **C-10 (note, not C-blocking):** `s_round_gate.integer_rule` has a direction bug (max-direction needs `k≤floor(rate·n)`, not `k≥ceil`) — fix before any **future S** freeze.

**REMAINS BLOCKED AFTER:** C gates evaluable only after PREREG v2 (§B) + B9-03 human sign-off (§G). B8-01 C anchors must be **re-exported after freeze** (currently `provisional_…_not_frozen`).

---

## §D — T03 numerics disposition (skeptic F-01/F-02; t03-numerics audit)

**WHAT IS REQUESTED:** A decision on how to dispose of the T03 BF16 full-vs-cache numerics gate now that the FP32 characterization is complete.

**WHY:** `historical_T03_bf16_gate=failed` is **immutable**; `T03_NUMERICS=failed_limit_recorded`; `new_full_cache_pass_threshold=null`. No status=passed real-model `HOOK_VALIDATION.json` exists. The FP32 characterization is `characterization_not_validation`, `does_not_unlock_t04`, and the runner hard-rejects it as a credential.

**EVIDENCE:** GPU BF16 A−B `0.375/0.75` > `0.5`; FP32 (TF32 off) A−B `3.72e-5/3.77e-5`; CPU BF16 `0.0`; CPU FP32 `~1.6e-5`; B−C batched `0.0`. **Skeptic F-01:** the 2×2 matrix is at least as consistent with a **GPU×dtype×SHAPE interaction** as with BF16 rounding; **F-02:** the discriminating experiment was not run.

**OPTIONS (pick one):**
- **(A) Keep `failed_limit_recorded` permanently** (no new threshold). T03_HOOK split-gate evidence stands as the engineering credential; the numerics limitation is recorded, not re-run. **Lowest risk; recommended default.**
- **(B) Order the optional single-variable SDPA control** (GPU-gated; needs its own ticket) — if a shape/backend change at **fixed BF16** eliminates the 0.75, the effect is shape/backend, not precision; this is the F-02 falsification test.
- **(C) Preregister a NEW full-vs-cache threshold** — must be frozen **BEFORE** any subsequent run, with applicable shape/backend/dtype, statistic, tolerance source, repeat count, failure handling, independent verification scope. **MUST NOT back-fit** a threshold the observed 0.75 would just pass (T03_GATE_DECISION_PLAN §4 forbids this).

**LANGUAGE DISCIPLINE (already applied in CURRENT_STATE §2):** the supported claim is "consistent with a precision-sensitive GPU computation effect within the tested shapes; mechanism unresolved" — **not** "precision-dominant proven". No kernel-level root-cause claim without a kernel trace.

**REMAINS BLOCKED AFTER:** Any GPU control (B) needs a ticket + live admission audit. T04/T05 are not unlocked by any T03 disposition.

---

## §E — S_DATA_PROTOCOL_v3 approval + `approved_source_ids` (s-data audit)

**WHAT IS REQUESTED:** Human/root approval of `reports/S_DATA_PROTOCOL_v3.yaml` via `S_DATA_PROTOCOL_v3_APPROVAL.json`, **and** the explicit `approved_source_ids` subset.

**WHY:** S is the largest remaining Phase-0 gap (no S refusal/benign baselines → admission cannot be evaluated). **Approving the sidecar text authorizes the protocol ONLY — it does NOT authorize any download.** `approved_source_ids=null` currently blocks every source.

**EVIDENCE:** v3 supersedes v2/v1 (both preserved); v3 applied nine-step acquisition sequencing + a benign-answer scoring decision table (27 combos = 18 mapped first-match-wins + 9 impossible, 0 defects, complete/exclusive/non-overlapping, verified programmatically). Candidate sources SRC-1 BeaverTails, SRC-2 AdvBench, SRC-3 XSTest, SRC-4 OR-Bench, SRC-5 SQuAD-v2/TriviaQA — **all `license_status=pending_verification`, capacity UNVERIFIED.**

**THE 9-STEP CHAIN (each a separate decision; nothing is acquired before all complete):**
1. protocol_approval (this packet) → 2. `approved_source_ids` subset → 3. metadata/license **channel** approval (narrow: license text + release metadata only, no payload) → 4. per-source license verification (snapshots into `artifacts/data/s/licenses/`: URL, revision, license sha256) → 5. **data channel** approval per verified source → 6. restricted intake to `/data/restricted/minicpm5_s_intake/<source_id>/` + dual-review staffing (every item dual-reviewed; accepted → `artifacts/data/s/accepted_items/`) → 7. post-intake capacity verification (insufficiency rule fires HERE; padding forbidden) → 8. 100% human gold audit (two independent reviewers, adjudications recorded) → 9. data freeze (family/split + hashes).

**HARD CONSTRAINTS:** No S content may be downloaded/scraped/generated/handwritten before the chain completes. Excluded categories (csam, cbrn operational, weapons operational, cyberattack payloads, doxxing) must never enter repo storage even as a quotation. The infra (`/data/restricted/...`, now existing, jybai:700, empty) is **ready but NOT authorized**.

**DECISION NEEDED:** Approve v3 + name the `approved_source_ids` subset (or keep null = all blocked). **Network caveat:** `huggingface.co` is unreachable (GFW); per-source channel reachability (github/HF) must be verified at steps 3–5; a proxy may be required.

**REMAINS BLOCKED AFTER:** Steps 3–9 each need their own action; S gate (refusal≥0.60 / benign-false-refusal≤0.15) stays inert until freeze.

---

## §F — B8-02 GPU prefill/decode measurement ticket (systems RES-01/RES-05/RES-06; draft packet from the auditor)

**WHAT IS REQUESTED:** An explicit GPU execution ticket + approval for a **RESOURCE_PROFILE** measurement: prefill/decode-separated forward/s + allocator peak on the locked official MiniCPM5-2B. **NOT authorized this turn** (`gpu_execution_this_turn=false`).

**WHY (cannot be satisfied from existing data):** Plan §6.3 lists `RESOURCE_PROFILE.json` as a required Phase-0 artifact; §14 requires all compute budgets be re-estimated from **measured** token/s and forward/s with **prefill and decode measured separately**. RES-06: the T04 aggregate tok/s **conflates prefill and decode** (V's ~8.9 tok/s is dominated by prompt prefill for only 2 decoded tokens) and cannot yield decode forward/s. RES-05: `sampled_own_gpu_memory_max_bytes` (5.36 GiB) is **not** the allocator peak.

**CPU-SIDE WORK ALREADY DONE (no GPU):** budget re-estimation arithmetic from the 4 authoritative runs — fixed overhead ~12.5s/run dominates (model load + tokenize + anchors), plus per-token generation cost; ledger reconciles to 234.429s. This bounds scale-up but **cannot** separate prefill/decode forward/s.

**THE GATED MEASUREMENT (what the ticket would run):** single worker, GPU3 UUID `GPU-e5c246b7…`, 32 GiB budget + 12 GiB reserve, ≥60s read-only admission audit, managed reservation released→restored with heartbeat; record `torch.cuda.max_memory_allocated()`/`max_memory_reserved()` (allocator peak), prefill forward/s and decode forward/s **separately**, over a fixed prefill length grid + decode step grid; bind to model rev `62b9b3bd…`, dtype bfloat16, backend eager. Output a content-addressed `RESOURCE_PROFILE.json` + re-estimated P1–P5 budgets.

**DECISION NEEDED:** Approve the ticket (then it runs under the standard GPU discipline: live admission audit, UUID bind, GPU5/SenseVoice untouched, no auto card-switch). **Until approved, §14 budget re-estimation stays incomplete and Phase-0 admission cannot be met.**

---

## §G — B9-03 human blind-review sign-off (R1/R2) + Level-B full audit

**WHAT IS REQUESTED:** Two independent human reviewers (R1, R2) to complete and sign the **blank** gold-audit sheets in `artifacts/audit/gold_audit_v2/sheets/`, adjudicating disagreements (record-then-adjudicate). This is a **human task by design** (`mode=agent_prepared_materials_only`).

**WHY:** Level A (`gold_audit_v2`) is an agent-prepared deterministic **spot** package: `unlocks_runs=false`, `proves_in_round_files_audited=false`. **manifest + auto-tests are NOT a human-acceptance credential.** Human sign-off is a **hard freeze prerequisite** for C (§C) and for S step 8 (§E).

**EVIDENCE / state:** Level A counts — gold_items V=72, T=48, C=24; surface_items=24; sealed_key_entries=168; **s_template_item_count=0** (S blocked). C coverage: families 12/40, category_rule_gold_cells 12/20 (8 uncovered cells enumerated); the spot audit only **partially** covers proposed in-round families. R1/R2 sheets are blank/unsigned.

**LEVEL B (still `future_package`, does not exist):** the 100% pre-freeze **full in-round** audit is required before **any** round execution. It is **blocked** on three unmet gates: C freeze (§C), round-allocation finalization (§C C-06), and the frozen in-round prompt/gold files. **What CAN be prepared now (CPU-only, AUD-03):** a Level-B builder mode generalizing `make_audit_packages.py` to take a frozen in-round manifest and emit 100% coverage + hash bindings, fixture-tested now so it is ready the moment freeze lands. (Lead can build this tooling next; it does not require approval and touches no frozen files.)

**DECISION NEEDED:** Staff R1/R2 (humans) for Level A signing; schedule Level B generation after C freeze. The lead cannot sign, fabricate, or substitute for this.

---

## Summary — decision queue for the human/root approver

| # | Packet | Decision | Unblocks |
|---|---|---|---|
| §A | Commit scope + git hygiene | approve commit / gitignore heartbeat / 5e8f769 provenance | B8-01 durability, clean worktree |
| §B | **PREREG v2 (KEYSTONE)** | approve (resolve C-08 stat rule) | C freeze, Round-1, S/C gate activation |
| §C | C-v2 freeze | approve freeze + pick C-06 allocation + disambiguate C-07 | C gates evaluable (after §B + §G) |
| §D | T03 disposition | A keep / B SDPA control / C new threshold | T03 closure language |
| §E | S v3 + source ids | approve protocol + name sources | S 9-step chain |
| §F | B8-02 GPU measurement | approve ticket | §14 budget re-estimate, admission |
| §G | B9-03 human review | staff R1/R2 | C/S freeze, Level B |

**Recommended order:** §A (durability) → §B (keystone) → §C+§G (C freeze + human audit) → §F (GPU measurement) → §D (T03) → §E (S chain, longest lead). The lead continues unblocked CPU work (Level-B builder tooling, RESOURCE_PROFILE instrumentation code) in parallel and does **not** wait idle on any gate.
