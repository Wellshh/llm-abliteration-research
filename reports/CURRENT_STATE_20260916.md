# CURRENT STATE — MiniCPM5 refusal-decision audit (authoritative present-tense record)

> **READ §12 FIRST (2026-09-17 addendum).** Sections §0–§11 below are the 2026-09-16 record at HEAD `5e8f769`, preserved
> verbatim. Their present-tense claims about **test count, commit state, B8-01/B8-02/B9-03 status, RES-01/05/06 and D5**
> have been superseded by `§12 ADDENDUM (2026-09-17)` at the end of this file (machine twin:
> `CURRENT_STATE_20260916.json → addendum_20260917`). Nothing below was edited to make later work look compliant.

**Date:** 2026-09-16 · **Branch:** `dev` · **Git base:** HEAD `5e8f7698fa55173c27f896857324037e1de06c14`
**Status of this document:** AUTHORITATIVE PRESENT-TENSE STATE. Created per GOAL.md §1/§14 to resolve documentation drift by provenance and chronology. It **supersedes the present-tense claims** of older summaries where they conflict, but **preserves all historical documents unchanged** (no historical record, threshold, artifact, failure or erratum was edited to produce this file). Machine-readable twin: `reports/CURRENT_STATE_20260916.json`.
**Prepared by:** Research Lead, after an independent 4-role read-only team audit (Reproducibility & Audit Reviewer; Construct/Data/Statistics Researcher; Experimental Systems Engineer; Skeptical/Red-Team Scientist) per GOAL §0/§12.
**Discipline:** calibrated language (GOAL §9). OBSERVATION / DERIVED RESULT / INTERPRETATION / SUPPORTED CLAIM / UNRESOLVED ALTERNATIVE are kept separable. Absence of evidence is not evidence of absence.

---

## 0. Source-of-truth hierarchy (§14)

When documents disagree, resolve in this order (highest first):

1. **Raw run artifacts + manifests + hashes** (`artifacts/runs/**`, `artifacts/hooks/**`, `artifacts/data/**` + manifests) — append-only ground truth.
2. **Approval sidecars + frozen protocol/amendment YAML/JSON** (`reports/*_APPROVAL.json`, `reports/T03_GATE_SPLIT_AMENDMENT_v1.yaml`, `reports/PREREGISTRATION_PHASE0_REVISION_v2.yaml`, `reports/S_DATA_PROTOCOL_v3.yaml`) — authority for what is approved/effective.
3. **This CURRENT_STATE record + its JSON twin** — authoritative present-tense synthesis.
4. **Errata sidecars** (`reports/*ERRATUM*`, `reports/DOCUMENTATION_DRIFT_ERRATA_20260916.md`) — corrections that annotate but never overwrite #1–#2.
5. **Point-in-time reports** (`reports/ALIGNMENT_T00-T04.md`, `reports/INCREMENTAL_*`, `reports/T04_EXECUTION_RUN_REPORT_*`, `handoff.md`) — historical snapshots; read for provenance, NOT for present-tense status where this record updates them.
6. **`README.md`, `docs/research/*` literature reports** — `README` is a convenience summary (known stale); `docs/research/*` are **EXTERNAL priors** (one is AI-generated, header "GOOGLE GEMINI:"), never this project's findings.

**Rule:** a stale present-tense statement in a lower tier does NOT override a higher tier. Known drift is itemized in §9 and in `DOCUMENTATION_DRIFT_ERRATA_20260916.md`.

---

## 1. Per-task status (T00–T05), verified

| Ticket | Present-tense status | Key verified facts |
|---|---|---|
| **T00** resource/permission audit | **aligned** | `RESOURCE_AUDIT.json` complete (60s, 12 samples, 0 errors). GPU3 reservation live (PID 3772767, heartbeat fresh, 32 GiB, UUID GPU-e5c246b7…). GPU5/SenseVoice untouched. |
| **T01** model/template lock | **done via mirror** | `openbmb/MiniCPM5-2B` rev `62b9b3bd…`; MODEL_MANIFEST sha256 `96985947…`; weights sha256 `14fb8e7f…`; 2,516,756,480 BF16 elements. **provenance=`mirror_file_hashes_verified`** (huggingface.co UNREACHABLE; hf-mirror.com works). `official_hub_reverification=pending_network_access`. |
| **T02** data + gold-verifier pilot | **partial** | `pilot.jsonl` 600 rows/180 families (sha `ecbcc6bf…`), **V120/T60 only — S80/C40 absent**. `pilot_c_v2.jsonl` 160 rows/40 families (sha `e66fbd26…`) = **candidate, NOT frozen**. native_xml_v1 parser implemented + verified on real model output at T04 pilot scale (n=4). |
| **T03** hooks + KV/full numerics | **split gate in effect; numerics FAILED (immutable)** | See §2. |
| **T04** restricted pilot | **pilot-only complete** | See §3. |
| **T05** direction extraction + intervention selection | **NOT started; gated** | Requires PREREG v2 approval + Phase-0 admission + separate ticket. No approval authorizes it. |

---

## 2. T03 — exact status triple (never collapse these)

- `historical_T03_bf16_gate = **failed**` — IMMUTABLE. GPU3 BF16 full-vs-cache A−B batched `0.375/0.75` > threshold `0.5` (=64·eps_bf16). Artifact `HOOK_VALIDATION_GPU_ABC_REAL_C_20260914.json`. The 0.5 threshold was an **implementation choice, NOT retroactively pre-registered**.
- `T03_HOOK = passed_under_gate_split_v1` — engineering-control / call-accounting / integrity scope **ONLY**. `T03_HOOK_GATE_v1.json` is `evidence_aggregation_not_runtime_credential`, **NOT** a `HOOK_VALIDATION` run artifact. **No status=passed real-model HOOK_VALIDATION.json exists.**
- `T03_NUMERICS = failed_limit_recorded` — a recorded limitation, **NOT a re-run**. `new_full_cache_pass_threshold = null`.
- **FP32 characterization** (`KV_FULL_GPU_FP32_CONTROL_20260914.json`): GPU A−B `3.72e-5/3.77e-5` vs BF16 `0.75`. `role=characterization_not_validation`, `does_not_unlock_t04=true`, `fp32_is_formal_credential=false`; runner hard-rejects it. No kernel trace.
  - **Skeptic F-01/F-02 (open):** the 2×2 matrix (CPU BF16 0.0 / CPU FP32 ~1.6e-5 / GPU BF16 0.75 / GPU FP32 ~3.7e-5) is **at least as consistent with a GPU×dtype×SHAPE interaction** as with "BF16 rounding". **SUPPORTED CLAIM is only "consistent with a precision-sensitive GPU computation effect within the tested shapes; mechanism unresolved"** — NOT "precision-dominant proven". The discriminating experiment (backend/shape/kernel-trace scan at fixed BF16) is GPU-gated and was NOT run.

---

## 3. T04 — pilot-only (n=1 family/task)

- **4 authoritative runs:** V-base `887571efd14d08b46a94`, V-id `939ad1d5254ed2960bd9`, T-base `7b0b4c88c0af90449723`, T-id `3ec2805afe33d3ef9ee9`. Old T `e40e1134…`/`f4e278b2…` **superseded** by token-aware decode fix (skip_special_tokens=True had stripped native markers).
- **Results (OBSERVATION):** V accuracy 1/3, decisive 1/2=**50%**, parse-valid 1.0. T next-action 2/4, parse-valid 1.0, write 2/4, PE3 1/3, sandbox WRITE_OK 1/READ_OK 2/BLOCKED 1. baseline ≡ identity row-for-row (except generation_seconds).
- **Ledger (DERIVED, reconciles exactly):** total charged `234.42904100380838s` = T03 `128.706022` + T04 authoritative `58.416402` + superseded T `29.783923` + post-admission setup failures `17.522693` (UUID-mismatch `3.620666` + token-type `13.902028`) + pre-admission `0`.
- **power_estimation = not_estimable.** Pilot-only: NOT power, mechanism, or construct-admission evidence.
- **Skeptic F-04 (open):** "baseline≡identity validates plumbing" **cannot distinguish** "identity hook fired and preserved logits" from "identity hook never engaged". **SUPPORTED CLAIM is only** "the two runs share a deterministic, reproducible generation/decode/parse pipeline and the α=0 configuration did not corrupt logits" — NOT "identity hook validated".
- **Systems RES-04/RES-05 (open):** `charged_seconds` is admitted-worker WALL time and **excludes** the mandatory ≥60s pre-admission audit per attempt; `sampled_own_gpu_memory_max_bytes` (`5752487936` ≈ 5.36 GiB) is **NOT** the allocator peak (it is max nvidia-smi process-sample).

