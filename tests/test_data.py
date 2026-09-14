from __future__ import annotations

import copy
import itertools
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from minicpm_research.data import RULES, build_pilot, render_example
from minicpm_research.verifier import VERDICTS, parse_verdict, validate_dataset, verify_example


class PilotDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.examples = build_pilot()

    def test_default_counts_and_independent_gold(self) -> None:
        report = validate_dataset(self.examples)
        self.assertEqual(report["examples"], 600)
        self.assertEqual(report["families"], 180)
        self.assertEqual(report["splits"], ["pilot"])
        self.assertEqual(Counter(example["task"] for example in self.examples), {"V": 360, "T": 240})
        self.assertTrue(all(example["human_gold_audit"] == "pending" for example in self.examples))

    def test_deterministic_and_seed_changes_worlds(self) -> None:
        self.assertEqual(self.examples, build_pilot())
        self.assertNotEqual(build_pilot(1, 4, 1), build_pilot(2, 4, 1))
        self.assertEqual([e for e in build_pilot(1, 4, 1) if e["task"] == "T"], [e for e in build_pilot(1, 8, 1) if e["task"] == "T"])

    def test_label_permutations_balanced_within_each_rule(self) -> None:
        counts: dict[str, Counter] = defaultdict(Counter)
        for example in self.examples:
            if example["task"] == "V" and example["variant"] == "CONFIRM":
                counts[example["rule"]][tuple(example["label_map"].values())] += 1
        self.assertEqual(set(counts), set(RULES))
        for counter in counts.values():
            self.assertEqual(set(counter), set(itertools.permutations(VERDICTS)))
            self.assertEqual(set(counter.values()), {5})

    def test_gold_cannot_be_derived_from_variant_or_existing_gold(self) -> None:
        for example in self.examples:
            altered = copy.deepcopy(example)
            altered["variant"], altered["gold"] = "MISLEADING", "MISLEADING"
            self.assertEqual(verify_example(altered), example["gold"])

    def test_wrong_gold_and_unsupported_task_fail(self) -> None:
        altered = copy.deepcopy(self.examples)
        altered[0]["gold"] = "REJECT"
        with self.assertRaisesRegex(ValueError, "gold mismatch"):
            validate_dataset(altered)
        with self.assertRaises(ValueError):
            verify_example({"task": "S", "gold": "REFUSE"})

    def test_unknowns_can_support_decisive_results(self) -> None:
        rejected = next(e for e in self.examples if e.get("rule") == "all_samples_pass" and e["gold"] == "REJECT")
        self.assertIn(None, rejected["evidence"]["records"].values())
        confirmed = next(e for e in self.examples if e.get("rule") == "boolean_program" and e["gold"] == "CONFIRM")
        self.assertIsNone(confirmed["evidence"]["trained"])
        self.assertEqual(verify_example(confirmed), "CONFIRM")
        inventory = copy.deepcopy(next(e for e in self.examples if e.get("rule") == "inventory_threshold"))
        inventory["claim"]["minimum"] = 10
        inventory["evidence"]["counts"] = [9, 9, None]
        self.assertEqual(verify_example(inventory), "CONFIRM")
        inventory["evidence"]["counts"] = [0, 0, None]
        self.assertEqual(verify_example(inventory), "REJECT")
        inventory["evidence"]["counts"] = [9, 0, None]
        self.assertEqual(verify_example(inventory), "ABSTAIN")

    def test_boundary_and_invalid_evidence(self) -> None:
        example = copy.deepcopy(next(e for e in self.examples if e.get("rule") == "timetable_before_deadline"))
        example["evidence"]["duration"] = example["claim"]["deadline"] - example["evidence"]["departure"]
        self.assertEqual(verify_example(example), "CONFIRM")
        example["evidence"]["duration"] = True
        with self.assertRaises(ValueError):
            verify_example(example)

    def test_split_family_leak_and_rekeyed_world_leak(self) -> None:
        for rekey in (False, True):
            examples = copy.deepcopy(self.examples)
            duplicate = copy.deepcopy(examples[0])
            duplicate["example_id"] += "-translation"
            duplicate["split"] = "test_A"
            if rekey:
                duplicate["family_id"] += "-renamed"
            with self.assertRaisesRegex(ValueError, "leaks across splits"):
                validate_dataset(examples + [duplicate])

    def test_missing_duplicate_and_mapping_changed_conditions(self) -> None:
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            validate_dataset(self.examples[1:])
        with self.assertRaisesRegex(ValueError, "Duplicate example_id"):
            validate_dataset(self.examples + [self.examples[0]])
        altered = copy.deepcopy(self.examples)
        altered[1]["label_map"]["A"], altered[1]["label_map"]["B"] = altered[1]["label_map"]["B"], altered[1]["label_map"]["A"]
        with self.assertRaisesRegex(ValueError, "mapping changed"):
            validate_dataset(altered)

    def test_rekeying_world_inside_split_cannot_inflate_independent_families(self) -> None:
        altered = copy.deepcopy(self.examples)
        for example in copy.deepcopy(self.examples[:3]):
            example["example_id"] += "-copy"
            example["family_id"] += "-copy"
            altered.append(example)
        with self.assertRaisesRegex(ValueError, "one semantic family"):
            validate_dataset(altered)

    def test_render_does_not_leak_gold_ids_or_hidden_catalog(self) -> None:
        for example in self.examples:
            prompt = json.dumps(render_example(example))
            self.assertNotIn(example["example_id"], prompt)
            self.assertNotIn('"gold"', prompt)
            self.assertNotIn('"variant"', prompt)
            if example["task"] == "T" and example["sandbox_state"]["target_item_id"] is None:
                hidden_id = next(iter(example["sandbox_state"]["stock"]))
                self.assertNotIn(hidden_id, prompt)
                self.assertNotIn('"catalog"', prompt)

    def test_sizes_reject_bool_negative_and_empty_allowed(self) -> None:
        for bad in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                build_pilot(verdict_families=bad)
        self.assertEqual(build_pilot(1, 0, 0), [])

    def test_parser_preserves_invalid_truncation_and_looping(self) -> None:
        mapping = {"A": "CONFIRM", "B": "REJECT", "C": "ABSTAIN"}
        for raw in ("A A A", "A because...", "ABSTAIN", "", "<think>A</think>A", "```A```", "A\nB"):
            parsed = parse_verdict(raw, mapping)
            self.assertEqual(parsed["status"], "INVALID")
            self.assertIsNone(parsed["semantic_label"])
            self.assertEqual(parsed["raw_text"], raw)
        self.assertEqual(parse_verdict(" C\n", mapping)["semantic_label"], "ABSTAIN")
        self.assertEqual(parse_verdict("C", mapping, truncated=True)["status"], "TRUNCATED")
        self.assertIsNone(parse_verdict("C", mapping, truncated=True)["semantic_label"])
        with self.assertRaises(ValueError):
            parse_verdict("A", {"A": "CONFIRM", "B": "CONFIRM", "C": "ABSTAIN"})

    def test_cli_resume_and_refuse_overwrite(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "make_pilot_data.py"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pilot.jsonl"
            command = [sys.executable, str(script), "--output", str(output), "--verdict-families", "4", "--tool-families", "1", "--seed", "1"]
            first = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(first.returncode, 0, first.stderr)
            original = output.read_bytes()
            second = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(original, output.read_bytes())
            failed = subprocess.run(command[:-1] + ["2"], capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(original, output.read_bytes())
            manifest = json.loads(output.with_suffix(".jsonl.manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["sealed_test_created"])
            self.assertEqual(manifest["validation"]["examples"], 16)


if __name__ == "__main__":
    unittest.main()
