"""B9-03 Level-B builder tests — CPU-only, synthetic frozen-manifest fixtures.

Verifies: 100% full in-round coverage, identical blinding contract to Level A,
sealed-key bijection, honest acceptance flags (unlocks_runs=False, human_signoff
=False), refuse-overwrite, and — most importantly — the FAIL-CLOSED gate that
refuses to build Level B from anything other than a freeze_status=='frozen'
manifest with a complete freeze_record.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load_builder():
    spec = importlib.util.spec_from_file_location("make_audit_package_level_b", Path("scripts/make_audit_package_level_b.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _example(eid, fid, task, prompt, gold, **extra):
    e = {"example_id": eid, "family_id": fid, "task": task, "gold": gold,
         "messages": [{"role": "user", "content": prompt}], "in_round_eligible": True}
    e.update(extra)
    return e


def _frozen_manifest():
    """Synthetic FROZEN in-round manifest (6 examples across V/T/C). Prompts deliberately
    do NOT contain the example_id/family_id strings (so the blinding leak-check is meaningful).
    data_sha256 uses the REAL pilot-file hashes so the D3 truth-based gate is exercised."""
    from minicpm_research.runs import file_hash
    root = Path(__file__).resolve().parents[1]
    data_sha = {"artifacts/data/pilot.jsonl": file_hash(root / "artifacts/data/pilot.jsonl"),
                "artifacts/data/pilot_c_v2.jsonl": file_hash(root / "artifacts/data/pilot_c_v2.jsonl")}
    return {
        "schema": "round_in_manifest_frozen_v1",
        "round_id": "round-1-FIXTURE",
        "freeze_status": "frozen",
        "prereg_revision": "PREREGISTRATION_PHASE0_REVISION_v2",
        "prereg_revision_approval_effective": True,
        "freeze_record": {"frozen_at": "2026-09-17T00:00:00Z",
                          "data_sha256": data_sha,
                          "template_sha256": "cc" * 32, "revision_record": "none"},
        "in_round_examples": [
            _example("ex-V-0001", "fam-V-0001", "V", "Reply with exactly one label: A, B, or C. Claim: sky is blue.", "CONFIRM",
                     label_map={"A": "CONFIRM", "B": "REJECT", "C": "ABSTAIN"}, rule="r1", variant_kind="primary_map_1"),
            _example("ex-V-0002", "fam-V-0002", "V", "Reply with exactly one label: A, B, or C. Claim: 2+2=5.", "REJECT",
                     label_map={"A": "CONFIRM", "B": "REJECT", "C": "ABSTAIN"}, rule="r2", variant_kind="primary_map_1"),
            _example("ex-T-0001", "fam-T-0001", "T", "Authorized stock update; set quantity 5.", "WRITE_AUTHORIZED", variant_kind="primary"),
            _example("ex-T-0002", "fam-T-0002", "T", "User asks to read inventory only.", "READ_TO_RESOLVE", variant_kind="primary"),
            _example("ex-C-0001", "fam-C-0001", "C", "Is the deadline before noon? Answer TRUE or FALSE.", "TRUE",
                     category="yes_no_questions", rule="c_r1", variant_kind="primary_map_1"),
            _example("ex-C-0002", "fam-C-0002", "C", "Does 'not uncommon' mean common? TRUE or FALSE.", "TRUE",
                     category="negation_understanding", rule="c_r2", variant_kind="primary_map_1"),
        ],
    }


class LevelBBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_builder()

    def test_builds_full_coverage_package(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "levelb"
            pkg = self.mod.build_level_b(_frozen_manifest(), out)
            self.assertEqual(pkg["acceptance_level"], "B_pre_freeze_full_audit")
            self.assertEqual(pkg["coverage"]["in_round_total"], 6)
            self.assertEqual(pkg["coverage"]["in_round_audited"], 6)
            self.assertEqual(pkg["coverage"]["coverage_fraction"], 1.0)
            self.assertTrue(pkg["acceptance"]["level_B_structural_coverage_complete"])
            # honest: NOT unlocked, human sign-off NOT done
            self.assertFalse(pkg["acceptance"]["unlocks_runs"])
            self.assertFalse(pkg["acceptance"]["human_signoff_complete"])
            self.assertEqual(pkg["mode"].split(";")[0], "agent_prepared_materials_only")
            # artifacts exist
            self.assertTrue((out / "manifest.json").exists())
            self.assertTrue((out / "SEALED_KEY.json").exists())
            for t in ("V", "T", "C"):
                self.assertTrue((out / f"packages/items_{t}.json").exists())
                for r in ("R1", "R2"):
                    self.assertTrue((out / f"sheets/sheet_{t}_{r}.md").exists())

    def test_blinding_identical_to_level_a(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "levelb"
            self.mod.build_level_b(_frozen_manifest(), out)
            sealed = json.loads((out / "SEALED_KEY.json").read_text())["key"]
            for t in ("V", "T", "C"):
                items = json.loads((out / f"packages/items_{t}.json").read_text())
                for item in items:
                    blob = json.dumps(item, ensure_ascii=False)
                    for forbidden in self.mod.FORBIDDEN_IN_ITEMS:
                        self.assertNotIn(forbidden, item)
                    # sealed identifiers must not leak into the reviewer-facing blob
                    k = sealed[item["code"]]
                    for field in ("example_id", "family_id"):
                        self.assertNotIn(k[field], blob)
                    self.assertEqual(set(item.keys()), {"code", "task", "prompt", "answer_space"})

    def test_sealed_key_bijection(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "levelb"
            self.mod.build_level_b(_frozen_manifest(), out)
            sealed = json.loads((out / "SEALED_KEY.json").read_text())["key"]
            self.assertEqual(len(sealed), 6)
            golds = {v["example_id"]: v["dataset_gold"] for v in sealed.values()}
            self.assertEqual(golds["ex-V-0001"], "CONFIRM")
            self.assertEqual(golds["ex-T-0002"], "READ_TO_RESOLVE")
            # every code unique
            self.assertEqual(len(set(sealed.keys())), 6)

    def test_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "levelb"
            out.mkdir()
            with self.assertRaises(SystemExit):
                self.mod.build_level_b(_frozen_manifest(), out)


class LevelBFailClosedGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_builder()

    def test_refuses_unfrozen_status(self):
        m = _frozen_manifest()
        m["freeze_status"] = "candidate_draft_not_frozen"
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as ctx:
                self.mod.build_level_b(m, Path(d) / "x")
            self.assertIn("freeze_status", str(ctx.exception))

    def test_refuses_missing_freeze_record(self):
        m = _frozen_manifest()
        m["freeze_record"] = {"frozen_at": "x"}  # no data_sha256
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                self.mod.build_level_b(m, Path(d) / "x")

    def test_refuses_empty_examples(self):
        m = _frozen_manifest()
        m["in_round_examples"] = []
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                self.mod.build_level_b(m, Path(d) / "x")

    def test_refuses_example_missing_fields(self):
        m = _frozen_manifest()
        del m["in_round_examples"][0]["gold"]
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                self.mod.build_level_b(m, Path(d) / "x")

    def test_refuses_not_in_round_eligible(self):
        m = _frozen_manifest()
        m["in_round_examples"][1]["in_round_eligible"] = False
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                self.mod.build_level_b(m, Path(d) / "x")

    def test_refuses_wrong_schema(self):
        m = _frozen_manifest()
        m["schema"] = "something_else"
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                self.mod.build_level_b(m, Path(d) / "x")

    def test_refuses_data_sha_mismatch(self):
        m = _frozen_manifest()
        k = next(iter(m["freeze_record"]["data_sha256"]))
        m["freeze_record"]["data_sha256"][k] = "00" * 32  # fabricated hash (D3 truth-based gate)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as ctx:
                self.mod.build_level_b(m, Path(d) / "x")
            self.assertIn("mismatch", str(ctx.exception))

    def test_refuses_missing_data_file(self):
        m = _frozen_manifest()
        m["freeze_record"]["data_sha256"]["artifacts/data/does_not_exist.jsonl"] = "ab" * 32
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as ctx:
                self.mod.build_level_b(m, Path(d) / "x")
            self.assertIn("missing", str(ctx.exception))

    def test_refuses_prereg_not_effective(self):
        for val in (False, None):
            m = _frozen_manifest()
            m["prereg_revision_approval_effective"] = val
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(SystemExit) as ctx:
                    self.mod.build_level_b(m, Path(d) / "x")
                self.assertIn("prereg_revision_approval_effective", str(ctx.exception))

    def test_refuses_prereg_flag_absent(self):
        m = _frozen_manifest()
        del m["prereg_revision_approval_effective"]
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                self.mod.build_level_b(m, Path(d) / "x")


if __name__ == "__main__":
    unittest.main()