---

## 4. Phase-0 construct admission — **NOT met**

`phase0_construct_admission_met = false` (verbatim PREREG). Reasons: V decisive accuracy 1/2=**50% < draft 75%**; S refusal/benign-false-refusal baselines **missing**; power **not_estimable** at 1 family/task; `T03_NUMERICS=failed_limit_recorded`; prefill/decode-separated resource re-estimation **missing**. **No threshold may be changed to pass the gate** (GOAL §4; ALIGNMENT §6 不为过门改阈值). Remediation per plan §6.3: max two pilot revision rounds with logs; else declare the construct unsuitable under the current protocol or move to a contrast model — never relax a threshold to pass.

**B7-01 diagnostic status:** CPU-only, proposes **NO threshold change** (`threshold_change_proposed=false`). V constant-'B'+`<|im_end|>` (token IDs [55,130073]) across all 3 variants/both conditions; prompts differ only at token positions 241/260 (boundary 270). T t-3 premature write with fabricated ID (SKU as item_id) on a CLARIFY gold → sandbox BLOCKED (safety-relevant PE3 event); identity==baseline (not a hook artifact).
- **Construct C-16 + Skeptic F-05 (open):** "model_decision primary locus" is warranted **only in the negative sense** — failures are *not attributable to parser/template-render/sandbox/anchor/run-integrity* (independently verified). At n=3 (V)/n=4 (T), with 1 family/1 label map, **constant-'B' and constant-CONFIRM are observationally equivalent** and H-V1..H-V4 / H-T1..H-T4 have `distinguishable_now=false`. The model-internal sub-locus is **under-determined**; do not cite it as a positive attribution.

---

## 5. Data families

- **S (safety):** **BLOCKED.** `S_DATA_PROTOCOL_v3` sidecar `pending_approval`/`effective=false`; `s_data_status=blocked`; all 9 ledger steps `pending`; `approved_source_ids=null`; every `license_status=pending_verification`; capacity UNVERIFIED. `/data/restricted/minicpm5_s_intake` + `_outputs` now EXIST (jybai:jybai, mode 700) but are **EMPTY and governance-blocked** — infra-ready ≠ authorized. **No S content may be acquired/downloaded/generated/handwritten.** S template item count 0.
- **V (evidence verdict) / T (tool action):** pilot pools exist (V120/T60 in `pilot.jsonl`); formal splits NOT generated; test sealed.
- **C (language/sycophancy control):** `pilot_c_v2.jsonl` = **candidate_draft_not_frozen** (v1 **DISCARDED**, 不得用于任何轮次或冻结). C gates (macro≥0.75, label_swap≥0.85) **inert** until PREREG v2 approval + freeze (no runnable code path applies a C gate — verified by grep). **Open construct findings:** C-07 (`c_round_gate.semantic_accuracy` ambiguous: macro-compensatory vs per-category — must disambiguate before freeze); C-06 (12-family/5-category allocation incompatible: equal per-category needs 5k=12→k=2.4 non-integer, two-sided balance needs k even); C-10 (`s_round_gate.integer_rule` direction bug: max-direction needs `k<=floor`, not `k>=ceil`).
- **Gold-verifier independence (C-02/C-03):** `verifier._verify_c` recomputes the verdict from (rule,claim,evidence) and never reads stored gold — **implementation-level independence** (catches construction bugs). It is **same-author/same-codebase**, NOT source-level independence; **B9-03 R1/R2 blind human audit remains a hard freeze prerequisite.**

---

## 6. Audit / approval status

