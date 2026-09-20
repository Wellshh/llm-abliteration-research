"""
Small-sample sensitivity analysis for the §B/§C decision queue (C-08, C-07).
CPU-only, deterministic, NO model and NO C output used — this characterises the
*rules*, not any model (GOAL §6: declared generative assumptions, fixed seed).

Two declared synthetic regimes are reported for each question; neither is
presented as MiniCPM5's truth. Run:
  CUDA_VISIBLE_DEVICES='' PYTHONPATH=src .venv/bin/python \
    reports/analysis_small_sample_20260917.py

Round-C correction note (independent re-derivation, 2026-09-17): an earlier
version asserted within-family rows are "perfectly correlated" as if verified.
Only gold/world/rule/claim/evidence sharing is verified (data_c/verifier); the
CORRELATION of model outcomes within a family is a DGP ASSUMPTION, and the
frozen always_letter_A/B degenerate itself splits every swap family (1 correct /
1 wrong), so partial within-family correctness is a design-anticipated regime.
C-07 is therefore reported under BOTH a fully-correlated-family regime and an
independent-rows regime, and the only DGP-free claim is labelled as a theorem.
"""
import math
import random
from itertools import product

SEED = 20260917


# --------------------------------------------------------------------------
# Part A — C-08: T-gate family-clustered bootstrap on 12 clusters.
# Rule under test (PREREG v2 t_round_gate.gate_A): pass iff
#   (model_rate - best_degenerate_rate) >= 0.15   AND
#   one-sided 95% *percentile* lower bound of the difference (family-clustered
#   bootstrap, resample the 12 families with replacement, degenerate recomputed
#   per resample) > 0.
# DGP: 12 families x 2 items (gate A: 24 items); per-family success prob
# pe = clip(p_mean + cluster_sd*Z), Z~N(0,1); cluster_sd=0 is iid items.
# Degenerate always_write = 1/2 in every family (balanced golds) so it resamples
# to exactly 0.50 and the bootstrap spread is the model side's. We report the
# CONJUNCTIVE rule (point AND LB>0), which is the actual gate, plus each conjunct
# alone, and substitute BCa for the percentile LB to test the small-sample fix.
# (The wild-cluster bootstrap that packet §B also lists is NOT implemented here;
# it is a separate pre-registered option and must not be read as evaluated.)
# --------------------------------------------------------------------------

def simulate_gate_a(rng, p_mean, cluster_sd, n_fam=12, items_per_fam=2,
                    deg_per_fam=1):
    model = []
    for _ in range(n_fam):
        pe = min(0.999, max(0.001, p_mean + cluster_sd * rng.gauss(0, 1)))
        model.append(sum(1 for _ in range(items_per_fam) if rng.random() < pe))
    deg = [deg_per_fam] * n_fam
    return model, deg, items_per_fam


def _rate_diff(model, deg, nif, idx):
    tot = nif * len(idx)
    return (sum(model[i] for i in idx) - sum(deg[i] for i in idx)) / tot


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p):
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def boot_diffs(model, deg, nif, n_fam, B, rng):
    return sorted(_rate_diff(model, deg, nif, [rng.randrange(n_fam) for _ in range(n_fam)])
                  for _ in range(B))


def percentile_lb(diffs, alpha=0.05):
    B = len(diffs)
    return diffs[max(0, int(math.ceil(alpha * B)) - 1)]


def bca_lb(model, deg, nif, n_fam, B, rng, alpha=0.05):
    diffs = boot_diffs(model, deg, nif, n_fam, B, rng)
    theta_hat = _rate_diff(model, deg, nif, list(range(n_fam)))
    jk = []
    for i in range(n_fam):
        idx = [j for j in range(n_fam) if j != i]
        jk.append(_rate_diff(model, deg, nif, idx))
    jbar = sum(jk) / len(jk)
    num = sum((jbar - v) ** 3 for v in jk)
    den = 6.0 * (sum((jbar - v) ** 2 for v in jk) ** 1.5)
    a = num / den if den else 0.0
    k = sum(1 for d in diffs if d < theta_hat)
    z0 = _norm_ppf(max(0.5, k + 0.5) / (B + 1))
    za = _norm_ppf(alpha)
    # Standard BCa (Efron & Tibshirani 1993, eq. 14.10) one-sided lower-bound level:
    #   adj = Phi( z0 + (z0 + za) / (1 - a*(z0 + za)) )
    # whose a->0 limit is the bias-corrected percentile Phi(2*z0 + za). (round-C BCa-1:
    # the prior code used a leading 2*z0 and returned `alpha` when a==0, which is neither
    # BCa nor BC; it characterised a non-standard variant. Fixed to the textbook form.)
    denom = 1.0 - a * (z0 + za)
    adj = _norm_cdf(z0 + (z0 + za) / denom) if denom != 0.0 else _norm_cdf(2 * z0 + za)
    adj = min(max(adj, 1.0 / B), 1 - 1.0 / B)
    return diffs[min(B - 1, max(0, int(adj * B)))]


