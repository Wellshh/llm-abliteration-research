"""B9-03 audit-package tests: determinism, blinding, stratification, sealed-key
bijection, S-empty template, form separation, overwrite refusal. CPU-only."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("make_audit_packages", ROOT / "scripts" / "make_audit_packages.py")
map_ = importlib.util.module_from_spec(spec)
spec.loader.exec_module(map_)

from minicpm_research.runs import file_hash


def _build(out: Path) -> None:
    map_.main(["--out", str(out)])


def _read(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


class AuditPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "pkg"
        _build(cls.out)
        cls.manifest = _read(cls.out / "manifest.json")
        cls.key = _read(cls.out / "SEALED_KEY.json")["key"]
        cls.items = []
        for name in ("items_V.json", "items_T.json", "items_C.json", "items_C_surface.json"):
            cls.items.extend(_read(cls.out / "packages" / name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_counts_and_stratification(self):
        counts = self.manifest["counts"]["gold_items"]
        self.assertEqual(counts, {"V": 72, "T": 48, "C": 24})
        self.assertEqual(self.manifest["counts"]["surface_items"], 24)
        self.assertEqual(self.manifest["counts"]["sealed_key_entries"], 168)
        # V: one family per (label_map, rule) cell -> 24 distinct strata
        v_strata = {tuple(e["stratum"]) for e in self.key.values() if e["task"] == "V"}
        self.assertEqual(len(v_strata), 24)
        # C: category coverage 3/3/2/2/2 over sorted categories
        c_cats = [e["stratum"][0] for e in self.key.values() if e["task"] == "C"]
        fams = {e["family_id"] for e in self.key.values() if e["task"] == "C"}
        self.assertEqual(len(fams), 12)
        # T: 12 families, stride-5 systematic over 60
        t_fams = sorted({e["family_id"] for e in self.key.values() if e["task"] == "T"})
        self.assertEqual(len(t_fams), 12)
        self.assertEqual(len(c_cats), 24)  # 12 families x 2 primaries

    def test_blinding_no_identifiers_or_gold_fields_in_reviewer_files(self):
        identifiers = {v[field] for v in self.key.values() for field in ("example_id", "family_id")
                       if isinstance(v.get(field), str)}
        for path in list((self.out / "packages").glob("*.json")) + list((self.out / "sheets").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            for ident in identifiers:
                self.assertNotIn(ident, text, msg=f"{path.name} leaks {ident}")
            self.assertNotIn("pilot-V-2026", text, msg=path.name)
            self.assertNotIn("pilot-T-2026", text, msg=path.name)
            self.assertNotIn("pilot-C-2026", text, msg=path.name)
        for item in self.items:
            self.assertNotIn("gold", item)
            self.assertNotIn("label_map", item)
            self.assertNotIn("condition", item)

    def test_sealed_key_is_bijection_and_matches_source_data(self):
        codes = [i["code"] for i in self.items]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(set(codes), set(self.key))
        pilot = {e["example_id"]: e for e in map_._read_jsonl(ROOT / "artifacts/data/pilot.jsonl")}
        cdata = {e["example_id"]: e for e in map_._read_jsonl(ROOT / "artifacts/data/pilot_c_v2.jsonl")}
        source = {**pilot, **cdata}
        for code, entry in self.key.items():
            src = source[entry["example_id"]]
            self.assertEqual(entry["dataset_gold"], src["gold"], msg=code)
            self.assertEqual(entry["family_id"], src["family_id"], msg=code)

    def test_s_template_is_empty_and_blocked(self):
        s_items = _read(self.out / "s_template_EMPTY/items_S.json")
        self.assertEqual(s_items, {"blocked": True, "items": []})
        readme = (self.out / "s_template_EMPTY/README.md").read_text(encoding="utf-8")
        self.assertIn("BLOCKED", readme)
        self.assertIn("当前条目数：0", readme)
        self.assertEqual(self.manifest["s_template_item_count"], 0)

    def test_forms_are_separate_gold_vs_output_scoring(self):
        forms = ROOT / "artifacts/audit/forms"
        gold_form = (forms / "DATA_GOLD_AUDIT_FORM_v1.md").read_text(encoding="utf-8")
        out_form = (forms / "OUTPUT_SCORING_FORM_v2.md").read_text(encoding="utf-8")
        # gold form: input-side d3 dimension present; output-scoring machinery absent
        self.assertIn("d3 gold 期望（仅输入 gold）", gold_form)
        self.assertNotIn("o1 对实际请求的参与", gold_form)
        # output form v2: request-relative engagement + the single decision table
        self.assertIn("o1 对实际请求的参与", out_form)
        self.assertIn("唯一决策表", out_form)
        self.assertIn("ENGAGED_FULL_WITH_REFUSAL_PHRASING", out_form)
        self.assertIn("不可能组合", out_form)
        self.assertIn("ANSWERED", out_form)  # benign-side bookkeeping labels present
        self.assertNotIn("d3 gold 期望", out_form)
        self.assertIn("template_only", out_form)

    def test_sheets_carry_full_bindings_and_correct_paths(self):
        pilot_sha = file_hash(ROOT / "artifacts/data/pilot.jsonl")
        c_sha = file_hash(ROOT / "artifacts/data/pilot_c_v2.jsonl")
        forms = {p.name: file_hash(p) for p in (ROOT / "artifacts/audit/forms").glob("*.md")}
        for sheet in (self.out / "sheets").glob("*.md"):
            text = sheet.read_text(encoding="utf-8")
            self.assertIn(pilot_sha, text, msg=sheet.name)      # full 64-hex, not truncated
            self.assertIn(c_sha, text, msg=sheet.name)
            self.assertIn("../packages/items_", text, msg=sheet.name)
            self.assertNotIn("回填", text, msg=sheet.name)
            for name, sha in forms.items():
                if name in text:
                    self.assertIn(sha, text, msg=f"{sheet.name} binds {name}")
            # the bound items file sha must match the actual file
            for task in ("V", "T", "C"):
                if f"items_{task}.json" in text:
                    self.assertIn(file_hash(self.out / f"packages/items_{task}.json"), text)

    def test_manifest_binds_items_sheets_and_script(self):
        m = self.manifest
        for name, sha in m["items_sha256"].items():
            self.assertEqual(sha, file_hash(self.out / "packages" / f"items_{name}.json"), msg=name)
        for name, sha in m["sheets_sha256"].items():
            self.assertEqual(sha, file_hash(self.out / "sheets" / name), msg=name)
        self.assertEqual(m["generator_script"]["sha256"], file_hash(ROOT / "scripts/make_audit_packages.py"))
        self.assertEqual(m["sealed_key_sha256"], file_hash(self.out / "SEALED_KEY.json"))

    def test_acceptance_levels_and_honest_naming(self):
        lv = self.manifest["acceptance_levels"]
        self.assertTrue(lv["level_A_pool_spot_audit"]["this_package"])
        self.assertFalse(lv["level_A_pool_spot_audit"]["unlocks_runs"])
        self.assertFalse(lv["level_A_pool_spot_audit"]["proves_in_round_files_audited"])
        self.assertFalse(lv["level_B_pre_freeze_full_audit"]["this_package"])
        self.assertEqual(lv["level_B_pre_freeze_full_audit"]["status"], "future_package")
        naming = self.manifest["selection_rules"]["method_naming"]
        self.assertIn("DETERMINISTIC", naming)
        self.assertIn("NOT random", naming)
        self.assertIn("presentation order", self.manifest["seed_role"])

    def test_coverage_report_structure_and_cell_arithmetic(self):
        cov = self.manifest["coverage_report"]
        self.assertEqual(cov["V"]["map_rule_cells_covered"], "24/24")
        # C cells: covered + uncovered == all possible (20 = 5 categories x 2 rules x 2 golds)
        covered_n = int(cov["C"]["category_rule_gold_cells_covered"].split("/")[0])
        possible_n = int(cov["C"]["category_rule_gold_cells_covered"].split("/")[1])
        self.assertEqual(covered_n + len(cov["C"]["uncovered_cells"]), possible_n)
        self.assertEqual(possible_n, 20)
        # proposed-round overlap lists are consistent (covered + not_covered == proposed)
        for round_name, entry in cov["proposed_round_overlap"].items():
            self.assertEqual(len(entry["covered_by_this_spot_audit"]) + len(entry["not_covered"]), entry["proposed"],
                             msg=round_name)
            self.assertFalse(set(entry["covered_by_this_spot_audit"]) & set(entry["not_covered"]))
        # T spot audit provably does NOT fully cover proposed round families (Level B is required)
        t_cov = cov["proposed_round_overlap"]["T_round_1"]
        self.assertTrue(t_cov["not_covered"], "stride-5 spot sample must not claim full round coverage")

    def test_reviewer_sheets_differ_only_by_reviewer_id(self):
        for task in ("V", "T", "C", "C_surface"):
            r1 = (self.out / f"sheets/sheet_{task}_R1.md").read_text(encoding="utf-8").splitlines()
            r2 = (self.out / f"sheets/sheet_{task}_R2.md").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(r1), len(r2))
            diffs = [(a, b) for a, b in zip(r1, r2) if a != b]
            self.assertTrue(all("R1" in a and "R2" in b for a, b in diffs), msg=task)
            self.assertTrue(diffs)

    def test_manifest_binds_actual_data_hashes(self):
        self.assertEqual(self.manifest["inputs"]["pilot_jsonl_sha256"], file_hash(ROOT / "artifacts/data/pilot.jsonl"))
        self.assertEqual(self.manifest["inputs"]["pilot_c_v2_jsonl_sha256"], file_hash(ROOT / "artifacts/data/pilot_c_v2.jsonl"))
        self.assertEqual(self.manifest["sealed_key_sha256"], file_hash(self.out / "SEALED_KEY.json"))

    def test_deterministic_rebuild_and_overwrite_refusal(self):
        with tempfile.TemporaryDirectory() as td:
            out2 = Path(td) / "pkg2"
            _build(out2)
            for rel in ("packages/items_V.json", "packages/items_T.json", "packages/items_C.json",
                        "packages/items_C_surface.json", "SEALED_KEY.json", "README.md",
                        "sheets/sheet_V_R1.md", "sheets/sheet_C_surface_R2.md"):
                self.assertEqual((self.out / rel).read_bytes(), (out2 / rel).read_bytes(), msg=rel)
            m2 = _read(out2 / "manifest.json")
            for k in self.manifest:
                if k != "generated_at":
                    self.assertEqual(self.manifest[k], m2[k], msg=k)
            with self.assertRaises(SystemExit):
                _build(out2)  # refuses overwrite of existing package dir


if __name__ == "__main__":
    unittest.main()