- **PREREG:** `status=draft_not_registered`; `registration_A/B_frozen=false`. Revision **v2 `proposed_not_approved`/`effective=false`** = **KEYSTONE GATE** (gates C freeze, Round-1 eligibility, S/C gate activation). v1 superseded pre-approval (its single overall-intent T gate must NOT be used; v2 demotes it to `supplementary_not_gating`).
- **B9-03 gold audit:** `gold_audit_v2` = **Level A** agent-prepared deterministic spot package (`mode=agent_prepared_materials_only`), `unlocks_runs=false`, `proves_in_round_files_audited=false`. R1/R2 sheets **blank/unsigned**. **Level B** pre-freeze full in-round audit = `future_package` (does not exist; blocked on C freeze + round-allocation finalization + frozen in-round files). **manifest + auto-tests are NOT a human-acceptance credential.**
- **Test count (VERIFIED this session, F-TEST-04/TEST-01):** `CUDA_VISIBLE_DEVICES='' PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -q` → **187 total / 186 passed / 1 skipped / 0 failed (exit 0)**. Decomposition: 151 (review_20260915 CLOSEOUT, pre-C) + 24 (`test_data_c.py`) + 12 (`test_audit_packages.py`) = 187. **Retire 151/175/183 as historical/superseded; 183 was never reachable from the current tree and was self-inconsistent within commit 5e8f769.** (Discovery collects 188 IDs; the runner's 187 includes 1 platform-skip — F-LOADER-12.)

---

## 7. This session's completed work (B8-01)

**B8-01 (plan §6.3 standalone Phase-0 artifacts) — DONE + audit-corrected to v2.** `scripts/export_phase0_artifacts.py` (CPU-only tokenizer, no weights/GPU, fail-closed on S, refuses overwrite) had a fabricated-key defect (`lock["tokenizer_sha256"]` — KeyError; committed in 5e8f769 but never executed). Lead fixed it; the team audit confirmed the fix correct (skeptic F-10) and surfaced 7 further defects/overclaim-risks, all closed in v2 **before first commit**:
- **F-03 (MAJOR):** ENVIRONMENT.json `nvidia.driver_version` was `null` due to a string-parse bug → fixed (regex); now records `driver_version=550.54.14`, `cuda_version_nvidia_smi=12.4`. ENVIRONMENT.json now fit-for-purpose.
- **F-B8-LOCK-02:** lock_binding now binds full tokenizer identity (`tokenizer_file_sha256` + `tokenizer_config_sha256` + `special_tokens_map_sha256` + `chat_template_sha256`).
- **F-06/F-07/F-08/F-09/F-11:** per-anchor `decision_tokenarity` (T=multi-token), C coverage relabeled `provisional_…__reexport_after_freeze`, honest `P_user`/`P_decision`/`decode_replay`/`tf32` notes.

**v2 outputs (verified, invariants PASS):** `artifacts/setup/TOKEN_ANCHORS.json` (24 anchors V8/T8/C8, **S0 fail-closed blocked**, sha256 prefix `ecdac639ab8a42aa`) + `artifacts/setup/ENVIRONMENT.json` (sha256 prefix `5b8b5bf6cf96d68b`). `gpu_execution_in_this_export=false`. Full record: `reports/B8_01_EXECUTION_NOTE_20260916.md`. **Pending:** independent re-verification of v2; commit for durability (F-B8-REPRO-01).

These two artifacts are **batch-10 P1–P8 precondition material** (project-level TOKEN_ANCHORS.json + independent ENVIRONMENT.json now exist).

---

## 8. Dependency graph (what is blocked on what)

```
[unblocked CPU work — DONE or in progress this session]
  B8-01 export (TOKEN_ANCHORS + ENVIRONMENT) ......... DONE v2 (pending commit + v2 re-verify)
  test-count reconciliation .......................... DONE (187/186/1)
  team audit of Phase-0 state ........................ DONE (4 roles)
  current-state record + errata + approval packets ... THIS DOCUMENT + siblings

[gated — needs human/root approval; packet prepared]
  PREREG v2 approval (KEYSTONE) ──┬─> C-v2 freeze ──> B9-03 Level-B full audit ──> Round-1 eligibility
                                  ├─> activation of C gates (macro>=0.75, swap>=0.85)
                                  └─> Round-1 data-freeze record + batch-10 P1–P8
  S_DATA_PROTOCOL_v3 approval ──> approved_source_ids ──> per-source license/channel ──> restricted intake
                                  ──> capacity verify ──> dual human gold audit ──> S freeze ──> S gate live
  T03 numerics disposition ──> (keep failed_limit_recorded | Option B SDPA control | new preregistered threshold)
  B8-02 GPU measurement ticket ──> prefill/decode forward/s + allocator peak ──> §14 budget re-estimate
  B9-03 human blind review (R1/R2) ──> gold-audit sign-off (Level A) ; Level B needs frozen in-round files

[gated — needs all of the above + Phase-0 admission]
  T05 direction extraction + intervention selection ──> Registration A ──> T06 behavior confirm ──> ...
```

**Critical path to Phase-0 admissibility:** PREREG v2 approval → (C freeze ‖ S chain) → B9-03 Level B + human sign-off → Round-1 data-freeze + batch-10 P1–P8 (incl. B8-02 GPU measurement) → re-pilot under the frozen ≤2-round revision protocol → construct admission re-evaluation. **Phase-0 admission is currently NOT met and must NOT be forced.**

---

## 9. Open audit findings → routing (none silently dropped)

| id | sev | finding | routed to |
|---|---|---|---|
| F-B8-REPRO-01 | major | B8-01 not reproducible from committed code (fix+artifacts uncommitted) | **COMMIT** (approval packet §A) |
| F-03 | major | ENVIRONMENT driver_version=null parse bug | **FIXED in v2** |
| RES-01 | major | RESOURCE_PROFILE production code does not exist (§14 prefill/decode forward/s) | **B8-02 ticket** (packet §E) |
| RES-05 | major | sampled memory ≠ allocator peak | **B8-02** must record torch.cuda.max_memory_allocated/reserved |
| RES-06 | major | aggregate tok/s conflates prefill+decode | **B8-02** GPU measurement |
| F-01/F-02 | major | T03 FP32 "precision-dominant" over-claimed; discriminating experiment not run | **T03 disposition packet §D**; language downgraded in §2 |
| F-04 | major | "baseline≡identity validates plumbing" over-claimed | language scoped in §3 |
| C-07 | major | c_round_gate.semantic_accuracy ambiguous (macro vs per-category) | **C freeze packet §C** (approver must disambiguate) |
| C-08 | major | T gate bootstrap fragile/underpowered at Round-1 sizes | **PREREG v2 packet §B** (pre-declare small-sample-corrected interval) |
| C-10 | minor | s_round_gate.integer_rule direction bug | fix before any future S freeze (packet §C note) |
| F-B8-LOCK-02 / F-06 / F-07 / F-08 / F-09 / F-11 | minor/info | B8-01 labeling/binding overclaim-risks | **FIXED in v2** |
| F-HEARTBEAT-07 | minor | reservation heartbeat logs git-tracked → permanently dirty worktree | gitignore decision (packet §A) |
| F-COMMIT-08 | minor | 5e8f769 bundles 67 files/16k insertions, vague message, no ticket | commit-hygiene note (packet §A) |
| F-LEAK-09 | minor | non-leakage verified at namespace+direct-print level only, NOT semantic | state as "namespace-disjoint + no direct gold print"; semantic-leakage review open until B9-03 human audit |
| F-ALIGN-06 / F-HANDOFF-05 | minor | ALIGNMENT §6 cites S v2 (now v3); handoff test count 183 (now 187) | **DOCUMENTATION_DRIFT_ERRATA** |
| C-17 | info | two extra V-baseline run dirs (27a5f2e/51f6ad0) not labeled superseded | classified: aborted/failed attempts (see T04 ledger); reconcile in run-chain |

---

## 10. Overclaim watchlist (disciplined language boundaries — GOAL §9)

Do **NOT** write, in any report or claim:
- "T03 passed" — only `T03_HOOK=passed_under_gate_split_v1` (engineering scope); BF16 numerics gate is permanently `failed`.
- "FP32 proves precision-dominant root cause" — only "consistent with a precision-sensitive GPU computation effect within tested shapes; mechanism unresolved" (no kernel trace).
- "T04 pilot shows power / mechanism / construct admission" — n=1 family/task, `not_estimable`.
- "baseline≡identity validates the hook" — only "shared deterministic pipeline; α=0 did not corrupt logits".
- "B9-03 Level A = Level B / human-accepted" — Level A is agent-prepared spot material, `unlocks_runs=false`.
- "S approved / S data acquired" — `s_data_status=blocked`, `approved_source_ids=null`.
- "C frozen / C gate evaluable" — `candidate_draft_not_frozen`, gates inert.
- "PREREG registered / Phase-0 admission met" — `draft_not_registered`, `phase0_construct_admission_met=false`.
- "model lock official" — `mirror_file_hashes_verified` only; official-Hub re-verification pending network.
- "no leakage" — only "namespace-disjoint + no direct gold-label print"; semantic non-leakage unproven until human audit.
- "capability preserved / independent / shared circuit / no effect" — these require predeclared non-inferiority/equivalence logic + adequate power, which do not exist yet.
- docs/research/* claims (shared downstream router, 92–95% shared component, systemic verdict bias) as this project's findings — they are EXTERNAL priors.

---

## 11. Provenance / git state / what needs commit

- **HEAD:** `5e8f769` "research architecture" (author wells, 2026-09-16 22:17:32 +0800). This commit **postdates handoff.md** (mtime 22:14:51) which states "本次未提交" and "本目录没有 .git" — both **false of the authoritative repo**; see DOCUMENTATION_DRIFT_ERRATA. Commit provenance/authorization is **unresolved** (created ~3 min after a handoff that said no commit; bundles 67 files incl. handoff.md, both heartbeat logs, verifier.py +182 lines).
- **Uncommitted this session (need commit for durability — F-B8-REPRO-01):**
  - `scripts/export_phase0_artifacts.py` (B8-01 defect fix + 7 audit corrections)
  - `artifacts/setup/TOKEN_ANCHORS.json`, `artifacts/setup/ENVIRONMENT.json` (new v2 outputs)
  - `reports/B8_01_EXECUTION_NOTE_20260916.md`, this `CURRENT_STATE_20260916.{md,json}`, `DOCUMENTATION_DRIFT_ERRATA_20260916.md`, `APPROVAL_PACKETS_20260916.md`
  - `.claude/settings.local.json` (gitignored — harness permissions, not committed)
  - pre-existing `M artifacts/reservation/gpu3_reservation.jsonl` (append-only heartbeat)
- **Commit requires root-specified scope** per repository discipline; deferred to the user (see APPROVAL_PACKETS §A). **Not committed by the lead unilaterally.**
- **Reproducibility:** another researcher can regenerate B8-01 v2 from the working tree (`.venv/bin/python scripts/export_phase0_artifacts.py` after deleting the outputs); CPU suite reproduces 187/186/1; T04 chain reproduces via `reports/review_20260914/reproduce_review.py` (exit 0). **Until committed, B8-01 v2 is working-tree-only.**

---

*This record is the lead's synthesis. The independent audit's per-role findings, verified-pass lists, and disagreements are preserved in the team-audit transcript and summarized in §7/§9. No historical document was altered to produce it.*

---

## 12. ADDENDUM (2026-09-17) — present-tense refresh at HEAD `fbb363c` + this session

**Why:** GOAL §1/§14 — the §0–§11 record above had drifted in exactly the way it warns about (it says 187 tests, "B8-01 pending commit + re-verification", "RESOURCE_PROFILE production code does not exist", "HEAD `5e8f769`"). All four are now false of the tree. The sections above are preserved verbatim; this addendum is the current present tense.

### 12.1 What changed since `5e8f769` (all committed and pushed; `dev` == `origin/dev`)

| commit | content | present-tense status |
|---|---|---|
| `bcfd237` | B8-01 v2 exporter + `TOKEN_ANCHORS.json` + `ENVIRONMENT.json` + this record | **committed** → closes **F-B8-REPRO-01** (reproducibility no longer depends on a working tree) |
| `8ac8c61` | B8-02 `resource_profile.py` + `profile_resources.py` + CPU harness artifact | **committed**; RES-01/05/06 now have real code, **still no measured `RESOURCE_PROFILE.json`** |
| `84f1952` | B9-03 Level-B builder (`make_audit_package_level_b.py`), fail-closed pre-freeze | **committed**; Level-B **content** still does not exist (needs C freeze + frozen in-round files) |
| `fbb363c` | §12 re-verification hardening D1–D4 + `INDEPENDENT_REVERIFICATION_20260917.md` | **committed**; D5 deferred by decision |

- **CPU suite (verified this session):** `CUDA_VISIBLE_DEVICES='' PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -q` → **241 tests, OK (skipped=1)**. Decomposition: 187 (§6, 2026-09-16) + 21 (B8-02) + 10 (Level-B) + 5 (D1/D3 hardening) + 18 (`tests/test_phase0_anchors.py`, this session). §6's `187/186/1` is historical.
- **§12 independent re-verification of B8-01 v2 / B8-02 / Level-B:** Reproducibility & Audit Reviewer `confirmed_sound`; Skeptic `confirmed_with_minor_issues` (5 defense-in-depth/disclosure gaps, "not correctness errors in what shipped"). D1–D4 fixed at `fbb363c`; both reviewers' honest caveat stands: **the post-gate GPU measurement path has never executed** — it is verified by code order + unit tests only.
- **RES-01/05/06 disposition:** code exists (prefill/decode timed in separate loops with `cuda.synchronize` brackets; allocator peak via `torch.cuda.max_memory_allocated/reserved`; `rate_provenance` enum now required so cpu/illustrative rates cannot be stamped as a real §14 re-estimate). The real `RESOURCE_PROFILE.json` + §14 re-estimate remain behind the **§F ticket**.

### 12.2 D5 — deferral re-affirmed, requirement converted from prose into code

`P_decision == P_boundary` for T remains a **first-generated-token** locus, not a single-token decision locus (plan §6.1; audit F-06). The 2026-09-17 deferral reasoning still holds — a machine-readable single-locus flag would change `TOKEN_ANCHORS.json` (`ecdac639ab8a42aa…`) and `ENVIRONMENT.json` (`5b8b5bf6cf96d68b…`), invalidating the byte-identical 24/24 anchor reproduction in `INDEPENDENT_REVERIFICATION_20260917.md` and the batch-10 P1–P8 precondition binding — **but** the carry-forward was "the T05 implementer MUST read the disclosure", i.e. enforced by reading discipline, the very pattern the reviewers flagged in D1.

New: `src/minicpm_research/phase0_anchors.py` is the load/consume API. `single_token_decision_locus()` **raises** `AmbiguousDecisionLocusError` for any anchor with `decision_tokenarity=multi_token_native_tool_call` (all 8 T anchors); `first_generated_token_locus()` returns `is_single_token_decision_locus=False` **by construction** (where a T decision lives is what T05 must find out, not what an anchor file may assert); `load_anchor_package()` fail-closes if a future re-export drops the phrase `NOT a single-token decision locus`, mislabels a T anchor as single-token, or breaks `P_decision == P_boundary`. Pinned by `tests/test_phase0_anchors.py` against the **committed** artifact (V8/T8/C8, S0 `blocked`, C still `candidate_draft_not_frozen…reexport_after_freeze`, lock binding == `MODEL_MANIFEST.json`). **Both B8-01 artifact hashes are byte-unchanged.** Exit condition for reversing the deferral: approved amendment **before** re-export → §12 re-verification of the new bytes → update every record citing the old hashes → green suite; the mandated post-freeze C re-export (§C / F-07) is the natural moment to bundle it.

**Honest limit:** this enforces the **API** path. `json.load("artifacts/setup/TOKEN_ANCHORS.json")` + `anchor["P_decision"]` is still available to anyone and no test can block it. What changed is that the default, discoverable route now refuses the wrong read and explains why, and that the F-06 disclosure can no longer vanish silently from a re-export. Making the T05 extraction code consume `phase0_anchors` exclusively is a **code-review rule for that ticket**, not something this commit can guarantee.

### 12.3 New findings routed out of the §B/§C decision queue

Full evidence + diff-ready texts: **`reports/PREREG_V2_PROSPECTIVE_FIXES_20260917.md`** (PROPOSED; it edited **no** pending-approval text).

- **C-06 corrected (the §C trichotomy is wrong).** Families are single-gold (verified 40/40) and each contributes exactly 2 in-round rows, so the implemented generator allocates **gold-balanced pairs**: `propose_round_families()` reproduces **both** round lists in `C_DATA_FREEZE_DRAFT_v2.md` byte-exactly, disjoint, 16 reserve families, per-category families `{4,2,2,2,2}`. 12 families/round **does** satisfy two-sided family-level balance — §C's option **C `{3,3,2,2,2}` is infeasible** (a 3-family single-gold cell cannot be 1.5T/1.5F) and option **B `{3,3,3,3,3}` silently tightens** accuracy to 5/6 = 83.3 % and consistency to 11/12 = 91.7 %. Degenerate projection on the **actual** round sets: all four constant strategies macro = 0.500.
- **C-18 (new, freeze-blocking for the C gate text).** `label_swap_consistency.pair_set` is undefined for `user_stance_agree_vs_oppose`: those 8 families have **no** `primary_map_*` pair (they pair by stance with identical gold, verified 8/8), so the denominator is ambiguous — **10 pairs → 9/10 = 90.0 %** vs **12 pairs → 11/12 = 91.7 %** per round. The approver must pick a definition; recommendation is to keep `label_swap_consistency` literal and report `stance_consistency` separately (two constructs, one number each — GOAL §7).
- **C-10 confirmed text-only, direction bug.** Zero code paths evaluate `s_round_gate`/`integer_rule` (grep over `src`, `scripts`, `tests` → 0 hits). `benign_false_refusal_rate_max=0.15` needs `k ≤ floor(0.15·n)`; the written `k ≥ ceil(0.15·n)` **inverts** it (n=10 would fail a model with zero benign false refusals). Direction fix, no threshold value changes.
- **C-07** still requires the approver to state one reading; under the implemented `{8,4,4,4,4}` cells the two readings actually differ in verdict (one category at 2/4 with four perfect: macro 0.90 passes the compensatory reading, fails the per-category-floor reading). Note macro ≡ micro **only** for equal-sized cells, which this allocation is not.

### 12.4 What is still true and still blocked (unchanged by any of the above)

`phase0_construct_admission_met = **false**` — V decisive 1/2 < draft 75 % at n=1 family; S baselines missing (S blocked, 9-step chain all pending); power `not_estimable`; `T03_NUMERICS = failed_limit_recorded`; **measured** prefill/decode re-estimation still missing (§F unapproved). PREREG still `draft_not_registered`; revision v2 still `proposed_not_approved` / `effective=false`; C still `candidate_draft_not_frozen`; B9-03 still Level-A agent-prepared with **blank/unsigned** R1/R2 sheets; T05 / formal test / intervention selection / test unsealing remain gated. §A's heartbeat-gitignore and `5e8f769`-provenance questions remain open; `artifacts/reservation/gpu3_reservation.jsonl` remains permanently dirty (append-only heartbeat, deliberately not committed).

**Constraints honored this session:** no GPU or model process, no S content acquired or generated, no historical threshold/artifact edited, no pending-approval protocol text edited, no GPU5/other-process contact. §12 status of this addendum itself: the D1–D4 code and the new anchor accessor are scheduled for independent re-verification (GOAL §12); until that record exists, §12.1–§12.3 are lead-authored claims, not independently confirmed ones.

### 12.5 Round B found a major defect in §12.3 — author-fixed, **fix pending round-C verification** (2026-09-17, appended; verdict wording corrected after the 2026-09-17 human/root review)

The scheduled §12 re-verification ran as three independent read-only reviewers. **This round did not close the loop:
it found one major statistical defect in §12.3's own packet (CS-1), which the lead then authored a fix for; that fix
and the new fail-closed code are self-tested only and are owed a round C.** Two reviewers returned
`confirmed_with_minor_issues`; the construct/stats reviewer confirmed the C-pool arithmetic independently but returned
a **major** finding (CS-1) plus minors — so the round's net verdict is "major found, author-fixed, fix unverified,"
not "all confirmed with minor issues." Full record: **`reports/INDEPENDENT_REVERIFICATION_20260917B.md`** (its own
verdict header now carries the same correction). What it changed:

- **The one that mattered (major, in §12.3's own packet):** both proposed C-18 texts fixed an expected pair count but
  left the **consistency denominator output-dependent** — under v2's `missing_or_invalid_side` clause a model that
  emits malformed output on the pairs it fails *lowers its own requirement* (9/10 → 7/8 → 6/7). Packet §4.1 now adds
  the fix (denominator frozen at freeze time; an invalid side counts as NOT consistent and stays in the denominator),
  matching `t_round_gate`'s gold-frozen pattern and GOAL §6. Also corrected in the packet: the "keeps both nominal
  floors exact" claim (consistency is 9/10 = **90 %**, not 85 %), a family-cost figure that matched no unit (whole-family
  miss = **50 pp** of a 4-row cell, not 12.5), "satisfies both properties" (it satisfies *size + balance* by dropping
  equal counts), the undefined `n_category` row membership, the missing C-08 pointer, and a rejected third C-18 option
  that a constant answerer would pass with certainty.
- **Code hardening (+16 tests, suite now 257 / OK / skipped=1):** `--budget-only` no longer accepts a profile's
  *self-declared* `is_real_profile`/`measurement_kind` as provenance — a real claim now requires the structural
  markers only the gated path writes (`admission` + `budget_settlement`) plus a `model_manifest_sha256` re-verified
  against `--model-lock`; the anchor loader enforces the S-blocked coverage policy and integer-typed positions; the
  Level-B freeze binding refuses absolute/`..` paths and manifests that bind no file under `artifacts/data/`.
- **The record's own strongest claim is now code, not prose** (skeptic RT-3): `ProvenancePinTests` pins both B8-01
  sha256s **and** a digest of all 24 `(example_id, task, P_user, P_boundary, P_decision)` tuples, with an explicit
  escape hatch — it is *expected* to fail when the §C/F-07 post-freeze C re-export runs, and may be updated only with
  the approving amendment, a fresh §12 record, and every citing report updated.
- **Honest residuals:** `phase0_anchors` is still imported by nothing but its tests (making consumption mandatory is a
  T05 review rule); its checks are disclosure-consistency, not truth-of-content; and **the round-B fixes are
  themselves lead-authored code tested only by their author** — a round C is owed before anything in §12.5 is treated
  as independently confirmed.
- **Sync note (RT-1, and a standing rule):** §12.1's "HEAD `fbb363c` / dev == origin/dev" was already stale at the
  moment of its own commit. Actual sequence: `fbb363c` → `8c229ca` (D5 accessor) → `a688149` (state refresh + packet,
  then pushed) → the round-B remediation commit. **Re-derive HEAD with `git rev-parse`; never trust a recorded hash
  over the repository.**
- **Test-count reconciliation for future agents (RA-5):** unittest reports **`Ran 257`** while `grep -c 'def test_'`
  gives **258** — the difference is the single always-skipped `test_resources.py:209` platform skip, which Python 3.12
  excludes from `testsRun`. Same off-by-one explains the historical "187 tests" vs 188 definitions.

### 12.6 Round C run + the two §4 argumentation fixes + C-08/C-07 sensitivity analysis (2026-09-17, appended)

The 2026-09-17 human/root review **did not approve PREREG v2 or authorize a C freeze or any GPU ticket**; it returned
three work items, all done or in flight this session, with `phase0_construct_admission_met=false` and every gate status
unchanged throughout.

- **Two argumentation errors in the §B/§C packet §4, corrected in place** (`PREREG_V2_PROSPECTIVE_FIXES_20260917.md`,
  §8 v3 provenance records it). (1) §4(iii) argued pooling the two pair types "lowers the bar" on the map-invariance
  gate — **false**: solo swap `ceil(.85·10)=9/10`, pooled `ceil(.85·12)=11/12`; with both stance pairs free the pooled
  11 is met by 9 swap + 2 stance (== the solo `9/10`) and one stance miss forces `10/10`, so pooling **holds or tightens**
  the swap requirement, never relaxes it; recommendation (i) now rests on construct purity alone. (2) §4(iii) rejected a
  stance-only gate because "a constant answerer trivially passes stance consistency" — but the two *semantic* constants
  score **10/10 on label-swap too** (only the *letter* constants fail swap, 0/10), so that argument does not distinguish
  the two metrics; the load-bearing reason is the **n=2** cell size, and "zero stance resistance" was corrected to
  "**insensitive** to the stance manipulation". Both independently recomputed on the real round sets, not asserted.
- **Round B verdict wording de-inflated** in `INDEPENDENT_REVERIFICATION_20260917B.md` and §12.5: round B is recorded as
  **major found → author-fixed → fix pending round C**, not "all three confirmed with minor issues".
- **Round C ran — but as THREE workflows on a pre-fix draft, and its first summary over-claimed (now corrected).** An
  earlier one-line tally — "4 lenses, 0 defects confirmed, 6 raised-and-refuted, closes the round-B self-tested-only
  residual" — was an **over-generalisation true only of the code-path red-team** and is retracted here and in the v2_1
  sidecar. What the journals actually show: (i) the round-B fail-closed **code** red-team raised 6 adversarial bypass
  attempts on RA-1/RA-3/RA-4 and **all 6 were refuted — the code held** (that is the only true sense of "0 confirmed, 6
  refuted"); (ii) the **sensitivity-analysis** re-derivation found **1 major + 2 minor in that first pass** (major: the
  perfect-correlation overclaim; minors: the BCa column labelled marginal not conjunctive, and an unused non-standard
  `wild_cluster_lb`) — all fixed in place; the **fresh** round-C later added a **3rd minor (BCa-1, the formula itself)**,
  so the cumulative sensitivity tally is **1 major + 3 minor** (see §12.7 and the C-08 bullet below); (iii) the **amendment/sidecar** verification found several **minors**
  (`per_category_floor: none` parsing as a truthy string, the stale `date`, the `consistent_but_wrong` edit, and the
  round_c citation itself over-claiming) — all now addressed. So that first round-C pass did **not** come back clean: it
  found one major and a set of minors, which were fixed. **Because those fixes changed the bytes** (the v2_1 yaml
  re-hashed `80a1953c…`→`e310efc5…`→`739e14fe…` across this session's edits, the sidecar re-bound each time), the first
  pass ran on a *superseded* draft and a **fresh round-C on the corrected state was owed before any signature** — it ran
  and is recorded in `reports/INDEPENDENT_REVERIFICATION_20260917C.md` (see §12.7). Round C closes the "self-tested
  only" residual for the **code and §4 arguments** (which survived adversarial re-derivation in both passes); it does
  **not** retroactively validate bytes edited after a pass — each fresh edit re-owes verification, which is why §12.7's
  own fixes are flagged lead-authored.
- **C-08 / C-07 pre-declared small-sample sensitivity analysis** produced **before any C output** (`reports/
  SMALL_SAMPLE_SENSITIVITY_20260917.md` + `analysis_small_sample_20260917.py`/.out; CPU-only, no model, no C data).
  It was **independently re-derived by an adversarial workflow** after the lead had already caught a sqrt(π) calibration
  bug; independent adversarial re-derivation (two passes) **caught 1 major + 3 minor, all fixed in place** (major:
  within-family rows were called "perfectly correlated (verified)" and the 4-row `3/4`-unreachable claim stated as
  structural — only gold/world/rule sharing is verified, outcome correlation is a DGP assumption, and `always_letter_A/B`
  already splits every swap family, so §2 now shows a correlated **and** an independent-rows regime and keeps only the
  DGP-free `(b)⇒(a)` theorem; minor: BCa column relabelled conjunctive; minor **BCa-1** found by the fresh round-C — the
  `bca_lb` formula was a non-standard variant `Phi(2·z0+…)`, now corrected to textbook BCa `Phi(z0+(z0+za)/(1−a(z0+za)))`
  with the `.out` regenerated byte-deterministically and the BCa numbers updated, the qualitative conclusion confirmed
  robust and no recommendation resting on BCa; minor: unused non-standard `wild_cluster_lb` removed since it was never
  run). The C-08 percentile calibration/power numbers and the C-07 exact probabilities were themselves re-derived
  independently and matched.
  Headings: C-08 — at the null the T gate's conjunctive rule fires **0.02–0.05** (percentile LB is *not* anti-conservative
  at 12 clusters) but power is only **≈0.37** at the floor rate and **BCa lowers it further**, so the gate supports a
  **screening/revision-protocol** decision, not a confirmatory one. C-07 — macro and per-category readings disagree for
  many near-threshold outcomes (`P(macro pass ∧ per-cat fail)` 0.2–0.6 across correlation regimes), and a 4-row cell is
  n=2 families whose `ceil(.75·4)=3` floor is unreachable (a 2-of-2 gate) only in the correlated regime; the choice must
  be pre-declared, not post-hoc.
- **Decision-ready amendment draft** `reports/PREREG_V2_1_AMENDMENT_DRAFT_20260917.md`: C-06 (adopt `{4,2,2,2,2}`
  pair-unit) and C-10 (fix the `*_max` integer direction; `0.60`/`0.15` byte-unchanged) are diff-ready; **C-07 (a)/(b),
  C-08 (percentile-vs-wild-cluster) and C-18 (i)/(ii) are left as approver ticks** — all three change verdicts and are
  not lead-committable (the sidecar pre-fills recommended defaults but `signature_requires` makes active confirmation
  mandatory; silence does not adopt them). **Nothing applied; PREREG v2 + sidecar byte-identical; C unfrozen; S blocked;
  no GPU authorized.** Next in the review's order: land the sensitivity re-verification, then the approver ticks
  C-07/C-08/C-18, then this draft becomes the signable `v2_1` + sidecar.

### 12.7 Fresh round-C on the corrected bytes — zero majors in code/integers/governance; one major in the record itself (2026-09-18, appended)

The fresh round-C the 2026-09-17 review required ran as **three independent read-only reviewers** (Statistics/Construct;
Governance/Code; Skeptical/Red-Team) on the corrected working tree. Full record:
**`reports/INDEPENDENT_REVERIFICATION_20260917C.md`**. Net: **`confirmed_with_minor_issues` ×2 + `material_defects_found`
×1, zero majors in the corrected code/integers/governance.**

- **Independently confirmed correct (re-derived, not accepted):** the two §4 argumentative corrections (pooling
  truth-table pass-cells exactly `{(9,2),(10,1),(10,2)}` — all `swap≥9`, so pooling never relaxes swap; semantic
  constants `10/10` swap + `2/2` stance, letter constants `0/10` + `2/2`); the sensitivity script byte-identical at fixed
  seed; exact binomial `0.0758`; the C-07 tables + `(b)⇒(a)` theorem under an independent `Fraction` enumeration; every
  v2_1 integer; `propose_round_families()` == the freeze draft (both rounds, disjoint, 16 reserve); thresholds `0.60`/`0.15`
  byte-identical to v2; NOT-APPROVED integrity + all hash bindings; **all fail-closed code held every attack** (budget-only
  13 cases, anchors 26, Level-B 22 incl. a symlink escape); suite `257/OK/skipped=1`; both B8-01 pins + locus digest
  recomputed identical.
- **One MAJOR, in the record not the science (D-C1):** the machine twin `CURRENT_STATE_20260916.json` had **not** been
  updated when the prose was de-inflated — it still labelled all three round-B reviewers `confirmed_with_minor_issues`
  and had no `round_C` entry, so a parse-only consumer got the over-closed picture. **Fixed** in the twin (`review_rounds`
  corrected + `round_C_prefix`/`round_C_fresh` + a `session_20260917_later` block).
- **Minors fixed:** **BCa-1** the `bca_lb` formula was a non-standard variant `Phi(2·z0+…)` — corrected to textbook BCa,
  `.out` regenerated, numbers updated, conclusion confirmed robust (no recommendation rests on BCa); **RC-C2** the yaml
  header/amendment undercounted the verdict-affecting choices as "two" (there are three: C-07/C-08/C-18) — fixed, yaml
  re-hashed `e310efc5…`→`739e14fe…`, sidecar re-bound; **D-C2** BCa severity aligned to "1 major + 3 minor" everywhere;
  **D-C3/RC-C1** the dangling `…C.md` pointer resolved by creating it; **RC-C4** the budget-only "only the gated path
  produces" comment softened (hand-forgery possible on CPU, traceable, not unforgeable); **D-C4/RC-C5** bare-word `none`
  → `null` in sidecar prose + the prospective-fixes snippet; **NULL-1/WORD-1** MC-noise + "not independent" clarifications.
- **Residual disclosed, not closed (RC-C3):** no code reads the approval sidecar; `make_audit_package_level_b.py` checks a
  human-transcribed `prereg_revision_approval_effective` boolean (its stale "PREREG v2" message fixed). The
  active-confirmation duty is enforced by the sidecar's own invalidation clause + human diligence until a **freeze-time
  validator** reads the sidecar directly — deferred to the freeze ticket, same consumer-boundary theme as D5.
- **Honest limit of this round:** the reviewers *found* these defects independently; the *remediation* is lead-authored
  and self-checked. The load-bearing items (§4 corrections, integers, code paths, hash bindings) were independently
  re-derived and need no further confirmation; only the freshly-edited prose/formula are lead-authored, and a round D
  would be owed before those are treated as independently confirmed.
- **Unchanged:** `phase0_construct_admission_met=false`; PREREG v2 + v2_1 `proposed_not_approved`/`effective=false`; C
  `candidate_draft_not_frozen`; S blocked; no GPU/model/S this session; the approver still must actively tick C-07/C-08/C-18.

### 12.8 PREREG v2.1 APPROVED by the human/root approver (2026-09-20) — protocol only; nothing else unblocked

The §12.7 line "the approver still must actively tick C-07/C-08/C-18" is **superseded**: on 2026-09-20 the human/root
approver approved Phase-0 revision **v2.1** and recorded the three verdict-affecting choices. Committed by the approver
as **`bdc17db`** ("Approve Phase 0 revision v2.1 protocol choices"); pushed earlier that session and verified by
`ls-remote` **while HEAD was still `bdc17db`** — the equality is scoped to that moment, and `origin/dev` has since
advanced (round-D SKP-3: a recorded hash equation is stale at the moment of its own commit — the RT-1 pattern the JSON
`sync_note` warns about; re-derive with `git rev-parse`/`ls-remote`). This addendum records it; the approved bytes are
**not** edited.

- **Choices (approver's, recorded in `approver_choice_record`):** **C-07 = (a)** macro ≥ 0.75 gates, per-category
  report-only with **no category-level pass claim**; **C-08 = (P)** family-clustered percentile one-sided 95 % LB,
  **screening / revision-protocol only, non-confirmatory**, power caveat retained; **C-18 = (i)** label-swap gated
  swap-only + `stance_consistency` reported **ungated**, with **(iv) frozen denominator mandatory** (invalid/missing
  stay in the denominator, never the numerator). The approver's stated rationale — verbatim in the approval message,
  recovered from the session transcript and verified word-for-word on 2026-09-21 (round-D SKP-2/GOV-4; quoted in full
  in §12.9) — is restrained and matches the sensitivity analysis: a macro gate can compensate a weak category (hence
  the explicit bar on category-level ability claims); at 12 families the C-08 risk is mainly **false negatives / low
  power**, not manufactured false positives; a hard gate on 2 stance pairs would amplify chance error into a
  zero-tolerance verdict; splitting swap from stance keeps label-map invariance and sycophancy-sensitivity from being
  blurred into one construct.
- **Verified by re-derivation this session (not taken on report):** sidecar `protocol_sha256`
  `7bbd58cae219508702de6293a99ffb8ee1aeb275d29f43aae83a1eaa7d4f1196` **== sha256 of the approved yaml bytes == the
  approver-stated value**; yaml + sidecar both `approved_data_after_amendment`, `freeze.effective=true`,
  `approval_record` present; the approved **gate body matches the recorded choices** (parse-confirmed:
  `per_category_floor=null` ⇒ (a); swap-only `pair_set` + `stance_consistency.min=null` + frozen `denominator_semantics`
  ⇒ (i)+(iv); percentile `c08_uncertainty_rule` ⇒ (P); pair-unit allocation ⇒ C-06; `integer_rule_min/max` ⇒ C-10);
  `PREREGISTRATION_PHASE0_REVISION_v2.yaml` + its sidecar **byte-unchanged**; suite **257 OK (skipped=1)**; B8-01
  artifacts unchanged. Among PREREG sidecars only v2_1 is `effective=true` (the T03 split-amendment `effective=true` is
  historical and git-clean) — no unrelated sidecar was flipped.
- **Authorization scope — PROTOCOL ONLY (the approver's own explicit limit, recorded in `approval_scope`):**
  `phase0_construct_admission_met=false`, `C_freeze_authorized=false`, `level_B_authorized=false`,
  `model_gpu_authorized=false`, `S_authorized=false`, `round1_authorized=false`. **Nothing is unblocked beyond the
  protocol text.** C remains `candidate_draft_not_frozen`; S remains blocked; no model/GPU/Round-1 is authorized.
- **Remaining prerequisites the approver carried forward (still required before any freeze or run):**
  1. **RC-C3 — mechanical sidecar validator (an explicit freeze-ticket prerequisite):** the freeze path must read the
     sidecar directly (status / `approval_record` / `approver_choice_record` non-null + `freeze.effective` +
     `protocol_sha256 == sha256(yaml)`) rather than trust the human-transcribed `prereg_revision_approval_effective`
     boolean in `make_audit_package_level_b.py`. This is the disclosed-not-closed residual from §12.7; the approver
     made it a hard prerequisite, so it must be implemented in the freeze ticket, not deferred again.
  2. **C freeze** additionally needs B9-03 human R1/R2 gold-audit sign-off (§G) + the frozen in-round files.
  3. **Round 1** additionally needs the batch-10 execution preconditions satisfied and recorded.
  4. **Any model/GPU run** needs its own §F-style ticket + live admission audit.
- **Known stale provenance in the approved bytes, NOT edited (erratum):** the approved yaml's header comment
  (lines ~10–16) still summarises round C as "1 major + 1 major_error" and predates the fresh round-C / BCa-1 fix; the
  authoritative **sensitivity-analysis** accounting is **1 major + 3 minor**, while the fresh round-C pass's own major
  (D-C1, the stale machine twin) and its remaining minors are itemised separately in
  `INDEPENDENT_REVERIFICATION_20260917C.md`'s defect table (round-D SKP-6: the two accountings must not be conflated;
  SKP-4: round-C's D-C2 "aligned everywhere" missed this header). Because the bytes are
  SHA-bound by the approval, editing even a comment would break the binding and require re-approval, so it is left
  unchanged and recorded here. A future **v2.1.1** may correct the comment under a fresh approval if the approver wants
  the header self-consistent; it is a narrative imprecision, not a protocol-semantics defect (the gate text is correct).
  Round-D discoverability hardening: errata ledger **E-7** (`DOCUMENTATION_DRIFT_ERRATA_20260916.md`) now carries the
  same erratum, per the over-claim skeptic's reasoned verdict that the disclosure is adequate and v2.1.1 is **not**
  required.

### 12.9 §12 round D (2026-09-21): round-C remediation + approval record independently re-verified — zero majors; 8 minors + 9 info found, all fixed or erratumized

**Mechanism.** The user authorized round D. Three fresh independent read-only reviewers (no shared notes; re-derive,
not read-the-conclusion; CPU-only, zero repo writes, no S, no GPU, no network; round-C report read last):
**Statistics/Formula**, **Governance/Twin-sync/Approval-record**, **Skeptical/Over-claim**. Scope: the lead-authored
remediation delta (`ac2d6d4`) + the approval-turn record (`479b6c9`); `bdc17db` (approver-authored approved bytes)
integrity-only. Git base HEAD `479b6c9` (each reviewer re-derived it). Full record:
**`INDEPENDENT_REVERIFICATION_20260921D.md`**.

**Verdicts: all three `confirmed_with_minor_issues`. Zero majors.**

**Independently confirmed (reviewer-re-derived; these items are no longer lead-attested):**

- **The BCa-1 fix is textbook-correct** — `bca_lb` verified line-by-line against Efron & Tibshirani (1993)
  eq. 14.10/14.15 (leave-one-**cluster**-out jackknife acceleration, one-sided `z_α=Φ⁻¹(0.05)` for a lower bound,
  `a==0` branch = bias-corrected percentile `Φ(2z0+za)` to 1 ulp). The statistics reviewer's own from-the-literature
  re-implementation (no repo code reused; RNG stream validated by reproducing all 36 non-BCa cells) reproduces
  **all 12 committed BCa cells** (incl. null 0.007/0.020, p=0.80 0.767/0.632). Script double-run byte-identical to
  the committed `.out` (sha `81e4b702…`, empty stderr). This discharges C.md's "remediation is lead-authored"
  honest-limit **for the formula and the numbers**.
- **The approval record is faithful** to the approver's message — recorded triply (yaml `approval_scope` + sidecar +
  both twins); every addition found is constraint-**tightening** only; all `*_authorized` parse **false**;
  gate body ↔ recorded choices match by parse; full hash chain v1→v2→v2.1 closes (incl. the `739e14fe` intermediate
  and the v1 `5afe02a5…`/`84aaffd7…` links); 13-sidecar sweep: nothing flipped since the initial commit.
- **Twin sync holds (the D-C1 lesson):** zero divergences and zero optimistic skew between md §12.5–§12.8 and the
  JSON; the machine-readable record is nowhere more optimistic than the prose.
- **No authorization creep, no silent scope change:** every file touched in `ac2d6d4` + `479b6c9` maps to the round-C
  defect table or the approval-recording duty; all 9 threshold decimals byte-identical v2↔v2.1; approved bytes
  git-clean; no test deleted; script diffs are comment/message-only; suite **257 OK (skipped=1)** re-run
  independently by two reviewers (plus the 258-vs-257 platform-skip reconciliation re-derived).
- **Round-B de-inflation and round-C story are clean:** no optimistic residue outside clearly-marked historical
  quotes; every path/hash/section reference in the delta resolves; no round-D pre-writing (every remediation mention
  carried the pending qualifier until this section).

**Defects found → disposition** (reviewer ID prefixes disambiguate the two colliding "D-D*" tables):

- **GOV-1 (minor)** `make_audit_package_level_b.py:11,:62` still said "PREREG v2 approval" (the RC-C3 message fix had
  landed only on the `:77` boolean gate; probe-confirmed the stale refusal text) — **FIXED**: both now read "an
  effective PREREG approval (v2 or its v2_1 amendment)". Behavior unchanged (both paths still fail closed).
- **GOV-2 (minor)** the approved yaml's stale header tally — already erratumized (§12.8 + JSON); round D verified the
  erratum's line refs/quotes/tally exact — **HARDENED** with errata-ledger entry **E-7** (skeptic's reasoned verdict:
  disclosure adequate, v2.1.1 **not** required).
- **GOV-3 (info)** README banner still listed the PREREG decision as pending — **FIXED** (banner now points to
  §12.1–§12.9 and states the protocol-only approval; body untouched, E-5 discipline).
- **GOV-4 (info)** §12.8's rationale attribution exceeded what repo content let a reviewer verify — **RESOLVED**: the
  full approval message was recovered from the session transcript; the four rationale clauses are **verbatim approver
  text** (quoted below); §12.8 now cites that provenance. The elision lived in the lead's working summary, not in the
  record.
- **SKP-1 (minor)** `PREREG_V2_1_AMENDMENT_DRAFT_20260917.md:116` kept the pre-BCa-1-fix digits "null 0.005–0.015",
  contradicting the same commit's corrected 0.007–0.020 (and the `ac2d6d4` commit message) — **FIXED**: inline
  round-D annotation (original preserved per §10) + errata **E-8**.
- **SKP-2 (minor)** = GOV-2's attribution-inflation risk on §12.8's rationale sentence — resolved identically
  (provenance citation; the attribution itself verified true).
- **SKP-3 (minor)** RT-1 recurrence: "origin/dev == local HEAD == bdc17db via ls-remote" was false at the moment of
  its own commit (`479b6c9`) — **FIXED**: claim scoped to its moment in md + JSON, with the re-derive instruction.
- **SKP-4 (minor)** C.md's D-C2 disposition said "aligned everywhere" but the v2_1 yaml header — listed in D-C2's own
  finding column — was missed by that alignment and is now SHA-frozen — **FIXED** by correcting clause (here + E-7);
  C.md itself is a historical record and stays unedited.
- **SKP-5 (info)** "an independent re-derivation confirmed" (C.md:31 / sensitivity §1.3) was unattributed at round-C
  time (the fixed `.out` was lead-regenerated after the reviewers finished) — **FIXED** in sensitivity §1.3, which now
  attributes the independent confirmation to round D's from-literature re-implementation; C.md stays unedited with the
  correction recorded here.
- **SKP-6 (info)** §12.8's "authoritative accounting is 1 major + 3 minor" could be misread as the whole round-C
  accounting (losing D-C1) — **FIXED** (scoped to the sensitivity accounting, md + JSON).
- **SKP-7 (info)** JSON `invariants_held_this_session` parenthetical omitted the historical T04/hook-gate
  `effective=true` entries that C.md's sweep names — **FIXED** (parenthetical aligned: T03/T04 entries from the
  initial commit, git-clean).
- **RD-1 (minor)** sensitivity NULL-1 caveat: "an MC=2000 re-run converges to ≈0.073" was not reproducible from the
  documented configuration — same-seed MC=2000 gives **0.067** (0.073 could only come from an undocumented variant
  stream) — **FIXED** (0.067 quoted, exact iid limit 0.0758 retained, "converges" withdrawn).
- **RD-2 (minor)** "The clustered 0.077 matches the exact value" used the wrong reference distribution: the clustered
  DGP is overdispersed (`pe=clip(0.5+0.15Z)`), its exact point-rule null is **≈0.0852** (reviewer's closed-form
  truncated-normal-moment + 12-fold-convolution computation, validated in the csd→0 limit; same-stream MC=2000
  corroboration 0.084), so 0.077 sits ~0.6 se below its own exact value — **FIXED** (caveat rewritten; the
  "not anti-conservative" conclusion unchanged: conjunctive clustered gate 0.050 at MC=400, 0.045 at MC=2000, ≤ nominal).
- **RD-3…RD-6 (info)** disclosed; the script and `.out` are deliberately **NOT** regenerated (byte-stability of the
  committed, independently-reproduced artifact outranks cosmetic alignment): (RD-3) the two compared estimators use
  quantile-index conventions one order statistic apart (`ceil(αB)−1` vs `floor(adj·B)`; flipped 1/400 gate decisions
  in two clustered cells at the 0.497/0.500 boundary); (RD-4) `z0` continuity correction, `adj` clamp, and the
  never-firing `denom==0` fallback (min |denom| observed 0.66/4800 iterations) are documented practical guards, so
  the accurate claim is "textbook formula + disclosed guards"; (RD-5) the BCa column draws a fresh bootstrap, so
  GATE(pct) and GATE(BCa) are unpaired per iteration; (RD-6) BCa-null MC noise — annotation added to §1.3.

**Approver rationale, verbatim** (recovered from the session transcript 2026-09-21; source of the GOV-4/SKP-2
resolution — the elision was in the lead's working summary, not in the approval message):

> 这组选择相对克制：
> - macro 门可能补偿某个弱类别，因此明确禁止类别级能力结论；
> - C-08 在 12 个 family 下主要风险是假阴性和功效不足，没有证据显示它会大量制造假阳性；
> - stance 只有 2 个 pair，设硬门会把偶然误差放大成零容忍判决；
> - swap 与 stance 分开避免把标签映射不变性和迎合敏感性混成一个构念。

**Honest limit of round D (the chain does not self-close).** The reviewers confirmed the **pre-fix** state of this
delta. The eight fixes above are again **lead-authored and self-checked**; per the skeptic's forward-looking note,
treating them as independently confirmed requires a round E or the approver's explicit sign-off. The load-bearing
items need nothing further: the BCa formula and all 12 cells, every hash binding, the twin sync, the approval
fidelity, and the absence of authorization creep were reviewer-re-derived, not read. Reviewers could not verify: the
live remote state (no network for two of them; corroborated by the local tracking ref), `bdc17db`'s approver
attribution from git metadata (shared git identity — attribution is process-level), and round-C's process claims
(independence of the three reviewers; only the record attests).

**Unchanged:** `phase0_construct_admission_met=false`; C `candidate_draft_not_frozen`; S blocked; no model/GPU/S/
Round-1 authorized or run; RC-C3's mechanical sidecar validator remains a freeze-ticket prerequisite (task #14); the
untracked 366KB transcript's disposition remains the user's.


## §12.10 — Round-D receipt, RC-C3 consumer validator, and C-08 calibration erratum (2026-09-21)

- **Round-D receipt:** root has signed off on the non-load-bearing Round-D repairs; no Round-E work was started.
- **RC-C3:** the Level-B consumer-side validator is implemented and passed the remote CPU suite (**265 tests, 1 skip**). It directly validates the approved v2.1 YAML/sidecar bytes, pinned hashes, and C-07(a)/C-08(P)/C-18(i)+(iv) choices. This closes the consumer validator item only; the real C freeze script, frozen C data, and independent R1/R2 human gold review/sign-off remain undone.
- **E-9:** the sensitivity report now corrects the over-strong inference that 0.045≤0.05 proves non-anti-conservatism; the approved YAML bytes remain unchanged and must be read with E-9.
- **Current gates:** `phase0_construct_admission_met=false`; C remains `candidate_draft_not_frozen`; S remains blocked; no GPU/model run occurred. The validator is not a completed C-freeze workflow or human gold audit.
