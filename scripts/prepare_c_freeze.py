"""C-freeze PREPARATION entry (approver-issued freeze-prep ticket, 2026-09-21).

CPU-only. This script has EXACTLY ONE output mode: an auditable freeze-record
DRAFT. It contains **no code path that marks anything frozen** — it never writes
`freeze_status='frozen'`, never emits the `round_in_manifest_frozen_v1` schema,
and never modifies data. Per the approver's ticket: "此步不把任何数据标为
frozen". The freeze EXECUTOR (which would emit the real frozen in-round
manifest) is deliberately NOT part of this script; it will be assembled, with
the exact files/hashes/command, into the execution package for approver
approval (task #19) and may run only after that approval.

What the draft binds (all recomputed live, all fail-closed):
  1. the approved PREREG v2.1 protocol + sidecar, via the committed consumer
     validator `validate_prereg_approval` (RC-C3) — pinned hashes, the three
     approver choices, all authorization flags false;
  2. the C candidate data bytes (`artifacts/data/pilot_c_v2.jsonl`) against the
     recorded `data_sha256` AND the frozen-draft constant;
  3. the generator/verifier module bytes against `pilot_c_v2.manifest.json`'s
     `generator_module_sha256` (freeze draft v2 §5 requires module shas in the
     freeze record);
  4. Round 1/2 family lists recomputed via `propose_round_families` and matched
     THREE ways: manifest `proposed_round_*_families`, the freeze-draft-v2 §3
     published lists (embedded below as constants), and live recomputation —
     ordered equality, disjointness, reserve = 16;
  5. stratification / gold balance via `round_balance_attestation`, deep-equal
     against the manifest's embedded attestation, plus per-round invariants
     (5/5 categories, both gold sides present per category, 2 eligible rows per
     family);
  6. the analytic degenerate-score projection via `project_degenerate_scores`
     (the four constant strategies must sit at macro 0.500 and `user_follower`
     at 0.5 — a round whose degenerate projection moved would mean the gold
     structure changed).

Any failed check raises SystemExit BEFORE anything is written (no partial
output). Refuses to overwrite an existing draft.

Usage (dry-run is the only mode):
  CUDA_VISIBLE_DEVICES='' PYTHONPATH=src .venv/bin/python \
      scripts/prepare_c_freeze.py [--out reports/C_FREEZE_RECORD_DRAFT_20260921.json]

No GPU, no network, no model, no S content (S blocked).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "src"))

from minicpm_research.data_c import (  # noqa: E402
    project_degenerate_scores,
    propose_round_families,
    round_balance_attestation,
)
from minicpm_research.runs import file_hash  # noqa: E402
from validate_prereg_approval import validate_prereg_approval  # noqa: E402

DATA_REL = Path("artifacts/data/pilot_c_v2.jsonl")
MANIFEST_REL = Path("artifacts/data/pilot_c_v2.manifest.json")

# Constants from the committed candidate record (pilot_c_v2.manifest.json,
# generated 2026-09-15, status candidate_draft_not_frozen) and the freeze draft
# v2 §3 published round lists. Recomputed values must match BOTH.
EXPECTED_DATA_SHA256 = "e66fbd2659ef745a13280decf610f84aa4375630a66981b79c077a643f8cf302"
EXPECTED_MODULE_SHA256 = {
    "data_c.py": "cba3bda6ca03baa52c58670da5410325c3851767725b2ad71f0177e34e375347",
    "verifier.py": "6e28ff06c0f1161d1d49004f11f83f45a76a5fcb21669e77161115d351c3f6d2",
}
MODULE_REL = {
    "data_c.py": Path("src/minicpm_research/data_c.py"),
    "verifier.py": Path("src/minicpm_research/verifier.py"),
}
EXPECTED_ROUND_1 = [f"pilot-C-20260915-{i}" for i in
                    ("0000", "0003", "0008", "0011", "0016", "0019", "0024", "0027",
                     "0032", "0035", "0001", "0002")]
EXPECTED_ROUND_2 = [f"pilot-C-20260915-{i}" for i in
                    ("0004", "0007", "0009", "0010", "0017", "0018", "0025", "0026",
                     "0033", "0034", "0012", "0015")]
EXPECTED_ROWS = 160
EXPECTED_FAMILIES = 40
EXPECTED_RESERVE = 16
ELIGIBLE_ROWS_PER_FAMILY = 2


def _fail(message: str) -> None:
    raise SystemExit(f"REFUSING to draft the C freeze record: {message}")


def _git_head(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, timeout=10).strip()
    except Exception:
        return None


def _check(checks: list[dict[str, Any]], name: str, ok: bool, detail: str = "") -> None:
    if not ok:
        _fail(f"check '{name}' failed" + (f": {detail}" if detail else ""))
    checks.append({"check": name, "result": "pass", **({"detail": detail} if detail else {})})


def build_draft(root: Path) -> dict[str, Any]:
    """Run every binding check fail-closed and return the draft record (nothing written)."""
    checks: list[dict[str, Any]] = []

    # 1. The approved protocol + sidecar, via the committed RC-C3 consumer validator.
    approval_audit = validate_prereg_approval(root)  # raises SystemExit on any failure
    _check(checks, "prereg_v2_1_approval_validated",
           approval_audit.get("status") == "approved_data_after_amendment"
           and approval_audit.get("phase0_construct_admission_met") is False,
           "validate_prereg_approval returned its audit record; all *_authorized flags false")

    # 2. Data bytes.
    data_path = root / DATA_REL
    manifest_path = root / MANIFEST_REL
    if not data_path.is_file() or not manifest_path.is_file():
        _fail("candidate data or manifest missing")
    data_sha = file_hash(data_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _check(checks, "data_sha256_matches_candidate_record",
           data_sha == EXPECTED_DATA_SHA256 and manifest.get("data_sha256") == data_sha,
           f"recomputed {data_sha[:16]}… == manifest == freeze-draft constant")
    _check(checks, "candidate_status_is_not_frozen",
           manifest.get("status") == "candidate_draft_not_frozen",
           "this entry drafts from the candidate only")

    # 3. Generator/verifier module bytes (freeze draft v2 §5).
    module_binding: dict[str, Any] = {}
    for name, rel in MODULE_REL.items():
        p = root / rel
        if not p.is_file():
            _fail(f"module file missing: {rel}")
        live = file_hash(p)
        recorded = manifest.get("generator_module_sha256", {}).get(name)
        module_binding[name] = {"path": rel.as_posix(), "sha256_manifest": recorded,
                                "sha256_recomputed": live, "match": live == recorded == EXPECTED_MODULE_SHA256[name]}
        _check(checks, f"module_sha256_{name}",
               live == recorded == EXPECTED_MODULE_SHA256[name],
               f"recomputed {live[:16]}… == manifest == constant")

    # 4. Rows / families / round lists (three-way binding, ordered).
    rows = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    _check(checks, "row_and_family_counts",
           len(rows) == EXPECTED_ROWS and manifest.get("rows") == EXPECTED_ROWS
           and len({e["family_id"] for e in rows}) == EXPECTED_FAMILIES,
           f"{len(rows)} rows / {EXPECTED_FAMILIES} families")
    r1, r2, reserve = propose_round_families(rows)
    _check(checks, "round_1_list_three_way_match",
           r1 == EXPECTED_ROUND_1 and manifest.get("proposed_round_1_families") == r1,
           "live recomputation == freeze-draft-v2 §3 == manifest (ordered)")
    _check(checks, "round_2_list_three_way_match",
           r2 == EXPECTED_ROUND_2 and manifest.get("proposed_round_2_families") == r2,
           "live recomputation == freeze-draft-v2 §3 == manifest (ordered)")
    _check(checks, "rounds_disjoint_and_reserve_complete",
           not (set(r1) & set(r2)) and len(reserve) == EXPECTED_RESERVE
           and set(r1) | set(r2) | set(reserve) == {e["family_id"] for e in rows},
           f"disjoint; reserve {len(reserve)}; union covers all families")

    # 5. Stratification / gold balance: recompute, deep-match the manifest, check invariants.
    attestation: dict[str, Any] = {}
    for label, fams in (("round_1", r1), ("round_2", r2)):
        att = round_balance_attestation(rows, fams)
        _check(checks, f"balance_attestation_{label}_matches_manifest",
               manifest.get("round_balance_attestation", {}).get(label) == att,
               "deep-equal to the candidate manifest's embedded attestation")
        cats = sorted(att)
        eligible = [e for e in rows if e["family_id"] in set(fams) and e["in_round_eligible"]]
        per_fam = Counter(e["family_id"] for e in eligible)
        ok_cats = len(cats) == 5
        ok_gold = all(all(v > 0 for v in a["family_gold_balance"].values()) for a in att.values())
        ok_rows = (len(eligible) == len(fams) * ELIGIBLE_ROWS_PER_FAMILY
                   and set(per_fam.values()) == {ELIGIBLE_ROWS_PER_FAMILY})
        _check(checks, f"balance_invariants_{label}",
               ok_cats and ok_gold and ok_rows,
               f"{len(cats)}/5 categories; both gold sides present per category; "
               f"{len(eligible)} eligible rows = {ELIGIBLE_ROWS_PER_FAMILY}/family")
        attestation[label] = {"families_ordered": fams, "eligible_example_ids": sorted(e["example_id"] for e in eligible),
                              "attestation": att}

    # 6. Analytic degenerate projection (no model): constants must sit at 0.500.
    degenerate: dict[str, Any] = {}
    for label, fams in (("round_1", r1), ("round_2", r2)):
        proj = project_degenerate_scores(rows, fams)
        constants_ok = all(abs(proj[s]["macro"] - 0.5) < 1e-12
                           for s in ("always_affirmative", "always_negate", "always_letter_A", "always_letter_B"))
        uf = proj["user_follower"]
        _check(checks, f"degenerate_projection_{label}",
               constants_ok and uf["total"] == 4 and uf["correct"] == 2 and abs(uf["rate"] - 0.5) < 1e-12,
               "4 constant strategies at macro 0.500; user_follower 2/4 = 0.5")
        degenerate[label] = proj

    return {
        "schema": "c_freeze_record_draft_v1",
        "freeze_status": "draft_not_frozen",
        "this_document_freezes_nothing": True,
        "ticket": "C-freeze preparation (approver-issued 2026-09-21, step 1 of 3)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": {"script": "scripts/prepare_c_freeze.py", "git_head": _git_head(root),
                         "mode": "dry_run_draft_only"},
        "prereg_approval_audit": approval_audit,
        "data_binding": {
            "data_file": DATA_REL.as_posix(), "data_sha256": data_sha,
            "manifest_file": MANIFEST_REL.as_posix(), "manifest_sha256": file_hash(manifest_path),
            "rows": len(rows), "families": EXPECTED_FAMILIES,
        },
        "module_binding": module_binding,
        "rounds": {**attestation, "reserve_families_sorted": reserve},
        "degenerate_projection": degenerate,
        "checks_passed": checks,
        "prerequisites_remaining_before_any_freeze": {
            "independent_review_of_validator_and_e9": "in_progress_20260921",
            "r1_r2_level_a_sheets_signed": False,
            "disagreements_recorded_then_adjudicated": False,
            "approver_execution_approval": False,
            "note": ("Level A (gold_audit_v2) is a SAMPLE audit (C: 12/40 families, 12/20 "
                     "category_rule_gold cells) — it does NOT cover all in-round entries; "
                     "Level B (full in-round audit) is generated only AFTER the approved freeze."),
        },
        "execution_path_after_approval": (
            "This script cannot freeze. The executor (emitting the real round_in_manifest_frozen_v1 "
            "with freeze_status='frozen') will be part of the execution package — exact freeze files, "
            "hashes, and command — submitted for approver approval; it may run ONLY after that approval "
            "(approver step 3, 2026-09-21)."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="reports/C_FREEZE_RECORD_DRAFT_20260921.json",
                    help="output path for the DRAFT freeze record (refuses to overwrite)")
    args = ap.parse_args(argv)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    if out.exists():
        raise SystemExit(f"REFUSING to overwrite existing draft: {out}")
    draft = build_draft(ROOT)  # every check runs BEFORE any write; failure = zero output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(draft, indent=2, sort_keys=False, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "draft_written_not_frozen", "out": str(out),
                      "checks_passed": len(draft["checks_passed"]),
                      "data_sha256": draft["data_binding"]["data_sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
