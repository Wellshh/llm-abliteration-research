import json
import tempfile
import unittest
from pathlib import Path

from minicpm_research.runs import RunStore
from minicpm_research.evaluation import summarize


class RunTests(unittest.TestCase):
    def test_resume_and_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = {"model": "fixed", "split": "pilot"}
            first = RunStore(Path(temp), manifest)
            first.commit([{"example_id": "one", "raw_text": "INVALID"}])
            restored = RunStore(Path(temp), manifest)
            self.assertEqual(restored.rows, first.rows)
            with self.assertRaises(ValueError):
                restored.commit([{"example_id": "one"}])
            shard = next(first.path.glob("shard-*.json"))
            payload = json.loads(shard.read_text())
            payload["rows"][0]["raw_text"] = "tampered"
            shard.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                RunStore(Path(temp), manifest)

    def test_invalid_denominator(self):
        rows = [{"task": "V", "gold": "REJECT", "parsed": {"status": state, "semantic_label": label}}
                for state, label in [("VALID", "REJECT"), ("INVALID", None), ("TRUNCATED", None)]]
        report = summarize(rows)
        self.assertEqual(report["metrics"]["V"]["accuracy"], 1 / 3)
        self.assertEqual(report["confusion"]["V:REJECT"]["TRUNCATED"], 1)


if __name__ == "__main__":
    unittest.main()
