"""Tests for scripts/prepare_c_freeze.py — the C-freeze PREPARATION entry (dry-run only).

The ticket's hardest guarantee is negative: this entry must be UNABLE to freeze.
These tests pin (a) the draft's content bindings (validator audit, data/module
hashes, three-way round lists, balance attestation, degenerate projection),
(b) fail-closed refusal with ZERO partial output on tampered approval files /
tampered data / validator failure, (c) the Level-B builder rejects the draft
(schema is not round_in_manifest_frozen_v1, freeze_status is not 'frozen'), and
(d) overwrite refusal.

CPU-only, no network, no GPU, no model, no S content.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import prepare_c_freeze as pcf  # noqa: E402


def _scratch_root(with_reports: bool = True) -> Path:
    """Scratch repo root carrying byte-identical copies of the approved files."""
    root = Path(tempfile.mkdtemp(prefix="c_freeze_test_"))
    if with_reports:
        (root / "reports").mkdir(parents=True)
        for name in ("PREREGISTRATION_PHASE0_REVISION_v2_1.yaml",
                     "PREREGISTRATION_PHASE0_REVISION_v2_1_APPROVAL.json"):
            shutil.copyfile(ROOT / "reports" / name, root / "reports" / name)
    return root


class DraftContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="c_freeze_draft_"))
        cls.out = cls.tmp / "draft.json"
        pcf.main(["--out", str(cls.out)])
        cls.draft = json.loads(cls.out.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_draft_is_explicitly_not_a_freeze(self):
        self.assertEqual(self.draft["schema"], "c_freeze_record_draft_v1")
        self.assertEqual(self.draft["freeze_status"], "draft_not_frozen")
        self.assertIs(self.draft["this_document_freezes_nothing"], True)
        # no value anywhere in the draft may claim a frozen status
        blob = json.dumps(self.draft)
        self.assertNotIn('"freeze_status": "frozen"', blob)
        self.assertNotIn("round_in_manifest_frozen_v1", self.draft["schema"])

    def test_all_binding_checks_passed(self):
        checks = self.draft["checks_passed"]
        self.assertGreaterEqual(len(checks), 12)
        self.assertTrue(all(c["result"] == "pass" for c in checks))
        names = {c["check"] for c in checks}
        for required in ("prereg_v2_1_approval_validated", "data_sha256_matches_candidate_record",
                         "round_1_list_three_way_match", "round_2_list_three_way_match",
                         "rounds_disjoint_and_reserve_complete", "degenerate_projection_round_1",
                         "degenerate_projection_round_2"):
            self.assertIn(required, names)

    def test_level_b_builder_rejects_the_draft(self):
        # the draft must never be consumable as a frozen in-round manifest
        import make_audit_package_level_b as lb
        with self.assertRaises(SystemExit):
            lb.validate_frozen_manifest(dict(self.draft))

    def test_data_and_module_bindings(self):
        self.assertEqual(self.draft["data_binding"]["data_sha256"], pcf.EXPECTED_DATA_SHA256)
        self.assertEqual(self.draft["data_binding"]["rows"], 160)
        for name, binding in self.draft["module_binding"].items():
            self.assertTrue(binding["match"], name)
            self.assertEqual(binding["sha256_recomputed"], pcf.EXPECTED_MODULE_SHA256[name])

    def test_round_lists_match_published_freeze_draft(self):
        self.assertEqual(self.draft["rounds"]["round_1"]["families_ordered"], pcf.EXPECTED_ROUND_1)
        self.assertEqual(self.draft["rounds"]["round_2"]["families_ordered"], pcf.EXPECTED_ROUND_2)
        self.assertEqual(len(self.draft["rounds"]["reserve_families_sorted"]), 16)
        for r in ("round_1", "round_2"):
            self.assertEqual(len(self.draft["rounds"][r]["eligible_example_ids"]), 24)

    def test_balance_attestation_invariants(self):
        for r in ("round_1", "round_2"):
            att = self.draft["rounds"][r]["attestation"]
            self.assertEqual(len(att), 5)
            for cat, a in att.items():
                self.assertTrue(all(v > 0 for v in a["family_gold_balance"].values()), cat)
                self.assertEqual(a["primary_samples"], 2 * a["families"], cat)

    def test_degenerate_projection_holds_constants_at_half(self):
        for r in ("round_1", "round_2"):
            proj = self.draft["degenerate_projection"][r]
            for s in ("always_affirmative", "always_negate", "always_letter_A", "always_letter_B"):
                self.assertAlmostEqual(proj[s]["macro"], 0.5, places=12)
            uf = proj["user_follower"]
            self.assertEqual((uf["correct"], uf["total"]), (2, 4))
            self.assertAlmostEqual(uf["rate"], 0.5, places=12)

    def test_prerequisites_are_open_and_approval_audit_bound(self):
        pre = self.draft["prerequisites_remaining_before_any_freeze"]
        self.assertIs(pre["r1_r2_level_a_sheets_signed"], False)
        self.assertIs(pre["disagreements_recorded_then_adjudicated"], False)
        self.assertIs(pre["approver_execution_approval"], False)
        audit = self.draft["prereg_approval_audit"]
        self.assertEqual(audit["protocol_sha256"],
                         "7bbd58cae219508702de6293a99ffb8ee1aeb275d29f43aae83a1eaa7d4f1196")
        self.assertIs(audit["phase0_construct_admission_met"], False)


class FailClosedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="c_freeze_fail_"))
        self._saved_root = pcf.ROOT

    def tearDown(self):
        pcf.ROOT = self._saved_root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_refuses_to_overwrite_existing_draft(self):
        out = self.tmp / "draft.json"
        pcf.main(["--out", str(out)])
        before = out.read_bytes()
        with self.assertRaises(SystemExit):
            pcf.main(["--out", str(out)])
        self.assertEqual(out.read_bytes(), before)

    def test_tampered_sidecar_refused_with_zero_output(self):
        scratch = _scratch_root()
        sidecar = scratch / "reports" / "PREREGISTRATION_PHASE0_REVISION_v2_1_APPROVAL.json"
        raw = sidecar.read_bytes()
        sidecar.write_bytes(raw.replace(b'"approved_data_after_amendment"', b'"approved_data_after_amendment "', 1))
        pcf.ROOT = scratch
        out = self.tmp / "draft.json"
        with self.assertRaises(SystemExit) as ctx:
            pcf.main(["--out", str(out)])
        self.assertIn("RC-C3 REFUSING", str(ctx.exception))
        self.assertFalse(out.exists(), "refusal must leave zero output")
        shutil.rmtree(scratch, ignore_errors=True)

    def test_tampered_protocol_yaml_refused(self):
        scratch = _scratch_root()
        proto = scratch / "reports" / "PREREGISTRATION_PHASE0_REVISION_v2_1.yaml"
        text = proto.read_text(encoding="utf-8")
        proto.write_text(text.replace("per_category_floor: null", "per_category_floor: 0.6", 1), encoding="utf-8")
        with self.assertRaises(SystemExit) as ctx:
            pcf.build_draft(scratch)
        # tampering trips the sidecar-binding check first ("does not match protocol
        # bytes"); either way the pinned-bytes defense must refuse with zero output
        self.assertIn("RC-C3 REFUSING", str(ctx.exception))
        shutil.rmtree(scratch, ignore_errors=True)

    def test_missing_approval_files_refused(self):
        scratch = _scratch_root(with_reports=False)
        with self.assertRaises(SystemExit):
            pcf.build_draft(scratch)
        shutil.rmtree(scratch, ignore_errors=True)

    def test_tampered_candidate_data_refused_with_zero_output(self):
        scratch = _scratch_root()
        (scratch / "artifacts" / "data").mkdir(parents=True)
        for rel in (pcf.DATA_REL, pcf.MANIFEST_REL):
            shutil.copyfile(ROOT / rel, scratch / rel)
        data = scratch / pcf.DATA_REL
        raw = bytearray(data.read_bytes())
        raw[100] ^= 0x01  # single-byte flip: hash must no longer match
        data.write_bytes(bytes(raw))
        pcf.ROOT = scratch
        out = self.tmp / "draft.json"
        with self.assertRaises(SystemExit) as ctx:
            pcf.main(["--out", str(out)])
        self.assertIn("data_sha256_matches_candidate_record", str(ctx.exception))
        self.assertFalse(out.exists(), "refusal must leave zero output")
        shutil.rmtree(scratch, ignore_errors=True)

    def test_module_drift_refused(self):
        scratch = _scratch_root()
        (scratch / "artifacts" / "data").mkdir(parents=True)
        for rel in (pcf.DATA_REL, pcf.MANIFEST_REL):
            shutil.copyfile(ROOT / rel, scratch / rel)
        (scratch / "src" / "minicpm_research").mkdir(parents=True)
        for name, rel in pcf.MODULE_REL.items():
            shutil.copyfile(ROOT / rel, scratch / rel)
        victim = scratch / pcf.MODULE_REL["data_c.py"]
        victim.write_text(victim.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as ctx:
            pcf.build_draft(scratch)
        self.assertIn("module_sha256_data_c.py", str(ctx.exception))
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
