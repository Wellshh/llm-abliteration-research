# Independent Re-verification round B (§12) — fbb363c hardening, the D5 accessor, and the §B/§C prospective fixes

**Date:** 2026-09-17 · **Scope:** everything the lead committed or authored in this session's first phase — commit
`fbb363c` (D1–D4), the new `src/minicpm_research/phase0_anchors.py` + tests (D5 consumer gate, commit `8c229ca`), and
the documentation/packet layer of commit `a688149` (`CURRENT_STATE` §12 + JSON twin, README banner, errata E-6,
`PREREG_V2_PROSPECTIVE_FIXES_20260917.md`).
**Why:** GOAL §12 — the lead implemented all of it; round A reviewed the tree at `84f1952`, so the D1–D4 fixes and
everything after them had had no independent look. **Reviewers:** Reproducibility & Audit Reviewer; Construct/Data/
Statistics Researcher; Skeptical/Red-Team Scientist — three read-only agents, no shared notes, each told to re-derive
rather than read-the-conclusion, CPU-only, no repo writes, no S, no GPU.
**Method note:** all three ran during the same window in which the lead committed `8c229ca`/`a688149` and pushed; the
repro reviewer explicitly re-verified its artifact-hash and structure claims *after* those commits landed, so the
concurrency did not stale-date its findings.

## Verdicts (all three: `confirmed_with_minor_issues`)

- **Reproducibility & Audit Reviewer** — "Every load-bearing claim reproduced from raw bytes … None is a correctness
  error in what shipped, and the Addendum's own claims — including its 'honest limit' — are supported."
- **Construct/Data/Statistics Researcher** — confirmed the C-pool observations and the effective-threshold arithmetic
  by independent recomputation, and found **one major statistical defect in the lead's own proposed fix texts** (§D1
  below) plus a set of wording/numeric errors. This is the finding that mattered.
- **Skeptic / Red-Team** — no history rewriting found in any appended file; **no test anywhere pinned the B8-01
  artifact hashes** (its own proposed falsification test, now implemented); flagged status-inflation in key *names*
  rather than bodies, and a self-invalidating git-state claim in the record it was reviewing.

## Independently reproduced (selection; per-agent lists are in the team transcript)

- **No silent re-export:** `TOKEN_ANCHORS.json` = `ecdac639ab8a42aa92a5db9cd632df3a6d84e8d04f56da0c3c4562fe78174c91`,
  `ENVIRONMENT.json` = `5b8b5bf6cf96d68bc6c556b300dcdce09a5589db058389f81622a9e3400fd027`, both **byte-identical to
  their `bcfd237` blobs**; 24 anchors V8/T8/C8, S0 with `coverage.S.status=blocked`, 8 multi-token T / 16 single-token
  V/C, `P_decision == P_boundary` 24/24, the F-06 caveat present 24/24, lock binding == `MODEL_MANIFEST.json`.
- **D1** fail-closed at the function layer under 13 attack inputs (`'real'`, case/space variants, `True`, `None`, `1`,
  `''`, list); stamping correct for all three provenance classes; `--budget-only` refuses a harness profile without
  `--illustrative` and labels it correctly with it.
- **D2** proven by import-hook + subprocess-killer instrumentation: the cuda:0 ticket gate exits 2 **before** any
  `torch`/`transformers`/`pynvml` import and before any subprocess (zero `nvidia-smi` calls), and `require_admission`
  is substantively the resource gate (hostname, ≥60 s complete audit, ≥2 fresh samples, ≤32 GiB, reserve).
- **D3** 22-case synthetic battery: fabricated hash, missing file, `prereg_revision_approval_effective` false /
  absent / `'true'` / `1`, `data_sha256` as a bare string (the pre-fix bypass shape), plus all 13 pre-existing refusal
  paths; only honest manifests pass.
- **D4** `start_cache_length`/`end_cache_length` on every decode row with `end == start + steps`, `decode_rate_caveat`
  verbatim, `is_real_profile=false`, `random_tiny_llama_harness_control_not_MiniCPM5`; **`RESOURCE_PROFILE.json`
  exists nowhere in the tree** and every mention in `reports/` is a forward-looking gated request.
