# Independent Re-verification (§12) — B8-01 v2 / B8-02 / Level-B builder

**Date:** 2026-09-17 · **Scope:** the lead's own committed work at HEAD `84f1952` (bcfd237 B8-01 v2, 8ac8c61 B8-02, 84f1952 Level-B).
**Why:** GOAL §12 — "No important positive claim may depend solely on the agent who implemented the relevant code." The lead implemented all three; two independent read-only reviewers re-derived/attacked them.
**Reviewers:** Reproducibility & Audit Reviewer; Skeptical/Red-Team Scientist.

## Verdicts

- **Reproducibility & Audit Reviewer: `confirmed_sound`.** "Every lead claim … reproduced exactly under independent recomputation … No material defect, no overclaim by the lead."
- **Skeptical/Red-Team Scientist: `confirmed_with_minor_issues`.** "Every load-bearing claim independently reproduced under attack … The five defects … are real but are defense-in-depth and disclosure gaps, not correctness errors in what shipped."

## Independently reproduced (selection; full lists in the team transcript)

- B8-01 artifact sha256 `ecdac639ab8a42aa…` / `5b8b5bf6cf96d68b…` match, **and `git show bcfd237:<path>` blobs are identical** (committed == working tree).
- **All 24 anchors re-derived byte-identically** by the reviewer's OWN code (locked tokenizer, CPU, `local_files_only`): ids/positions/replay/arity/tools-digests/label-contexts/per-anchor lock-binding — "field diffs: NONE" for 24/24. Position invariants + decode-replay all pass (reviewer's own check, not the script's).
- All 7 B8-01 fixes present in the artifacts (F-03 driver `550.54.14`/`12.4` re-parsed from the cited historical audit; F-B8-LOCK-02 full tokenizer binding, 0 stale `tokenizer_sha256`; F-06 T `decision_tokenarity=multi_token_native_tool_call`; F-07 C `provisional_…`; F-08/F-09/F-11 notes). S fail-closed (0 anchors, blocked); `gpu_execution_in_this_export=false`. The bcfd237 diff touches **no** anchor-selection or invariant logic.
- B8-02 budget math **hand-recomputed** (10.4 / 104 / 704; charged excludes and occupancy includes the 60s audit, RES-04); prefill/decode timed in **separate** loops with `cuda.synchronize` brackets and the ref_L prefill **outside** the decode timed region (the "prefill contaminates decode" hypothesis is **false**); allocator peak via `torch.cuda.max_memory_*` (RES-05).
- All 6 CLI gates exit 2 with **zero files written**; the cuda:0 ticket/lock gate fires in **0.059s before any torch import or admission** (verified by code order + import audit: no top-level torch import). Harness artifact honestly labelled (`is_real_profile=false`, 22,688-param `LlamaForCausalLM`); **no real `RESOURCE_PROFILE.json` exists anywhere**.
- Level-A `make_audit_packages.py` **byte-identical** to the committed `gold_audit_v2` manifest binding (`c7c1a481…`); untouched by bcfd237/8ac8c61/84f1952.
- Level-B: all 8 fail-closed refusals + refuse-overwrite reproduced; blinding single-sourced from Level A (verbatim-identical check); acceptance flags hardcode `human_signoff_complete=false`, `unlocks_runs=false`; no downstream consumer could unlock a run from a Level-B package.
- Full suite **218 OK (skipped=1)**, decomposing exactly 187 + 21 + 10.

## Defects found → disposition

