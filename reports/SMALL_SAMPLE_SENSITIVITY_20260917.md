# Small-sample sensitivity analysis for C-08 and C-07 (pre-declared, before any C output)

**Date:** 2026-09-17 · **Branch:** `dev` · **Git base:** HEAD `52d45e6` (re-derived with `git rev-parse`, per the §12.5 rule)
**Status:** **PROPOSED decision-support — NOT APPROVED, NOT EFFECTIVE, NOTHING APPLIED.** It edits no pending-approval
text; `PREREGISTRATION_PHASE0_REVISION_v2.yaml` and its sidecar are byte-unchanged. The **C-07/C-08 choice remains the
approver's** — this supplies the pre-declared analysis the 2026-09-17 review said must precede the choice.
**Scope / honesty:** CPU-only. **No model, no GPU, no C data run, no C output observed** — every C family is still
`candidate_draft_not_frozen`, and no C baseline has ever been run at any scale. Every number here is a property of a
**declared synthetic generative model plus exact arithmetic / Monte-Carlo**, and constrains the **rules**, never
MiniCPM5. Reproduce with:
`CUDA_VISIBLE_DEVICES='' PYTHONPATH=src .venv/bin/python reports/analysis_small_sample_20260917.py`
(the `…_20260917.out` file is that script's output; fixed seed `20260917`, B=1500 bootstrap × MC=400 datasets).

This exists because the 2026-09-17 review returned two things that must be settled **before** the C-06/C-07/C-10/C-18
protocol text is written, and must not be settled after a model result is seen (GOAL §6):
- **C-08** — "what admission judgement can a 12-family bootstrap threshold actually support?"
- **C-07** — "macro and per-category floors give different verdicts; the per-category cells hold only 2 families, so
  'stricter' is not by itself a reason to pick the per-category hard gate." Pick **one** rule, pre-declared.

---

## 1. C-08 — the T-gate family-clustered bootstrap at 12 clusters

**Rule tested** (`t_round_gate.gate_A`, unchanged): pass iff `model_rate − best_degenerate_rate ≥ 0.15` **AND** the
one-sided 95 % **percentile** lower bound of the difference — from a family-clustered bootstrap (10 000 resamples in
the protocol; 1 500 here for runtime, seed fixed, resample the 12 families with replacement, degenerate recomputed per
resample) — is `> 0`. At Round-1 gate A: 24 items = **12 families × 2 items**, best degenerate `always_write` = 12/24
= **0.50**, so the margin floor is `model_rate ≥ 0.65` → **≥ 16/24**.

DGP (declared): per-family success prob `= clip(p + cluster_sd·Z)`, `Z~N(0,1)`; `cluster_sd=0` is iid items, `0.15`
induces family correlation. Degenerate is deterministic 1/2 per family under balanced golds, so it resamples to
exactly 0.50 and the bootstrap spread is the model side's. Sanity: the point-rule null rejection at `p=0.50` measured
**0.055 (iid) / 0.077 (clustered)** matches the exact binomial `P(≥16/24 | p=0.5) = 0.0758`, confirming the harness.

**Gate pass-probability by true model rate `p`:**

| true `p` | P(point ≥ .65) | P(pct-LB5 > 0) *[marginal]* | **gate: point AND pct-LB5>0** | gate: point AND BCa-LB>0 |
|---|---|---|---|---|
| **0.50 = null (model ≡ degenerate)** | 0.055 / 0.077 | 0.035 / 0.055 | **0.020 / 0.050** | 0.007 / 0.020 |
| 0.65 (floor of what can pass) | 0.515 / 0.502 | 0.395 / 0.380 | **0.375 / 0.365** | 0.233 / 0.205 |
| 0.70 | 0.735 / 0.728 | 0.623 / 0.555 | **0.615 / 0.550** | 0.407 / 0.343 |
| 0.75 | 0.880 / 0.853 | 0.777 / 0.715 | **0.777 / 0.713** | 0.608 / 0.500 |
| 0.80 | 0.953 / 0.940 | 0.900 / 0.873 | **0.895 / 0.865** | 0.767 / 0.632 |

(left/right = iid / clustered; the last two columns are the **conjunctive** gate with the percentile vs BCa LB —
comparable to each other; only the marked column is a marginal LB-only rate. The BCa column is **textbook BCa**
(Efron & Tibshirani 1993 eq. 14.10, `Phi(z0 + (z0+za)/(1−a(z0+za)))`); round-C finding **BCa-1** caught that an
earlier draft computed a non-standard variant `Phi(2·z0 + …)` with an `a==0 → alpha` branch — the formula was fixed
and this table + the `.out` regenerated, so these are now standard-BCa numbers, reproducible byte-identically.)

**What it shows.**
1. **Type-I error is in the right neighbourhood, so the gate is not a broken test.** Under the null the conjunctive rule
   fires **0.020–0.050** — at or below the nominal 5 % one-sided rate, not inflated. The packet's stated worry ("the
   percentile bootstrap is statistically fragile at small cluster counts") is **real but bounded**: it does not
   manufacture false passes at the null. (Family correlation nudges the point rule up to 0.077, above nominal —
   clustering *is* the thing the cluster-bootstrap exists to handle, and here it roughly holds.) **MC-noise caveat
   (round-C NULL-1; corrected in round D, RD-1/RD-2):** at MC=400 the iid point-rule null estimate 0.055 is a noisy
   low draw — the exact **iid** population value is `P(Bin(24,0.5)≥16)=0.0758` and the MC se is ≈0.013, so 0.055 sits
   ~1.6 se low; a same-seed MC=2000 re-run of the committed script gives **0.067** (still ~1.5 se low — the "≈0.073 an
   MC=2000 re-run converges to" that an earlier draft of this caveat quoted came from an undocumented variant stream
   and is superseded, RD-1). The **clustered** regime's exact null is **not** `P(Bin(24,0.5)≥16)`: with
   `pe=clip(0.5+0.15Z)` the family scores are overdispersed, and an independent round-D computation (closed-form
   truncated-normal moments + 12-fold convolution, validated against the csd→0 limit; same-stream MC=2000
   corroboration **0.084**) gives **≈0.085**, so the measured 0.077 sits ~0.6 se below **its own** exact value — the
   earlier "the clustered 0.077 matches the exact value" compared against the wrong reference distribution (RD-2).
   The "not anti-conservative" conclusion holds either way (the conjunctive clustered gate is 0.050 at MC=400 and
   0.045 at MC=2000, still ≤ nominal); the low-MC figures should not be read as precise to the third decimal.
2. **Power is the binding constraint, not calibration.** A model that genuinely clears the floor sits at `p≈0.65`; the
   conjunctive gate admits it only **≈ 0.37** of the time, reaching ≈ 0.78 only by `p=0.75`. At 12 families the test
   **cannot separate "just clears the floor" from "clears it comfortably"** — the confidence band is wider than the
   effect the gate is meant to certify.
3. **BCa (the usual small-sample correction) makes it worse here, not better.** Textbook BCa's null rejection is
   **0.007–0.020** — it *under-rejects the null*, i.e. it over-corrects at `n=12` and throws away power the percentile
   rule had: at `p=0.80` BCa admits **0.767 (iid) / 0.632 (clustered)** vs the percentile rule's **0.895 / 0.865**.
   Adopting BCa "because small samples" would lower the pass rate for good models without buying calibration the
   percentile rule lacked. (These are now standard-BCa numbers per the BCa-1 formula fix. Attribution — round-D SKP-5:
   at round-C time the corrected bytes were lead-regenerated and self-checked; as of round D (2026-09-21) the
   statistics reviewer independently re-implemented textbook BCa from the literature (E&T 1993 eq. 14.10/14.15, no
   repo code reused) and reproduced **all 12 committed BCa cells** plus byte-identical determinism, so the qualitative
   conclusion — textbook BCa still under-rejects the null and still loses power to the percentile rule at `n=12` — is
   now independently confirmed. The BCa null cells carry their own MC noise, symmetric with the point rule's: the
   0.007 low end is 3/400 events (se≈0.004) and a same-stream MC=2000 re-run gives ≈**0.019 (iid) / 0.019
   (clustered)**, so neither BCa range should be read to the third decimal (RD-6). No recommendation rests on the
   exact digits.)
4. **Not tested here (do not read as endorsed):** the wild cluster bootstrap (the third option packet §B lists). It is
   the theory-preferred interval for few clusters, but implementing and simulating it correctly is its own CPU task;
   this analysis deliberately reports only what it actually ran.

**Answer to "what can the 12-family bootstrap support."** It can support a **revision-protocol / screening** decision
— *does this model clear the degenerate baseline by enough, with the direction not explainable by the clustering, to
justify a larger round* — which is exactly the role PREREG v2 already assigns it (a pass/fail to **proceed**, not a
finding). It **cannot** support a **confirmatory power claim** ("the model beats the baseline with 95 % confidence in
the population"): the point estimate against a hard floor at `n=12` clusters, with the family-dependent (not independent)
rows the C gate itself flags, does not carry that. The approver's realistic options, in the reviewer's words, are to
**pre-declare a small-sample-corrected interval** or **record the percentile interval is used with a stated power
caveat**; this analysis adds the empirical input that (a) percentile is not anti-conservative at the null here, and
(b) BCa specifically *loses* power at `n=12`, so "just switch to BCa" is not obviously the correction it sounds like.
**Recommendation (flagged, approver's call):** keep the percentile LB, but write the power caveat and the
screening-not-confirmatory framing into the gate text, and treat the wild-cluster interval as a separate pre-registered
option if the approver wants a corrected interval rather than a caveat. **No threshold value changes.**

---

## 2. C-07 — macro vs per-category floor on the implemented `{8,4,4,4,4}` cells

**Setup (exact enumeration; the correlation is an ASSUMPTION, not verified).** Families are single-gold with
**2 same-gold in-round rows**; what is *verified* (data_c/verifier, 40/40) is that a family's two rows share
**gold, world, rule, claim and evidence** and are **not independent** (as *samples* — this is structural sharing of the
generating world/gold/rule, NOT a verified claim about a model's outcome correlation, which §2 below treats as a DGP
assumption) — a whole-family miss costs both rows. What is
**not** verified (and cannot be, with no model ever run) is the *correlation of a real model's outcomes* within a
family. The project's own frozen `always_letter_A/B` degenerate already **splits every swap family** (1 correct / 1
wrong per family, i.e. 2/4 per category), so partial within-family correctness is design-anticipated, not excluded. C-07
is therefore reported under **two** regimes, and the strictness of reading (b) depends on which holds:
- **Regime C** — family fully correlated (the whole family is right or wrong): a 4-row cell scores only `{0,2,4}/4`.
- **Regime I** — rows independent: a 4-row cell is `Binomial(4,q)` and scores `{0,1,2,3,4}/4`.
Implemented round cells are **families `[4,2,2,2,2]` → rows `[8,4,4,4,4]`** (the 8-row rotating cell behaves the same
way, one coarser). Reading **(a)** = `macro ≥ 0.75` (compensatory); reading **(b)** = `every cell ≥ ceil(0.75·n)`
(≥ 3/4 in a 4-row cell, ≥ 6/8 in the 8-row cell).

**DGP-free theorem (holds under both regimes):** every cell ≥ its 0.75 floor ⇒ the macro (mean of cell rates, each
≥ 0.75) ≥ 0.75, so **(b) ⇒ (a)** and `P(b and ¬a) = 0` always. The disagreement is entirely one-directional.

**Pass-probability (exact binomial enumeration; regime C has `q`=P(whole family correct), regime I has `q`=P(single
row correct) — the two `q`s are on different scales, read within a column-pair not across regimes):**

| `q` | Regime C: P(a) | P(b) | P(a∧¬b) | Regime I: P(a) | P(b) | P(a∧¬b) |
|---|---|---|---|---|---|---|
| 0.75 | 0.596 | 0.074 | 0.522 | 0.570 | 0.202 | 0.369 |
| 0.80 | 0.743 | 0.137 | 0.606 | 0.775 | 0.359 | 0.416 |
| 0.85 | 0.869 | 0.243 | 0.626 | 0.922 | 0.563 | 0.359 |
| 0.90 | 0.954 | 0.408 | 0.546 | 0.987 | 0.776 | 0.211 |

`P(b∧¬a)=0` in every cell of both tables (the theorem).

**What it shows.**
1. **The two readings disagree often, and only one way.** `P(a∧¬b)` is **0.21–0.63** across both regimes — macro passes
   a configuration the per-category floor rejects in a large share of near-threshold outcomes. This is not a rounding
   quirk and it survives the correlation question entirely: whichever regime a real model is in, the choice of reading
   changes verdicts, so it **must be pre-declared** (GOAL §6).
2. **How strict (b) is depends on the correlation, and that is exactly the honest caveat.** In a **correlated** regime
   a 4-row cell = 2 families × 2 rows and scores only `{0,2,4}/4`, so `ceil(0.75·4)=3` is **unreachable** and the
   "≥ 3/4" floor there collapses to a **2-of-2 zero-tolerance** gate (both families perfect); the 8-row cell's `6/8`
   is "≥ 3 of 4 families". In an **independent-rows** regime `3/4` is reachable and (b) is a genuine 3-of-4 gate —
   visibly less brutal (higher `P(b)`), but the cell is still **n = 2 families**, so one family slipping still moves a
   4-row cell by 50 pp. Either way the reviewer's caution stands: these are tiny cells; "stricter" mostly means
   "more likely to fail on one unlucky family."
3. **Consequence for the choice.** (b) is the stricter reading and is the one that matches *why* the taxonomy pins 5
   **independent** categories (a control that passes overall while one category sits at chance cannot license reading
   results **in that category** — GOAL §5 baseline-competence prerequisite). But its honest description is regime-shaped
   — in a correlated regime "each category must get both its families right," not "75 % per category" — and any (b)
   text must carry the n=2-family granularity in `reported_alongside`.

**Answer to "pick one rule, pre-declared."** Both are defensible but they are *different gates*, and the analysis
quantifies the gap so the approver picks with eyes open **before** any C output. If the intent is "no category may be
at chance" (the §5 rationale), **(b) is the faithful reading**, and its text must say plainly that a 4-row cell is a
both-families-must-be-correct gate and report the n=2-family granularity. If the intent is "overall control competence
at 0.75 macro," **(a) is the faithful reading**, and its text must state that a single category can sit low and the gate
still pass, so per-category results are reported for diagnosis and a chance-level category is a **flag for the human
reviewer**, not a silent pass. **This packet recommends neither as settled** — it records the numbers and the exact
text for both (in `PREREG_V2_PROSPECTIVE_FIXES_20260917.md` §3) so the approver states one. What it does establish: the
choice **must be pre-declared now**, because `P(a∧¬b)` is 0.2–0.6 across the two correlation regimes — a large,
model-independent disagreement that cannot be settled after seeing which side a real model lands on (GOAL §6).

---

## 3. Boundaries (so this is not mistaken for closure)

- **This is analysis of rules under assumed DGPs, not of MiniCPM5.** It uses no model output and predicts no model
  result; the pass probabilities are functions of an *assumed* `p`/`q`, and no `p`/`q` has been observed or is claimed.
- **The analysis was lead-authored, then independently re-derived twice** (GOAL §12: an adversarial workflow on the
  first version, and a fresh round-C pass on the corrected bytes). Across both it caught **one major and three minor
  problems, all now fixed in place**:
  - **(major)** an earlier draft called within-family rows "perfectly correlated (verified)" and stated the 4-row `3/4`
    floor was unreachable as a *structural* fact — but only gold/world/rule sharing is verified, the *outcome*
    correlation is a DGP assumption, and the frozen `always_letter_A/B` degenerate itself splits every swap family, so
    §2 now reports **both** a correlated and an independent-rows regime and keeps only the `(b)⇒(a)` theorem as DGP-free.
  - **(minor)** the C-08 BCa column was the *conjunctive* gate but an earlier header implied *marginal* — relabelled.
  - **(minor, round-C BCa-1)** the `bca_lb` formula was a **non-standard variant** `Phi(2·z0 + (z0+za)/(1−a(z0+za)))`
    with an `a==0 → alpha` branch — neither BCa nor BC. Fixed to textbook BCa `Phi(z0 + (z0+za)/(1−a(z0+za)))` (whose
    `a→0` limit is the bias-corrected percentile `Phi(2·z0+za)`); the `.out` and the §1 table were regenerated, so the
    BCa numbers are now standard-BCa. The qualitative conclusion is unchanged and was independently confirmed robust
    (textbook BCa still under-rejects the null and still loses power to the percentile rule at `n=12`); **no
    recommendation rests on the BCa column** — the doc recommends the percentile LB and does not endorse BCa.
  - **(minor)** the script carried an unused, non-standard `wild_cluster_lb` the docstring implied had been run —
    removed (wild-cluster remains explicitly *not evaluated*).
  The C-08 percentile calibration/power numbers and the C-07 exact probabilities were **re-derived independently and
  matched** (the C-07 tables and the `(b)⇒(a)` theorem reproduce exactly under an independent `Fraction`-based
  enumeration; the script output is byte-identical across runs at the fixed seed); the lead had already caught and
  fixed a separate √π-calibration bug before the first run.
- **C-08 is about the T gate, not the C gate.** The C accuracy gate carries **no** bootstrap/CI rule at all (packet §2
  consequence 6); that a C pass is a point estimate at `n=2` families/category is stated there and unchanged here.
- **Nothing here approves or freezes anything.** `phase0_construct_admission_met=false`; PREREG v2 `proposed_not_approved`;
  C `candidate_draft_not_frozen`; S blocked; no GPU ticket authorized. The C-06/C-07/C-10/C-18 protocol text still
  awaits the approver's C-07 choice and C-08 disposition before it can be written as signature-ready.