def c08():
    print("=" * 80)
    print("PART A — C-08: T-gate family-clustered bootstrap, 12 clusters, 2 items/fam")
    print("GATE (the real rule) = point>=.15 margin AND one-sided-95% LB>0. Columns are")
    print("CONJUNCTIVE unless marked marginal. LB5 = one-sided 95% lower bound at p=0.05.")
    print("DGP: per-family success prob = clip(p + cluster_sd*Z); degenerate = 1/2/family.")
    print("=" * 80)
    B = 1500
    MC = 400
    for csd, lab in ((0.0, "iid items (cluster_sd=0)"), (0.15, "clustered (cluster_sd=0.15)")):
        print(f"\n--- {lab} ---")
        print(f"{'true p':>7} | {'P(point)':>8} | {'P(pctLB5>0)*marg':>16} | "
              f"{'GATE(pct)':>9} | {'GATE(BCa)':>9}")
        for p_mean in (0.50, 0.60, 0.65, 0.70, 0.75, 0.80):
            rng = random.Random(f"{SEED}-A-{csd}-{p_mean}")
            n_point = n_marg = n_pct = n_bca = 0
            for _ in range(MC):
                m, d, nif = simulate_gate_a(rng, p_mean, csd)
                point = _rate_diff(m, d, nif, list(range(12))) >= 0.15 - 1e-12
                pct_lb = percentile_lb(boot_diffs(m, d, nif, 12, B, rng))
                bca = bca_lb(m, d, nif, 12, B, rng)
                if point:
                    n_point += 1
                if pct_lb > 0:
                    n_marg += 1                       # marginal percentile LB (diagnostic)
                if point and pct_lb > 0:
                    n_pct += 1                        # the actual gate, percentile
                if point and bca > 0:
                    n_bca += 1                        # the actual gate, BCa substituted
            tag = " <== NULL (model==degenerate; a 5% one-sided test rejects ~0.05)" if abs(p_mean - 0.50) < 1e-9 else ""
            print(f"{p_mean:7.2f} | {n_point/MC:8.3f} | {n_marg/MC:16.3f} | "
                  f"{n_pct/MC:9.3f} | {n_bca/MC:9.3f}{tag}")
    print("\nReading: at the NULL the conjunctive gate fires ~0.02-0.05 -> percentile LB is NOT")
    print("anti-conservative at 12 clusters; power at p=0.65-0.75 is only ~0.37-0.78 (screening,")
    print("not confirmatory); textbook BCa (round-C BCa-1 fix) LOWERS both further (null 0.007-0.020,")
    print("p=0.80 power 0.632-0.767 vs percentile 0.865-0.895) -> it over-corrects at n=12.")


# --------------------------------------------------------------------------
# Part B — C-07: exact finite-population behaviour of the two C-gate readings on
# the implemented cells. Cells: families [4,2,2,2,2] -> rows [8,4,4,4,4].
# Family = single-gold; its 2 in-round rows SHARE gold/world/rule (verified) but
# their outcome correlation is NOT verified, so BOTH regimes are reported:
#   REGIME C (fully correlated family): a family is all-correct or all-wrong ->
#     a 4-row cell takes only {0,2,4}/4, so ceil(.75*4)=3 is unreachable and the
#     (b) floor there collapses to "both families correct" (a 2/2 gate).
#   REGIME I (independent rows): a 4-row cell is Binomial(4,q), 3/4 reachable,
#     (b) is a genuine 3-of-4 gate -> far more permissive than regime C.
# DGP-FREE THEOREM (both regimes): every cell >= its ceil(.75 n) floor => macro
#   (mean of cell rates, each >= .75) >= .75, so (b) => (a); i.e. P(b and not a)=0.
# --------------------------------------------------------------------------