| id | sev | finding | disposition |
|---|---|---|---|
| **D1** | minor | `reestimate_phase_budgets` took raw rates with no machine-readable provenance; a caller bypassing the CLI could mint a real-looking §14 estimate from cpu/illustratory rates ("toy masquerading as real", enforced by convention not code). | **FIXED.** Added a **required** `rate_provenance` enum (`real_gpu_measurement`/`cpu_harness_validation`/`illustrative`); output now stamps `rate_provenance` + `reestimate_kind` + `is_real_reestimate`; only `real_gpu_measurement` may be labelled real. CLI `_budget_only` passes it. New test `test_rate_provenance_required_and_stamped`. |
| **D2** | minor | `--execution-ticket` accepted any non-empty string; docstrings/help said "approved-id"/"GATED", implying validation that doesn't exist (the real resource gate is `require_admission`). | **FIXED (honest relabel).** Help/error text now state it is an **intent flag**, not validated against an approval; `require_admission` is the resource gate and the §F approval process is the authorization gate. (Validating against an approval sidecar is deferred until a B8-02 approval artifact exists.) |
| **D3** | minor | Level-B `validate_frozen_manifest` was **presence-based**: never verified `data_sha256` against on-disk files, never enforced `prereg_revision_approval_effective` — so a self-declared "frozen" manifest with fabricated hashes passed (the lead's own fixture used `"aa"*32`). | **FIXED (truth-based).** Now verifies every `data_sha256` entry against the on-disk file (`file_hash`, refuse on mismatch **or** missing file) and **requires** `prereg_revision_approval_effective is True`. Fixture updated to use real pilot hashes; +4 refusal tests (mismatch / missing file / prereg false / prereg absent). |
| **D4** | minor | Decode rows omitted the start cache length; a single `decode_forward_per_s_median` is applied uniformly regardless of context, so long-context decode is costed optimistically. | **FIXED.** Each decode row now records `start_cache_length` (=ref_L) + `end_cache_length`; profile carries a `decode_rate_caveat` (context-specific; uniform application is optimistic). Harness artifact regenerated. |
| **D5** | minor | `P_decision==P_boundary` for T numerically asserts a single decision locus that plan §6.1 says does not exist for multi-token native tool calls; the invariant enforces the equality for all tasks. | **DEFERRED (accepted minor).** Already mitigated by the co-located `decision_tokenarity` field + `position_definitions.P_decision` text (added in B8-01 v2 for F-06); **both reviewers rated the disclosure adequate for careful consumers.** A machine-readable `p_decision_is_single_locus` flag would force a 3rd B8-01 re-export/re-commit/re-push for a hypothetical future consumer. **Action carried forward:** the T05 probing/activation-extraction implementer MUST read `decision_tokenarity` and treat T `P_decision` as a first-generated-token locus, not a single-token decision locus. TOKEN_ANCHORS.json hashes are therefore **unchanged** (`ecdac639…`/`5b8b5bf6…`). |

## Info-level observations (no action required)

- Decode timed region includes per-step host-side `torch.randint` + growing `torch.cat` mask (direction is **conservative** — understates decode forward/s → over-estimates budgets). Optional: pre-generate outside the timed region before the real gated cuda:0 run.
- Level-B `verify_blinding` duplicates Level-A's inline check body (only constants are imported). Acceptable: Level A must stay byte-frozen, and `test_blinding_identical_to_level_a` pins parity.
- Blinded items' `answer_space` enumerations necessarily contain the gold string as one of several options (e.g. "TRUE | FALSE …"); this is **not** a leak (nothing marks which is gold) and is identical to Level A — exclude `answer_space` from naive automated gold-leak checks.
- Environment trap (not repo code): a stray `/data/root/tmp/inspect.py` shadows stdlib `inspect` for scripts run from that directory.
- `autoplacer-RL` (pid 3772767) holds the GPU3 reservation (pre-existing, untouched).

## Post-fix state

- **Full suite: 223 tests, OK (skipped=1)** = 218 + 1 (D1 provenance) + 4 (D3 refusals).
- Changed: `src/minicpm_research/resource_profile.py`, `scripts/profile_resources.py`, `scripts/make_audit_package_level_b.py`, `tests/test_resource_profile.py`, `tests/test_audit_package_level_b.py`, regenerated `artifacts/setup/RESOURCE_PROFILE_HARNESS_VALIDATION.json`.
- **Unchanged:** `scripts/export_phase0_artifacts.py`, `artifacts/setup/TOKEN_ANCHORS.json` (`ecdac639…`), `artifacts/setup/ENVIRONMENT.json` (`5b8b5bf6…`) — D5 deferred, no B8-01 re-export.
- **Caveat scoped honestly (both reviewers):** the post-gate GPU measurement path has never executed; it is verified by code order + unit tests only. The real `RESOURCE_PROFILE.json` + §14 re-estimate remain gated behind the §F ticket.