- **Suite** `Ran 241 / OK (skipped=1)` at the time of review, sole skip `test_resources.py:209` (`@skipIf(linux)`);
  historical definition counts per commit reproduce the decomposition (188/209/219/224/242 **definitions** vs 187/208/
  218/223/241 **run**, the constant 1 being the platform skip).
- **The D5 accessor works as claimed**: `single_token_decision_locus` raised for **8/8** T anchors naming the example
  and F-06, accepted 16/16 V/C; `first_generated_token_locus` returned `is_single_token_decision_locus=False` 24/24;
  loader refused unknown tokenarity, broken equality, stripped caveat, T-relabelled-single, bad schema, empty anchors.
  The reviewer **confirmed the disclosed bypass is real** (raw `anchors[i]["P_decision"]` → 516, no error), i.e. the
  Addendum's "honest limit" is accurate rather than aspirational.
- **C packet arithmetic, independently recomputed:** `build_c_pilot()` == on-disk pool; both round lists == the freeze
  draft, disjoint, 16 reserve; families single-gold 40/40; per-category pool balance 4/4; degenerate constants
  macro **0.500** on both actual round sets; 10 swap pairs → 9/10 = 90.0 %; 12 pooled → 11/12 = 91.7 %; option B →
  5/6 = 83.3 %; option C infeasible for family-level balance; C-10 direction confirmed with 0 code hits.
- **Append-only discipline:** the heartbeat log shows 918 insertions / 0 deletions, all external `autoplacer-RL`
  heartbeats; nothing in a CPU-only review touched it.

## Defects found → disposition

