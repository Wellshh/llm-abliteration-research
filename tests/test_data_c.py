"""B9-01 C control family tests: generator determinism, independent verification,
structure per the pinned v2 taxonomy, discovery-variant invariants, namespace
disjointness from the historical pilot, and no-gold-leak rendering. CPU-only."""
from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minicpm_research.data_c import (build_c_pilot, project_degenerate_scores,
                                     propose_round_families, round_balance_attestation)
from minicpm_research.verifier import (C_CATEGORIES, C_STANCE_CATEGORY, C_SURFACE_REFUSAL_TOKENS,
                                       parse_c_verdict, validate_dataset, verify_example)

NUM_RE = re.compile(r"\d+")
ID_RE = re.compile(r"(?:synthetic-c|site|R)-[0-9A-Za-z\-]+")


def _by_family(examples):
    fams = {}
    for e in examples:
        fams.setdefault(e["family_id"], []).append(e)
    return fams


def _kind(fam, kind):
    return next(e for e in fam if e["variant_kind"] == kind)


class CGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples = build_c_pilot()
        cls.fams = _by_family(cls.examples)

    def test_build_is_deterministic(self):
        again = build_c_pilot()
        self.assertEqual(json.dumps(again, sort_keys=True), json.dumps(self.examples, sort_keys=True))

    def test_counts_categories_balance_and_rounds(self):
        self.assertEqual(len(self.examples), 160)
        self.assertEqual(len(self.fams), 40)
        base = [e for e in self.examples if e["variant_kind"] in ("primary_map_1", "stance_agree")]
        per_cat = Counter(e["category"] for e in base)
        self.assertEqual(dict(per_cat), {c: 8 for c in C_CATEGORIES})
        for cat in C_CATEGORIES:
            golds = Counter(e["gold"] for e in base if e["category"] == cat)
            domain = ("YES", "NO") if cat == "yes_no_questions" else ("TRUE", "FALSE")
            self.assertEqual(golds[domain[0]], 4, msg=cat)
            self.assertEqual(golds[domain[1]], 4, msg=cat)
            rules = Counter(e["rule"] for e in base if e["category"] == cat)
            self.assertEqual(sorted(rules.values()), [4, 4], msg=cat)
        self.assertEqual(Counter(e["variant_kind"] for e in self.examples),
                         Counter({"primary_map_1": 32, "primary_map_2": 32, "stance_agree": 8,
                                  "stance_oppose": 8, "paraphrase_discovery": 40,
                                  "translation_zh_discovery": 40}))
        stance_maps = Counter(json.dumps(_kind(v, "stance_agree")["label_map"], sort_keys=True)
                              for f, v in self.fams.items() if v[0]["category"] == C_STANCE_CATEGORY)
        self.assertEqual(sorted(stance_maps.values()), [4, 4])
        r1, r2, reserve = propose_round_families(self.examples, per_round=12)
        self.assertEqual((len(r1), len(r2), len(reserve)), (12, 12, 16))
        self.assertFalse(set(r1) & set(r2))
        self.assertFalse((set(r1) | set(r2)) & set(reserve))
        for rounds in (r1, r2):
            cats = {self.fams[f][0]["category"] for f in rounds}
            self.assertEqual(cats, set(C_CATEGORIES))
            # Review finding 2: per-round per-category gold balance and rule mixing
            balance = round_balance_attestation(self.examples, rounds)
            for cat, att in balance.items():
                golds = sorted(att["family_gold_balance"].values())
                expected = [1, 1] if att["families"] == 2 else [2, 2]
                self.assertEqual(golds, expected, msg=cat)
                self.assertEqual(len(att["rules"]), 2, msg=f"{cat} pairs must mix both rules")
            # Every frozen degenerate strategy must sit at chance (0.5) on the round set
            degen = project_degenerate_scores(self.examples, rounds)
            for strategy in ("always_affirmative", "always_negate", "always_letter_A", "always_letter_B"):
                self.assertEqual(degen[strategy]["macro"], 0.5, msg=strategy)
            self.assertEqual(degen["user_follower"]["rate"], 0.5)

    def test_swap_pair_and_stance_pair_structure(self):
        for fid, fam in self.fams.items():
            cat = fam[0]["category"]
            golds = {e["gold"] for e in fam}
            self.assertEqual(len(golds), 1, msg=fid)
            if cat == C_STANCE_CATEGORY:
                a, o = _kind(fam, "stance_agree"), _kind(fam, "stance_oppose")
                self.assertEqual(a["label_map"], o["label_map"], msg=fid)
                self.assertEqual(a["claim"], o["claim"])
                self.assertEqual(a["evidence"], o["evidence"])
                self.assertNotEqual(a["messages"], o["messages"])  # stance sentence differs
            else:
                m1, m2 = _kind(fam, "primary_map_1"), _kind(fam, "primary_map_2")
                self.assertEqual(m1["claim"], m2["claim"])
                self.assertEqual(m1["evidence"], m2["evidence"])
                self.assertEqual(set(m1["label_map"]), set(m2["label_map"]))
                for letter in m1["label_map"]:
                    self.assertNotEqual(m1["label_map"][letter], m2["label_map"][letter], msg=fid)

    def test_discovery_variants_are_ineligible_and_content_preserving(self):
        for fid, fam in self.fams.items():
            base_kind = "stance_agree" if fam[0]["category"] == C_STANCE_CATEGORY else "primary_map_1"
            base = _kind(fam, base_kind)
            base_text = " ".join(m["content"] for m in base["messages"])
            for kind in ("paraphrase_discovery", "translation_zh_discovery"):
                var = _kind(fam, kind)
                self.assertFalse(var["in_round_eligible"], msg=fid)
                self.assertTrue(base["in_round_eligible"])
                self.assertEqual(var["gold"], base["gold"])
                self.assertEqual(var["label_map"], base["label_map"])
                self.assertEqual(var["claim"], base["claim"])
                self.assertEqual(var["evidence"], base["evidence"])
                text = " ".join(m["content"] for m in var["messages"])
                self.assertNotEqual(text, base_text)
                # numeric and ID tokens survive every surface form (verifier invariant)
                self.assertTrue(set(NUM_RE.findall(base_text)) <= set(NUM_RE.findall(text)), msg=fid)
                self.assertTrue(set(ID_RE.findall(base_text)) <= set(ID_RE.findall(text)), msg=fid)
                if kind == "translation_zh_discovery":
                    self.assertTrue(re.search(r"[一-鿿]", text), msg=fid)

    def test_surface_refusal_families_carry_benign_refusal_words(self):
        found = 0
        for e in self.examples:
            if e["category"] == "surface_refusal_words_non_refusal":
                notes = e["evidence"]["metadata"]["surface_notes"]
                self.assertTrue(any(tok in notes.lower() for tok in C_SURFACE_REFUSAL_TOKENS))
                found += 1
            else:
                self.assertNotIn("surface_notes", e["evidence"].get("metadata", {}))
        self.assertEqual(found, 32)  # 8 families x 4 variants

    def test_no_direct_gold_label_printed_in_user_message(self):
        # LIMITED scope (review record-tightening): proves the gold label string is not
        # directly printed into the user message. This is NOT a full semantic
        # non-leakage proof; human gold review (B9-03) covers content-level audit.
        for e in self.examples:
            user = e["messages"][1]["content"]
            self.assertNotIn(e["gold"], user)
            self.assertNotIn(json.dumps(e["gold"]), user)

    def test_all_decision_necessary_claim_fields_reach_the_prompt(self):
        # Review finding 1: gold recomputation being correct does NOT mean the model
        # sees a complete question; every decision-necessary claim scalar must appear
        # in the rendered messages of EVERY surface form.
        def scalars(obj):
            if isinstance(obj, dict):
                return [s for k, v in obj.items() if k != "statement" for s in scalars(v)]
            if isinstance(obj, list):
                return [s for v in obj for s in scalars(v)]
            return [obj]
        for e in self.examples:
            text = " ".join(m["content"] for m in e["messages"])
            for value in scalars(e["claim"]):
                self.assertIn(str(value), text, msg=f"{e['example_id']} missing claim value {value!r}")

    def test_timetable_deadline_visible_in_all_surfaces(self):
        # Regression for pilot-C-20260915-0009-0 (deadline=24 absent from v1 prompts).
        checked = 0
        for e in self.examples:
            if e["rule"] == "c_timetable_strictly_before":
                user = e["messages"][1]["content"]
                self.assertIn(str(e["claim"]["deadline"]), user, msg=e["example_id"])
                self.assertIn("截止时间" if e["surface_form"] == "zh" else "deadline", user)
                checked += 1
        self.assertEqual(checked, 32)  # 8 families x 4 variants

    def test_discovery_variants_bind_to_first_primary_and_keep_stance(self):
        # Review finding 4: discovery variants are pure surface variants of the FIRST
        # primary; in stance families they keep the agree stance and never silently
        # become a second experimental level of the stance variable.
        for fid, fam in self.fams.items():
            is_stance = fam[0]["category"] == C_STANCE_CATEGORY
            base_kind = "stance_agree" if is_stance else "primary_map_1"
            base = _kind(fam, base_kind)
            for kind in ("paraphrase_discovery", "translation_zh_discovery"):
                var = _kind(fam, kind)
                self.assertEqual(var["derived_from_primary"], base_kind, msg=fid)
                self.assertEqual(var["stance"], base["stance"], msg=fid)
            if is_stance:
                para = " ".join(m["content"] for m in _kind(fam, "paraphrase_discovery")["messages"])
                zh = " ".join(m["content"] for m in _kind(fam, "translation_zh_discovery")["messages"])
                self.assertIn("confident this claim is correct", para)
                self.assertNotIn("sure this claim is wrong", para)
                self.assertIn("我确信这个陈述是对的", zh)
                self.assertNotIn("我确信这个陈述是错的", zh)


class CVerifierIndependenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples = build_c_pilot()

    def _one_per_rule(self):
        seen = {}
        for e in self.examples:
            if e["variant_kind"] in ("primary_map_1", "stance_agree"):
                seen.setdefault(e["rule"], e)
        return seen

    def test_corrupted_claims_flip_independent_recomputation(self):
        for rule, e in self._one_per_rule().items():
            domain = tuple(e["semantic_domain"])
            bad = copy.deepcopy(e)
            holds_now = verify_example(bad) == domain[0]
            if rule == "c_not_all_passed":
                recs = bad["evidence"]["records"]
                if holds_now:
                    recs.update({k: True for k in recs})
                else:
                    recs[next(iter(recs))] = False
            elif rule in ("c_field_equals", "c_field_not_equals"):
                fields = bad["evidence"]["fields"]
                f = bad["claim"]["field"]
                if rule == "c_field_equals":   # holds = observed == claimed
                    fields[f] = "CORRUPT-9999" if holds_now else bad["claim"]["value"]
                else:                           # holds = observed != claimed
                    fields[f] = bad["claim"]["value"] if holds_now else "CORRUPT-9999"
            elif rule == "c_sum_at_least":
                bad["claim"]["minimum"] = 100 if holds_now else 0
            elif rule == "c_arithmetic_equals":
                correct = bad["claim"]["left"] + bad["claim"]["right"] if bad["claim"]["op"] == "+" \
                    else bad["claim"]["left"] * bad["claim"]["right"]
                bad["claim"]["equals"] = correct + 1 if holds_now else correct
            else:  # c_timetable_strictly_before
                arr = bad["evidence"]["departure"] + bad["evidence"]["duration"]
                bad["claim"]["deadline"] = arr if holds_now else arr + 1
            self.assertNotEqual(verify_example(bad), e["gold"], msg=rule)
            with self.assertRaises(ValueError):
                validate_dataset([bad])

    def test_null_observations_rejected_c_worlds_fully_observed(self):
        for rule, e in self._one_per_rule().items():
            bad = copy.deepcopy(e)
            if "records" in bad["evidence"]:
                bad["evidence"]["records"][next(iter(bad["evidence"]["records"]))] = None
            elif "fields" in bad["evidence"]:
                bad["evidence"]["fields"][bad["claim"]["field"]] = None
            elif "bins" in bad["evidence"]:
                bad["evidence"]["bins"][0] = None
            elif "departure" in bad["evidence"]:
                bad["evidence"]["duration"] = None
            else:  # arithmetic: claim operand null
                bad["claim"]["left"] = None
            with self.assertRaises(ValueError):
                verify_example(bad)

    def test_surface_refusal_note_is_required_for_that_category(self):
        e = next(x for x in self.examples if x["category"] == "surface_refusal_words_non_refusal")
        bad = copy.deepcopy(e)
        del bad["evidence"]["metadata"]["surface_notes"]
        with self.assertRaisesRegex(ValueError, "refusal-word surface note"):
            verify_example(bad)

    def test_rule_category_matrix_enforced(self):
        e = next(x for x in self.examples if x["category"] == "negation_understanding")
        bad = copy.deepcopy(e)
        bad["rule"] = "c_arithmetic_equals"
        with self.assertRaises(ValueError):
            verify_example(bad)


class CStructuralValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples = build_c_pilot()
        cls.fams = _by_family(cls.examples)

    def _fam(self, category=None):
        for fid, fam in self.fams.items():
            if category is None or fam[0]["category"] == category:
                return [copy.deepcopy(e) for e in fam]
        raise AssertionError("no family")

    def test_missing_variant_rejected(self):
        fam = self._fam()
        with self.assertRaisesRegex(ValueError, "exactly two primary"):
            validate_dataset(fam[:3])

    def test_discovery_variant_must_not_be_round_eligible(self):
        fam = self._fam()
        for e in fam:
            if e["variant_kind"] == "paraphrase_discovery":
                e["in_round_eligible"] = True
        with self.assertRaisesRegex(ValueError, "never round-eligible"):
            validate_dataset(fam)

    def test_family_gold_must_be_uniform(self):
        fam = self._fam()
        fam[1]["gold"] = fam[1]["semantic_domain"][1] if fam[1]["gold"] == fam[1]["semantic_domain"][0] else fam[1]["semantic_domain"][0]
        with self.assertRaises(ValueError):
            validate_dataset(fam)

    def test_stance_pair_map_mismatch_rejected(self):
        fam = self._fam(C_STANCE_CATEGORY)
        opp = _kind(fam, "stance_oppose")
        opp["label_map"] = {"A": opp["label_map"]["B"], "B": opp["label_map"]["A"]}  # actual letter swap
        with self.assertRaisesRegex(ValueError, "share one label map"):
            validate_dataset(fam)

    def test_swap_pair_must_be_exact_letter_swap(self):
        fam = self._fam("negation_understanding")
        _kind(fam, "primary_map_2")["label_map"] = _kind(fam, "primary_map_1")["label_map"]
        with self.assertRaisesRegex(ValueError, "letter-swap"):
            validate_dataset(fam)

    def test_variant_content_divergence_rejected(self):
        # Review finding 3: same gold must not let different content pass as a variant.
        fam = self._fam()
        fam[2]["evidence"] = json.loads(json.dumps(fam[2]["evidence"]))
        fam[2]["evidence"]["metadata"]["site"] = "site-999"
        with self.assertRaisesRegex(ValueError, "identical claim and evidence"):
            validate_dataset(fam)

    def test_message_tampering_without_field_change_rejected(self):
        # Review finding 3: messages must correspond to the structured fields.
        fam = self._fam()
        fam[0]["messages"][1]["content"] += " (tampered)"
        with self.assertRaisesRegex(ValueError, "do not correspond"):
            validate_dataset(fam)

    def test_stance_marker_swap_rejected(self):
        # Review finding 3: variant_kind must match the bound stance field.
        fam = self._fam(C_STANCE_CATEGORY)
        a, o = _kind(fam, "stance_agree"), _kind(fam, "stance_oppose")
        a["variant_kind"], o["variant_kind"] = "stance_oppose", "stance_agree"
        with self.assertRaises(ValueError):
            validate_dataset(fam)

    def test_discovery_stance_rebinding_rejected(self):
        # Review finding 4: a discovery variant may not silently flip the stance level.
        fam = self._fam(C_STANCE_CATEGORY)
        para = _kind(fam, "paraphrase_discovery")
        para["stance"] = "oppose"
        with self.assertRaisesRegex(ValueError, "stance does not match"):
            validate_dataset(fam)


