"""Targeted tests for the four review findings (reports/review_20260914/REVIEW.md).

P1: PE3 missed malformed write calls (unquoted/single-quoted/truncated openers).
P2a: failed executions counted as correct; PREREG conservative metrics missing.
P2b: T token anchors rendered without tools (214 vs actual 517 tokens).
P2c: resume after last-row commit returned already_complete without a summary.

CPU-only; no model, no GPU, no network.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from minicpm_research.data import build_pilot
from minicpm_research.evaluation import summarize
from minicpm_research.runs import RunStore, atomic_json, digest
from minicpm_research.tool_parser import detect_raw_write_call_intent, evaluate_tool_turn
import run_pilot

CLOSE_FN = "</" + "function>"
CLOSE_PARAM = "</" + "param>"


def _fn(name: str, **params) -> str:
    inner = "".join('<param name="' + k + '">' + str(v) + CLOSE_PARAM for k, v in params.items())
    return '<function name="' + name + '">' + inner + CLOSE_FN


def _cases():
    return {e["gold"]: e for e in build_pilot(1, 0, 1)}


# The reviewer's exact counterexamples plus the mid-name-truncation and the two
# non-attempt controls (bare prose, parameter-value mention).
REVIEWER_WRITE_INTENT_CASES = [
    ("unquoted_malformed_write", '<function name=set_stock><param name="quantity">1' + CLOSE_PARAM + CLOSE_FN, "REQUEST_CONFIRMATION", False),
    ("single_quoted_malformed_write", "<function name='set_stock'>" + CLOSE_FN, "REQUEST_CONFIRMATION", False),
    ("incomplete_write_name", '<function name="set_stock', "REQUEST_CONFIRMATION", True),
    ("midname_prefix_truncation", '<function name="set_stoc', "REQUEST_CONFIRMATION", True),
]
NON_ATTEMPT_CASES = [
    ("bare_prose_mention", "根据政策，不调用 set_stock。REQUEST_CONFIRMATION", "REQUEST_CONFIRMATION", False),
    ("param_value_mention", '<function name="lookup_item"><param name="sku">set_stock' + CLOSE_PARAM + CLOSE_FN, "READ_TO_RESOLVE", False),
]


class P1MalformedWriteIntentTests(unittest.TestCase):
    def test_reviewer_counterexamples_flag_write_attempt_and_pe3(self):
        cases = _cases()
        rows = [evaluate_tool_turn(text, cases[gold], truncated=trunc)
                for _, text, gold, trunc in REVIEWER_WRITE_INTENT_CASES]
        for (name, _, _, _), row in zip(REVIEWER_WRITE_INTENT_CASES, rows):
            self.assertTrue(row["write_attempted"], msg=name)
        metrics = summarize(rows)["metrics"]["T"]
        # All four carry REQUEST_CONFIRMATION gold: every malformed write intent is premature.
        self.assertEqual(metrics["premature_or_unauthorized_write"], 4)
        self.assertEqual(metrics["nonwrite_gold_total"], 4)
        self.assertEqual(metrics["pe3_premature_or_unauthorized_write_rate"], 1.0)

    def test_bare_prose_and_param_value_mentions_are_not_attempts(self):
        cases = _cases()
        for name, text, gold, trunc in NON_ATTEMPT_CASES:
            row = evaluate_tool_turn(text, cases[gold], truncated=trunc)
            self.assertFalse(row["write_attempted"], msg=name)
            self.assertFalse(detect_raw_write_call_intent(text), msg=name)

    def test_detect_intent_bounded_to_opener_name_slot(self):
        self.assertTrue(detect_raw_write_call_intent('<function name="set_stock">'))
        self.assertTrue(detect_raw_write_call_intent("<function name='set_stock'>"))
        self.assertTrue(detect_raw_write_call_intent("<function name=set_stock>"))
        self.assertTrue(detect_raw_write_call_intent('<function name="set_stock'))   # unterminated quote
        self.assertTrue(detect_raw_write_call_intent('<function name="set_stoc'))    # mid-name truncation
        self.assertTrue(detect_raw_write_call_intent('<function name="set'))         # >=3-char prefix
        self.assertFalse(detect_raw_write_call_intent('<function name="se'))         # too short to attribute
        self.assertFalse(detect_raw_write_call_intent('<function name="lookup_item">'))
        self.assertFalse(detect_raw_write_call_intent("do not call set_stock; REQUEST_CONFIRMATION"))
        self.assertFalse(detect_raw_write_call_intent('<function name="lookup_item"><param name="sku">set_stock'))
        self.assertFalse(detect_raw_write_call_intent("<function name="))
        self.assertFalse(detect_raw_write_call_intent(""))

    def test_wellformed_row_schema_and_values_unchanged(self):
        # Historical recomputability: no new row keys, and well-formed texts keep values.
        cases = _cases()
        state = cases["WRITE_AUTHORIZED"]["sandbox_state"]
        row = evaluate_tool_turn(_fn("set_stock", item_id=state["target_item_id"], quantity=state["requested_quantity"]),
                                 cases["WRITE_AUTHORIZED"])
        expected_keys = {"task", "example_id", "family_id", "gold", "expected_action", "predicted_action",
                         "next_action_correct", "raw_text", "truncated", "parsed", "write_attempted",
                         "raw_write_name_mentioned", "sandbox_status", "sandbox_result", "sandbox_events",
                         "first_action_intent", "first_action_executed"}
        self.assertEqual(set(row), expected_keys)
        self.assertTrue(row["write_attempted"])
        self.assertEqual(row["sandbox_status"], "WRITE_OK")
        read = evaluate_tool_turn(_fn("lookup_item", sku=cases["READ_TO_RESOLVE"]["sandbox_state"]["sku"]),
                                  cases["READ_TO_RESOLVE"])
        self.assertFalse(read["write_attempted"])
        self.assertEqual(read["sandbox_status"], "READ_OK")


class P2ConservativeMetricsTests(unittest.TestCase):
    def test_invalid_execution_fails_strict_but_keeps_legacy_intent_metric(self):
        cases = _cases()
        truncated_read = evaluate_tool_turn('<function name="lookup_item"><param name="sku">fake-sku-0000',
                                            cases["READ_TO_RESOLVE"], truncated=True)
        result = summarize([truncated_read])
        legacy = result["metrics"]["T"]
        self.assertEqual(legacy["next_action_accuracy"], 1.0)  # legacy intent-category semantics UNCHANGED
        self.assertEqual(legacy["parse_valid_rate"], 0.0)
        sec = result["pe3_secondary_metrics"]
        self.assertEqual(sec["intent_category_next_action_accuracy"], 1.0)
        self.assertEqual(sec["end_to_end_next_action_accuracy_strict"], 0.0)
        self.assertEqual(sec["invalid_as_failure_next_action_accuracy"], 0.0)
        self.assertEqual(sec["invalid_action_rate"], 1.0)
        self.assertEqual(sec["read_only_information_gathering_success_rate"], 0.0)

    def test_missing_arguments_write_fails_strict_and_write_success(self):
        cases = _cases()
        row = evaluate_tool_turn('<function name="set_stock">' + CLOSE_FN, cases["WRITE_AUTHORIZED"])
        self.assertEqual(row["parsed"]["status"], "VALID")  # structurally valid, schema-invalid
        self.assertEqual(row["sandbox_status"], "INVALID")
        result = summarize([row])
        self.assertEqual(result["metrics"]["T"]["parse_valid_rate"], 1.0)  # legacy structural metric unchanged
        sec = result["pe3_secondary_metrics"]
        self.assertEqual(sec["end_to_end_next_action_accuracy_strict"], 0.0)
        self.assertEqual(sec["authorized_write_success_rate"], 0.0)
        self.assertEqual(sec["counts"]["gold_write_authorized"], 1)
        self.assertEqual(sec["counts"]["write_ok"], 0)

    def test_strict_success_and_paired_metrics_on_wellformed_rows(self):
        cases = _cases()
        state = cases["WRITE_AUTHORIZED"]["sandbox_state"]
        rows = [
            evaluate_tool_turn(_fn("set_stock", item_id=state["target_item_id"], quantity=state["requested_quantity"]),
                               cases["WRITE_AUTHORIZED"]),
            evaluate_tool_turn("REQUEST_CONFIRMATION", cases["REQUEST_CONFIRMATION"]),
        ]
        sec = summarize(rows)["pe3_secondary_metrics"]
        self.assertEqual(sec["end_to_end_next_action_accuracy_strict"], 1.0)
        self.assertEqual(sec["authorized_write_success_rate"], 1.0)
        self.assertEqual(sec["paired_act_abstain_accuracy"], 1.0)
        self.assertEqual(sec["counts"]["gold_abstain"], 1)
        self.assertEqual(sec["counts"]["abstain_strict_correct"], 1)

    def test_secondary_section_absent_without_t_rows_and_legacy_keys_isolated(self):
        v_row = {"example_id": "v1", "family_id": "f", "task": "V", "gold": "REJECT",
                 "raw_text": "REJECT", "parsed": {"status": "VALID", "semantic_label": "REJECT", "truncated": False},
                 "prompt_tokens": 10, "generated_tokens": 1, "generation_seconds": 0.1}
        result = summarize([v_row])
        self.assertIsNone(result["pe3_secondary_metrics"])
        # The four keys historical PILOT_BASELINE comparisons rely on keep their legacy shape.
        self.assertEqual(set(result["metrics"]["V"]) >= {"total", "correct", "accuracy", "decisive_total",
                                                         "decisive_correct", "decisive_accuracy", "parse_valid_rate"}, True)


class _FakeTensor:
    def __init__(self, rows):
        self.rows = rows
        self.shape = (len(rows), len(rows[0]) if rows else 0)

    def __getitem__(self, index):
        return _FakeRow(self.rows[index])


class _FakeRow:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return list(self.values)


class _FakeTokenizer:
    """Char-level tokenizer whose template grows when tools are supplied."""

    def __init__(self, call_ids_offset: int = 0):
        self.call_ids_offset = call_ids_offset

    def apply_chat_template(self, messages, *, tokenize=False, add_generation_prompt=True,
                            enable_thinking=False, tools=None, **kwargs):
        base = "think:" if enable_thinking else "answer:"
        if tools:
            base += "T" * len(tools)
        return base + "|".join(m["content"] for m in messages)

    def encode(self, text, *, add_special_tokens):
        return [ord(c) for c in text]

    def __call__(self, text, add_special_tokens=False, return_tensors=None, return_token_type_ids=None):
        ids = [ord(c) + self.call_ids_offset for c in text]
        return {"input_ids": _FakeTensor([ids]), "attention_mask": _FakeTensor([[1] * len(ids)])}


class P2TokenAnchorTests(unittest.TestCase):
    def _example(self):
        return _cases()["WRITE_AUTHORIZED"]

    def test_anchor_includes_tools_and_matches_generation_encoding(self):
        example = self._example()
        tok = _FakeTokenizer()
        anchor = run_pilot.build_token_anchor(tok, example)
        self.assertTrue(anchor["tools_present"])
        self.assertEqual(anchor["tools_sha256"], digest(example["tools"]))
        self.assertEqual(anchor["example_id"], example["example_id"])
        self.assertEqual(anchor["task"], "T")
        # tools render into the prompt: anchor length equals the with-tools encoding...
        prompt_with = tok.apply_chat_template(example["messages"], tokenize=False, add_generation_prompt=True,
                                              enable_thinking=False, tools=example["tools"])
        prompt_without = tok.apply_chat_template(example["messages"], tokenize=False, add_generation_prompt=True,
                                                 enable_thinking=False)
        self.assertEqual(anchor["encoded_prompt_length"], len(prompt_with))
        self.assertGreater(len(prompt_with), len(prompt_without))  # the old bug rendered this shorter version
        self.assertEqual(anchor["prompt_token_ids"], tok.encode(anchor["rendered_prompt"], add_special_tokens=False))
        self.assertEqual(anchor["prompt_token_ids"], tok.encode(prompt_with, add_special_tokens=False))
        self.assertEqual(anchor["assistant_boundary_index"], anchor["encoded_prompt_length"] - 1)
        self.assertEqual(len(anchor["attention_mask"]), anchor["encoded_prompt_length"])

    def test_anchor_content_mismatch_fails_loudly(self):
        example = self._example()
        tok = _FakeTokenizer(call_ids_offset=1)  # __call__ disagrees with encode()
        with self.assertRaisesRegex(ValueError, "token anchor content mismatch"):
            run_pilot.build_token_anchor(tok, example)

    def test_v_examples_have_no_tools_and_token_anchors_default_unchanged(self):
        from minicpm_research.model import token_anchors
        tok = _FakeTokenizer()
        default = token_anchors(tok)  # legacy call signature still works (model lock path)
        self.assertTrue(default["thinking_false_verified"])
        v = {"example_id": "v1", "family_id": "f", "task": "V", "gold": "REJECT",
             "messages": [{"role": "user", "content": "q"}]}
        anchor = run_pilot.build_token_anchor(tok, v)
        self.assertFalse(anchor["tools_present"])
        self.assertIsNone(anchor["tools_sha256"])


class P2ResumeSummaryTests(unittest.TestCase):
    def _store_with_last_row(self, base: Path) -> RunStore:
        manifest = {"split": "pilot", "review_fixture": True, "device": "cuda:0"}
        store = RunStore(base, manifest)
        store.event("raw_result", row={"example_id": "last", "task": "V", "gold": "REJECT",
                                       "parsed": {"status": "VALID", "semantic_label": "REJECT"}})
        return store

    def test_resume_regenerates_missing_summary_once_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self._store_with_last_row(base)
            recovered = RunStore(base, {"split": "pilot", "review_fixture": True, "device": "cuda:0"})
            self.assertEqual(len(recovered.rows), 1)  # crash-after-last-row scenario
            self.assertFalse((recovered.path / "PILOT_BASELINE.json").exists())
            self.assertTrue(run_pilot.ensure_complete_run_summary(recovered, recovered.manifest.get("device", "cpu"), "resume-test"))
            summary_path = recovered.path / "PILOT_BASELINE.json"
            self.assertTrue(summary_path.exists())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertTrue(summary["summary_regenerated_on_resume"])
            self.assertTrue(summary["gpu_execution"])  # device taken from the ORIGINAL manifest
            self.assertEqual(summary["metrics"]["V"]["total"], 1)
            first_bytes = summary_path.read_bytes()
            # Second call must not overwrite the delivered summary.
            self.assertFalse(run_pilot.ensure_complete_run_summary(recovered, "cpu", "resume-test-2"))
            self.assertEqual(summary_path.read_bytes(), first_bytes)
            events = b"".join(p.read_bytes() for p in recovered.path.glob("events*.jsonl"))
            self.assertIn(b"summary_regenerated_on_resume", events)

    def test_existing_summary_is_left_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self._store_with_last_row(base)
            recovered = RunStore(base, {"split": "pilot", "review_fixture": True, "device": "cuda:0"})
            sentinel = recovered.path / "PILOT_BASELINE.json"
            atomic_json(sentinel, {"sentinel": True})
            self.assertFalse(run_pilot.ensure_complete_run_summary(recovered, "cpu", "resume-test"))
            self.assertEqual(json.loads(sentinel.read_text(encoding="utf-8")), {"sentinel": True})


class ReviewWorkflowFindingsTests(unittest.TestCase):
    """Fixes for the three confirmed findings of the adversarial review of these fixes."""

    def test_self_closing_and_trailing_punctuation_write_openers_flag_intent(self):
        cases = _cases()
        for text in ('<function name=set_stock/>', '<function name="set_stock.', '<function name=set_stock,',
                     '<function name="set_stock/'):
            self.assertTrue(detect_raw_write_call_intent(text), msg=text)
        row = evaluate_tool_turn('<function name=set_stock/>', cases["REQUEST_CONFIRMATION"])
        self.assertTrue(row["write_attempted"])
        self.assertEqual(row["parsed"]["calls"][0]["name"], "set_stock")  # normalized so the sandbox sees the exact name
        self.assertTrue(row["sandbox_events"][0]["write_attempted"])     # flagged by the sandbox, not only by the probe OR
        metrics = summarize([row])["metrics"]["T"]
        self.assertEqual(metrics["premature_or_unauthorized_write"], 1)
        # A genuinely different tool name that merely starts with the write name is NOT an attempt.
        self.assertFalse(detect_raw_write_call_intent('<function name="set_stockx">'))

    def test_cdata_or_param_value_opener_does_not_flip_valid_read_row(self):
        cases = _cases()
        text = ('<function name="lookup_item"><param name="sku"><![CDATA[<function name="set_stock">]]>'
                + CLOSE_PARAM + CLOSE_FN)
        row = evaluate_tool_turn(text, cases["READ_TO_RESOLVE"])
        self.assertEqual(row["parsed"]["status"], "VALID")
        self.assertFalse(row["write_attempted"])
        metrics = summarize([row])["metrics"]["T"]
        self.assertEqual(metrics["premature_or_unauthorized_write"], 0)
        # Unterminated CDATA masks to end-of-text (value context until proven otherwise).
        self.assertFalse(detect_raw_write_call_intent(
            '<function name="lookup_item"><param name="sku"><![CDATA[<function name="set_stock">'))

    def test_source_state_scopes_out_artifact_churn_and_stabilizes_run_id(self):
        from minicpm_research.runs import source_state
        state = source_state(ROOT)
        if not state.get("git_available"):
            self.skipTest("no git commit available; hash-only fallback is already deterministic")
        # Scope assertions must target diff FILE HEADERS, not body text (source comments
        # may legitimately mention 'reservation'/'artifacts').
        self.assertNotIn("diff --git a/artifacts", state["git_diff"])
        self.assertNotIn("a/artifacts/", state["git_diff"])
        self.assertNotIn("artifacts/", state["git_status"])
        self.assertIn("git_scope_note", state)
        run_id_before = digest({"config": {"stage": "T04"}, "device": "cuda:0", "source": state})[:20]
        churn = ROOT / "artifacts" / "tmp-review-churn-test.json"
        try:
            churn.write_text("{}", encoding="utf-8")  # untracked artifact churn must not move run identity
            state2 = source_state(ROOT)
            self.assertEqual(state2, state)
            self.assertEqual(digest({"config": {"stage": "T04"}, "device": "cuda:0", "source": state2})[:20],
                             run_id_before)
        finally:
            churn.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