| id | by | sev | finding | disposition |
|---|---|---|---|---|
| **CS-1** | construct/stats | **major** | Both proposed C-18 texts fixed an *expected* pair count but left the **denominator output-dependent** (v2's `missing_or_invalid_side` excludes pairs from the denominator at run time), so a model that emits invalid output on the pairs it fails **lowers its own requirement** (10→9 needed, 8→7, 7→6). Inherited from v2, unfixed by any of the packet's options. | **FIXED.** Packet §4.1 adds text (iv): denominator **frozen at freeze time**, an invalid/missing side counts as NOT consistent and stays in the denominator, invalid side also counts as a semantic error — matching `t_round_gate`'s gold-frozen pattern and GOAL §6. |
| **CS-2** | construct/stats | minor | §6 claimed the adopted allocation "keeps **both** nominal floors exact" while its own table shows consistency at 9/10 = 90 % (+5 pp) — the very tightening used to disqualify option B. | **FIXED.** Reworded: accuracy floor exact in both cell sizes; consistency floor **90.0 %**, no allocation at these sizes hits exactly 85 %, and the approver should *state* the effective floor rather than let it emerge. |
| **CS-3** | construct/stats | minor | "a 1-family miss costs 12.5 pp in a 4-row cell and 6.25 pp in an 8-row cell" matches **no unit** at these denominators (a family = 2 same-gold rows). | **FIXED** with units labelled: whole-family miss = **50 pp** of a 4-row cell (10 pp macro) / **25 pp** of an 8-row cell (5 pp macro); single-row 25/12.5 pp. Same error also corrected in §7's first bullet. |
| **CS-4** | construct/stats | minor | §0 said the scheme "satisfies both properties §C says cannot coexist" — the scheme is explicitly **unequal** per category; it satisfies *size + balance* by dropping equal counts. | **FIXED.** Reworded, and the real trade-off ("round size vs equal counts", pair as the unit) stated. |
| **CS-5** | construct/stats | minor | `n_category` row membership is undefined in PREREG v2 **and** in both proposed C-07 texts; the table silently assumed `in_round_eligible` rows, and scoring discovery variants would change every integer. | **FIXED.** `denominator_rows` clause added to both texts (a) and (b), plus a new §2 consequence 5. |
| **CS-6** | construct/stats | minor | C-18 missed a third option (gate swap and stance pairs separately) and the packet did not say why it is bad. | **FIXED.** Enumerated and rejected with the counterexample: 2 stance pairs → `ceil(0.85·2)` = **2/2 zero-tolerance**, and stance pairs share gold *and* label map so a constant answerer is trivially 2/2 consistent — and pooling (ii) is *weakened* by them. |
| **CS-7** | construct/stats | info | "macro and micro differ" (should be *can* differ — proportional patterns still coincide); C-10 "passes nothing meaningful" understates a **full inversion**; "degenerate-proof" broader than the repo's own C-05 caveat. | **FIXED** in all three places ("can differ" with the 6/8,3/4,3/4,3/4,3/4 example; C-10 fails compliant models and passes a 100 % false-refuser; "constant-strategy-proof"). |
| **CS-8** | construct/stats | info | C accuracy floors count rows whose within-family pair is perfectly correlated → a 4-row cell is **n=2 families**, and `c_round_gate` has no CI/bootstrap rule at all (whereas `t_round_gate` has one that C-08 already flags). | **FIXED (disclosure).** New §2 consequence 6 + `reported_alongside` lines in both texts. Not "fixed" statistically — attaching an uncertainty rule to the C gate is a §B decision, recorded as such. |
| **CS-9** | construct/stats | info | §0 omitted **C-08**, which packet §B lists as a blocker the approver must resolve with §B. | **FIXED.** §0 now names C-08 (+C-09/C-11/C-12) as explicitly untouched and still open. |
| **RA-1** | repro/audit | minor | `profile_resources.py --budget-only` derived provenance from two **self-declared** profile fields; a hand-written `{"is_real_profile": true, "measurement_kind": "real_gpu_measurement"}` minted a `real_gpu_measurement_based` re-estimate with `is_real_reestimate=true` (reproduced, exit 0). Same class as D3, undisclosed. | **FIXED.** A real claim now additionally requires the structural markers only the gated cuda:0 path writes — non-empty `admission` + `budget_settlement` — and `model_manifest_sha256` **re-verified** against `--model-lock`; refuses with zero output otherwise, records `real_claim_basis` in the result. +3 tests (fabricated refusal incl. zero-output check; three missing-marker subtests; structurally-evidenced accept path). |
| **RA-2** | repro/audit | minor | `validate_anchor_disclosure` checks disclosure **consistency**, not locus truth: `'7' == 7`-style equality, missing keys → `KeyError`, non-dict → `AttributeError`, and — structurally — a mis-constructed multi-token **V** anchor can *never* fail, because the per-task map forces V to claim single-token. | **FIXED (types/exceptions) / DISCLOSED (truth).** `_position()` requires a real non-negative `int` (rejecting `bool` and `str`); all three P keys required; non-dict anchors now yield a documented violation/exception. Content-level tokenarity truth needs the locked tokenizer and is upstream (F-08) — stated in the module docstring and `validate_anchor_disclosure`, with the inverted-but-phrase-preserving reword named as an unfixed limit. +5 tests. |
| **RA-3** | repro/audit | minor | Loader enforced disclosure but not **coverage policy**: a smuggled 25th `task='S'` anchor loaded fine; `coverage.*.anchors` could lie. | **FIXED.** `load_anchor_package` now asserts per-task coverage counts match the anchors present and that S is `(status='blocked', anchors=0, actual=0)` via a single named `S_COVERAGE_POLICY` constant — so a future legitimate post-§E-step-9 re-export changes one greppable constant, never incidentally. +2 tests. |
| **RA-4** | repro/audit | minor | Level-B's D3 gate verified truth-of-listed-paths but not **relevance**: `ROOT / rel` happily verified `/etc/hostname`, and a manifest binding only `GOAL.md` (zero data files) passed. | **FIXED.** Absolute and `..` paths refused, resolved path must stay inside `ROOT`, and at least one bound path must be under `artifacts/data/`. +3 tests. Residual *disclosed* in the builder docstring: which specific data files a freeze must list remains the freeze record's declaration, not this builder's. |
| **RA-5** | repro/audit | info | `187 + 21 + 10 + 5 + 18 = 241` is exact against unittest's `Ran` counter, but static `def test_` counts give **242** (the always-skipped Linux test). | **RECORDED** in `CURRENT_STATE` §12.5 so the next agent reconciles 241-vs-242 without rediscovering it. No code change. |
| **RT-1** | skeptic | minor | The record's own git claims were **self-invalidating at their commit**: it said "HEAD `fbb363c`, dev == origin/dev" while the commit carrying that text moved dev past it. | **FIXED by append:** §12.5 sync note with the real sequence; `dev` now pushed and equal to `origin/dev`. Historical §12.1 untouched (§10). |
| **RT-2** | skeptic | minor | Status inflation in **key names**: `t05_requirement_now_enforced` + D5 filed under `closed_findings` + commit subject "D5 closed", while the adjacent `honest_limit` disclosed the bypass. | **FIXED.** Key value reworded to what the code does; §12.2 and the module docstring carry the same limit. D5 remains **deferred** in prose everywhere — the "closed" word now attaches only to the *consumer-boundary* work item, and says so. |
| **RT-3** | skeptic | minor | "**Both B8-01 artifact hashes are byte-unchanged**" — the record's strongest present-tense claim — appeared in **no test**; nothing pinned the hashes or the absolute locus values, so a semantic re-export would pass all 18 tests silently. | **FIXED — the reviewer's own falsification test, implemented.** `ProvenancePinTests` pins both sha256s **and** a digest over `(example_id, task, P_user, P_boundary, P_decision)` for all 24 anchors, with an explicit, loud **escape hatch** docstring: it is *expected* to fail when the §C/F-07 post-freeze C re-export runs, and may be updated only with the approving amendment + a new §12 record + every citing report updated. +2 tests. |
| **RT-4** | skeptic | info | **Nothing imports `phase0_anchors`**; `run_pilot.py` builds its own anchors, so "the API" is guidance + tests until T05 makes it mandatory. | **DISCLOSED**, not fixed. Stated verbatim in the module docstring ("Nothing imports this module yet") and in §12.2. Mechanical enforcement (CI grep banning raw `json.load` of `TOKEN_ANCHORS.json`) is deferred to the T05 ticket, where the rule belongs. |
| **RT-5** | skeptic | info | The JSON twin omitted the round-A **verdict strings** the markdown carried. | **FIXED** in §12.5's `addendum_20260917.review_rounds`. |
| **RT-6** | skeptic | info | Stray untracked 366 KB session transcript `handoff-recovered-2026-09-17.md`, referenced by nothing, in a repo whose §A hygiene decision is still open. | **SURFACED to the human** (not deleted, not committed). §A already carries the open gitignore decision; disposition is the owner's. |

## Post-fix state

- **Full CPU suite: 257 tests, OK (skipped=1)** = 241 + 10 (`test_phase0_anchors` 18→28) + 3 (Level-B 14→17) + 3
  (resource-profile 22→25). Zero regressions; `sha256sum` re-confirmed unchanged for both B8-01 artifacts.
- **Changed:** `src/minicpm_research/phase0_anchors.py`, `scripts/profile_resources.py`,
  `scripts/make_audit_package_level_b.py`, `tests/test_phase0_anchors.py`, `tests/test_audit_package_level_b.py`,
  `tests/test_resource_profile.py`, `reports/PREREG_V2_PROSPECTIVE_FIXES_20260917.md` (v2, with a §8 provenance
  section listing what the review changed and why), `reports/CURRENT_STATE_20260916.{md,json}` (§12.5 appended).
- **Unchanged, deliberately:** both B8-01 artifacts (and they are now pinned by tests), every pending-approval
  protocol text, every historical record/threshold/failure, the Level-A generator and package.
- **Still true after all of this:** `phase0_construct_admission_met=false`; PREREG v2 `proposed_not_approved`; C
  `candidate_draft_not_frozen`; S blocked, content untouched; no `RESOURCE_PROFILE.json`; **the post-gate GPU
  measurement path has still never executed** (code order + unit tests only). §B/§C/§D/§E/§F/§G all still need the
  human/root decisions; §B additionally still needs C-08 resolved.

## What this round did *not* achieve (so it is not mistaken for closure)

- The round-B fixes are themselves **lead-authored code**. They are unit-tested and were written against specific,
  reproduced reviewer findings, but no fourth agent has re-attacked them; RA-1/RA-3/RA-4 in particular are new
  fail-closed paths whose *tests* were written by the same author as the *code*. Treat as "defect addressed,
  verification pending round C" for anything load-bearing.
- `phase0_anchors` remains unconsumed (RT-4) and disclosure-level only (RA-2): it makes the default path refuse the
  wrong read; it cannot detect an inverted-but-phrase-preserving reword, a mis-constructed single-token V construct, or
  a raw `json.load` bypass.
- Every C number in the packet is a property of a deterministic generator plus integer arithmetic. **No C data has
  ever been run**, so nothing here constrains model behaviour; §4.1 in particular only guarantees that the model
  cannot shrink the bar it is measured against.