CELLS = [(4, 8), (2, 4), (2, 4), (2, 4), (2, 4)]  # (families, rows)


def c07_regime(name, correlated, q_label):
    """Enumerate per-cell score DIST (correct ROWS), then combine.

    correlated=True: the family is the unit; correct_families ~ Binomial(nf, q)
      and rows_correct = 2*families, so a 4-row cell scores only {0,2,4}/4.
      Here q is the probability a WHOLE family is answered correctly.
    correlated=False: rows independent; rows_correct ~ Binomial(nrows, q).
      Here q is the probability a single ROW is correct.
    The cell RATE and the (b) FLOOR always use ROW counts (nrows), for both.
    """
    print(f"\n--- REGIME {name}  ({q_label}) ---")
    print(f"{'q':>4} | {'P(a) macro>=.75':>15} | {'P(b) per-category':>17} | "
          f"{'P(a and ~b)':>11} | {'P(b and ~a)':>11}")
    for q in (0.75, 0.80, 0.85, 0.90):
        dists = []
        for nf, nrows in CELLS:
            d = {}
            if correlated:
                for k in range(nf + 1):        # k = correct families
                    d[2 * k] = math.comb(nf, k) * (q ** k) * ((1 - q) ** (nf - k))
            else:
                for r in range(nrows + 1):     # r = correct rows
                    d[r] = math.comb(nrows, r) * (q ** r) * ((1 - q) ** (nrows - r))
            dists.append(d)
        pa = pb = pandnb = pbandna = 0.0
        for combo in product(*[sorted(d) for d in dists]):
            probs = 1.0
            for sc, d in zip(combo, dists):
                probs *= d[sc]
            rates = [sc / nrows for sc, (_, nrows) in zip(combo, CELLS)]
            macro = sum(rates) / len(rates)
            a_ok = macro >= 0.75 - 1e-12
            b_ok = all(sc >= math.ceil(0.75 * nrows) - 1e-12
                       for sc, (_, nrows) in zip(combo, CELLS))
            pa += probs * a_ok
            pb += probs * b_ok
            pandnb += probs * (a_ok and not b_ok)
            pbandna += probs * (b_ok and not a_ok)
        print(f"{q:4.2f} | {pa:15.3f} | {pb:17.3f} | {pandnb:11.3f} | {pbandna:11.3f}")


def c07():
    print("\n" + "=" * 80)
    print("PART B — C-07: macro vs per-category floor, exact, cells rows=[8,4,4,4,4]")
    print("reading (a)=macro>=.75; (b)=every cell>=ceil(.75*nrows) (3/4 in a 4-row")
    print("cell, 6/8 in the 8-row cell). Cell RATE and (b) FLOOR use ROW counts.")
    print("DGP-FREE THEOREM: (b) => (a), so P(b and not a)=0 under BOTH regimes.")
    print("=" * 80)
    c07_regime("C (family fully correlated)", True, "q = P(whole family correct)")
    c07_regime("I (rows independent)", False, "q = P(single row correct)")
    print("\nReachability differs by regime, NOT by arithmetic:")
    print("  Regime C: 4-row cell scores only {0,2,4}/4 -> 3/4 UNREACHABLE -> (b) floor there")
    print("            == both-families-correct (a 2/2 gate). 8-row cell {0,2,4,6,8}/8 -> 6/8")
    print("            == '>=3 of 4 families'.")
    print("  Regime I: 4-row cell scores {0,1,2,3,4}/4 -> 3/4 REACHABLE -> (b) is a genuine")
    print("            3-of-4 gate (much more permissive; see higher P(b) above).")
    print("  Within-family OUTCOME correlation is an assumption (never observed: no model has")
    print("  run C); always_letter_A/B already splits every swap family (1/2), so partial")
    print("  correlation is real. Read the (b) strictness as regime-dependent, n=2 families.")


if __name__ == "__main__":
    c08()
    c07()
    print("\nDone. Analysis of the RULES under declared synthetic models. NO model output;")
    print("NO claim about MiniCPM5 behaviour; no p/q value is asserted as observed.")
