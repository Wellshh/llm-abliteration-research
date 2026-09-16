"""Build the B9-01 C pilot candidate pool + manifest with proposed round lists.

CPU-only; no model, no GPU. Writes NEW files (refuses overwrite); pilot.jsonl
and all historical artifacts are never touched. C gates remain inert until
PREREGISTRATION_PHASE0_REVISION_v2 is approved and this data is frozen.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from minicpm_research.data_c import (SEED_DATE, build_c_pilot, project_degenerate_scores,
                                     propose_round_families, round_balance_attestation)
from minicpm_research.runs import file_hash
from minicpm_research.verifier import C_CATEGORIES, C_STANCE_CATEGORY, validate_dataset

OUT_DATA = ROOT / "artifacts/data/pilot_c_v2.jsonl"
OUT_MANIFEST = ROOT / "artifacts/data/pilot_c_v2.manifest.json"
V1_DATA = ROOT / "artifacts/data/pilot_c_v1.jsonl"
V1_MANIFEST = ROOT / "artifacts/data/pilot_c_v1.manifest.json"
EXISTING_PILOT = ROOT / "artifacts/data/pilot.jsonl"


def _write_atomic(path: Path, text: str) -> None:
    if path.exists():
        raise SystemExit(f"REFUSING to overwrite existing {path}")
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("x", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def main() -> int:
    examples = build_c_pilot()  # validate_dataset (independent gold re-derivation) runs inside
    lines = [json.dumps(example, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for example in examples]
    payload = "\n".join(lines) + "\n"

    # Coexistence: C candidates must validate together with the historical pilot pool
    # (disjoint family/world/example namespaces) WITHOUT modifying pilot.jsonl.
    existing = [json.loads(line) for line in EXISTING_PILOT.read_text(encoding="utf-8").splitlines() if line.strip()]
    combined = validate_dataset(existing + examples)
    overlap = {e["family_id"] for e in existing} & {e["family_id"] for e in examples}
    if overlap:
        raise SystemExit(f"family namespace overlap with historical pilot: {sorted(overlap)[:3]}")

    _write_atomic(OUT_DATA, payload)
    data_sha = file_hash(OUT_DATA)

    families = sorted({e["family_id"] for e in examples})
    fam_meta = {e["family_id"]: e for e in examples if e["variant_kind"] in ("primary_map_1", "stance_agree")}
    per_category = Counter(fam_meta[f]["category"] for f in families)
    gold_per_category = {c: dict(Counter(fam_meta[f]["gold"] for f in families if fam_meta[f]["category"] == c))
                         for c in sorted(C_CATEGORIES)}
    rule_per_category = {c: dict(Counter(fam_meta[f]["rule"] for f in families if fam_meta[f]["category"] == c))
                         for c in sorted(C_CATEGORIES)}
    stance_maps = dict(Counter(json.dumps(fam_meta[f]["label_map"], sort_keys=True)
                               for f in families if fam_meta[f]["category"] == C_STANCE_CATEGORY))
    kinds = Counter(e["variant_kind"] for e in examples)
    round_1, round_2, reserve = propose_round_families(examples, per_round=12)
    assert not (set(round_1) & set(round_2)) and len(round_1) == len(round_2) == 12 and len(reserve) == len(families) - 24
    for rounds in (round_1, round_2):
        cats = {fam_meta[f]["category"] for f in rounds}
        assert len(cats) == len(C_CATEGORIES), f"round must cover all five categories: {sorted(cats)}"
    balance_r1, balance_r2 = round_balance_attestation(examples, round_1), round_balance_attestation(examples, round_2)
    for balance in (balance_r1, balance_r2):
        for cat, att in balance.items():
            counts = sorted(att["family_gold_balance"].values())
            assert counts[0] >= 1 and counts == sorted(counts, reverse=True) and min(counts) >= 1, \
                f"per-round per-category gold must cover both sides: {cat} {att}"
    degen_r1 = project_degenerate_scores(examples, round_1)
    degen_r2 = project_degenerate_scores(examples, round_2)

    manifest: dict[str, Any] = {
        "schema": "c_pilot_candidate_manifest_v2",
        "ticket": "B9-01",
        "candidate_version": 2,
        "supersedes": {
            "data_file": "artifacts/data/pilot_c_v1.jsonl",
            "data_sha256": file_hash(V1_DATA) if V1_DATA.exists() else None,
            "manifest_file": "artifacts/data/pilot_c_v1.manifest.json",
            "manifest_sha256": file_hash(V1_MANIFEST) if V1_MANIFEST.exists() else None,
            "v1_retained_unmodified": True,
            "issues_record": "reports/B9_01_C_DATA_V1_REVIEW_FINDINGS.md",
            "fixed_in_v2": ["timetable deadline visible in statement (all surfaces)",
                             "stratified per-round rule x gold selection + rotating extra pair + analytic degenerate projections",
                             "family verifier enforces claim/evidence identity, kind-stance binding, message-field correspondence",
                             "stance discovery variants bound to first primary and inherit its stance"],
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "candidate_draft_not_frozen",
        "c_gate_status": "inert_until_PREREGISTRATION_PHASE0_REVISION_v2_approved_and_data_frozen",
        "seed": 20260915,
        "seed_date": SEED_DATE,
        "generator_module_sha256": {"data_c.py": file_hash(ROOT / "src/minicpm_research/data_c.py"),
                                     "verifier.py": file_hash(ROOT / "src/minicpm_research/verifier.py")},
        "data_file": str(OUT_DATA.relative_to(ROOT)),
        "data_sha256": data_sha,
        "rows": len(examples),
        "families": len(families),
        "families_per_category": dict(per_category),
        "gold_balance_per_category": gold_per_category,
        "rule_balance_per_category": rule_per_category,
        "stance_family_letter_map_balance": stance_maps,
        "variant_kind_counts": dict(kinds),
        "primary_variants_per_family": 2,
        "discovery_variants_round_eligible": False,
        "independent_verification": "validate_dataset ran inside build_c_pilot (every gold re-derived by verifier logic separate from the generator; family content identity, kind-stance binding and message-field correspondence enforced) and again over the combined V/T+C pool",
        "combined_with_historical_pilot": combined,
        "historical_pilot_jsonl_modified": False,
        "historical_pilot_sha256": file_hash(EXISTING_PILOT),
        "family_namespace_disjoint_from_historical": True,
        "formal_test_status": "sealed_nonexistent_no_formal_split_generated",
        "human_gold_audit": "pending_two_independent_reviewers_B9_03",
        "proposed_round_1_families": round_1,
        "proposed_round_2_families": round_2,
        "proposed_reserve_families": reserve,
        "round_selection_rule": ("per round: one stratified pair (2 families; TRUE-side + FALSE-side gold; rule r0+r1; "
                                  "stance pairs share one letter map) from EVERY category in sorted order, plus one extra "
                                  "pair from the rotating category (round index over sorted categories); round 2 continues "
                                  "consuming the per-category pair queues; remainder is reserve"),
        "round_balance_attestation": {"round_1": balance_r1, "round_2": balance_r2},
        "degenerate_score_projections": {"round_1": degen_r1, "round_2": degen_r2,
                                          "note": "analytic, no model involved; with stratified selection every frozen degenerate strategy scores 0.5 macro (user-follower 0.5 within the stance category), so constant answers cannot pass the >=0.75 gate"},
        "stance_neutral_category_limitation": ("stance_neutral_objective families use independent random worlds; they are an "
                                                "unpaired reference for objective-verdict ability, NOT a paired control isolating "
                                                "the effect of inserting a user stance (paired contrast = agree vs oppose within "
                                                "user_stance families)"),
        "leakage_check_scope": ("automated check verifies the gold label string is not printed in the user message; this is a "
                                 "direct-print check only, NOT a full semantic non-leakage proof"),
        "safety_note": "all content is benign synthetic record-keeping verdicts; no safety-relevant or dangerous content is generated by this ticket (S data remains blocked under B9-02)",
    }
    _write_atomic(OUT_MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "candidate_draft_written", "rows": len(examples), "families": len(families),
                      "data_sha256": data_sha, "round_1": len(round_1), "round_2": len(round_2),
                      "reserve": len(reserve), "combined_validation": combined["gold_verified"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