class CParseAndNamespaceTests(unittest.TestCase):
    def test_parse_c_verdict_semantics(self):
        m = {"A": "TRUE", "B": "FALSE"}
        self.assertEqual(parse_c_verdict(" A ", m, ("TRUE", "FALSE"))["semantic_label"], "TRUE")
        self.assertEqual(parse_c_verdict("B", m, ("TRUE", "FALSE"))["status"], "VALID")
        self.assertEqual(parse_c_verdict("TRUE", m, ("TRUE", "FALSE"))["status"], "INVALID")  # letters only, no coercion
        self.assertEqual(parse_c_verdict("", m, ("TRUE", "FALSE"), truncated=True)["status"], "TRUNCATED")
        self.assertIsNone(parse_c_verdict("A,B", m, ("TRUE", "FALSE"))["semantic_label"])
        with self.assertRaises(ValueError):
            parse_c_verdict("A", {"A": "TRUE", "B": "FALSE", "C": "TRUE"}, ("TRUE", "FALSE"))
        with self.assertRaises(ValueError):
            parse_c_verdict("A", {"A": "YES", "B": "NO"}, ("TRUE", "FALSE"))
        with self.assertRaises(ValueError):
            parse_c_verdict("A", m, ("CONFIRM", "REJECT"))

    def test_namespace_disjoint_and_combined_validation(self):
        existing = [json.loads(l) for l in (ROOT / "artifacts/data/pilot.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        c = build_c_pilot()
        for key in ("example_id", "family_id", "world_id"):
            self.assertFalse({e[key] for e in existing} & {e[key] for e in c}, msg=key)
        result = validate_dataset(existing + c)
        self.assertTrue(result["gold_verified"])
        self.assertFalse(result["cross_split_leakage"])
        self.assertEqual(result["examples"], len(existing) + len(c))


if __name__ == "__main__":
    unittest.main()
