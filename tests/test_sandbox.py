from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from minicpm_research.data import build_pilot
from minicpm_research.sandbox import Sandbox, parse_action_json


class SandboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.examples = {example["gold"]: example for example in build_pilot(1, 0, 1)}

    def world(self, gold: str) -> Sandbox:
        return Sandbox(self.examples[gold]["sandbox_state"])

    def write(self, sandbox: Sandbox) -> dict:
        state = sandbox.state
        return {"name": "set_stock", "arguments": {"item_id": next(iter(state["stock"])), "quantity": state["requested_quantity"]}}

    def test_four_gold_next_steps(self) -> None:
        for gold, example in self.examples.items():
            sandbox = Sandbox(example["sandbox_state"])
            if gold == "WRITE_AUTHORIZED":
                action, expected_status = self.write(sandbox), "WRITE_OK"
            elif gold == "READ_TO_RESOLVE":
                action, expected_status = {"name": "lookup_item", "arguments": {"sku": sandbox.state["sku"]}}, "READ_OK"
            else:
                action, expected_status = {"name": "request_confirmation" if gold == "REQUEST_CONFIRMATION" else "clarify", "arguments": {}}, "REQUEST_OK"
            event = sandbox.execute(action, raw_intent="synthetic model action")
            self.assertEqual(event["status"], expected_status)
            self.assertEqual(event["gold_next_before"], gold)
            self.assertEqual(Sandbox.replay(example["sandbox_state"], sandbox.events).state, sandbox.state)

    def test_block_all_premature_writes_and_record_attempt(self) -> None:
        for gold in ("REQUEST_CONFIRMATION", "READ_TO_RESOLVE", "CLARIFY_MISSING_INFORMATION"):
            sandbox = self.world(gold)
            before = sandbox.state
            event = sandbox.execute(self.write(sandbox), raw_intent="set_stock")
            self.assertEqual(event["status"], "BLOCKED")
            self.assertTrue(event["write_attempted"])
            self.assertEqual(sandbox.state, before)

    def test_read_then_write_and_requests_do_not_grant_permission(self) -> None:
        sandbox = self.world("READ_TO_RESOLVE")
        stock = sandbox.state["stock"]
        event = sandbox.execute({"name": "lookup_item", "arguments": {"sku": sandbox.state["sku"]}})
        self.assertEqual(event["status"], "READ_OK")
        self.assertEqual(sandbox.state["stock"], stock)
        self.assertEqual(sandbox.execute(self.write(sandbox))["status"], "WRITE_OK")
        confirmation = self.world("REQUEST_CONFIRMATION")
        confirmation.execute({"name": "request_confirmation", "arguments": {}})
        self.assertEqual(confirmation.execute(self.write(confirmation))["status"], "BLOCKED")

    def test_bad_parameters_and_unavailable_tools_cannot_mutate(self) -> None:
        sandbox = self.world("WRITE_AUTHORIZED")
        before = sandbox.state
        for value in (True, -1, 10000, "10"):
            action = self.write(sandbox)
            action["arguments"]["quantity"] = value
            self.assertNotEqual(sandbox.execute(action)["status"], "WRITE_OK")
            self.assertEqual(sandbox.state, before)
        sandbox = self.world("CLARIFY_MISSING_INFORMATION")
        self.assertEqual(sandbox.execute({"name": "lookup_item", "arguments": {"sku": sandbox.state["sku"]}})["status"], "BLOCKED")

    def test_parser_invalid_truncated_and_duplicate_json_keys(self) -> None:
        for raw in ('{"name":"set_stock","arguments":', '{"name":"set_stock","name":"lookup_item","arguments":{}}', '[]', '```json\n{}\n```'):
            parsed = parse_action_json(raw)
            self.assertEqual(parsed["status"], "INVALID")
            self.assertEqual(parsed["raw_text"], raw)
        raw = '{"name":"set_stock","arguments":{"item_id":"fake-x","quantity":4}}'
        parsed = parse_action_json(raw, truncated=True)
        self.assertEqual(parsed["status"], "TRUNCATED")
        self.assertTrue(parsed["raw_write_name_mentioned"])
        self.assertFalse(parsed["native_parser_verified"])
        sandbox = self.world("WRITE_AUTHORIZED")
        before = sandbox.state
        event = sandbox.execute(self.write(sandbox), raw_intent=raw, parser_result=parsed)
        self.assertEqual(event["status"], "INVALID")
        self.assertEqual(sandbox.state, before)
        self.assertEqual(event["parser_result"], parsed)

    def test_retry_limit_and_replay_tamper_detection(self) -> None:
        state = self.examples["REQUEST_CONFIRMATION"]["sandbox_state"]
        sandbox = Sandbox(state, max_steps=1)
        action = {"name": "request_confirmation", "arguments": {}}
        sandbox.execute(action)
        self.assertEqual(sandbox.execute(action)["status"], "RETRY_LIMIT")
        self.assertEqual(Sandbox.replay(state, sandbox.events, max_steps=1).state, sandbox.state)
        tampered = copy.deepcopy(sandbox.events)
        tampered[0]["status"] = "WRITE_OK"
        with self.assertRaisesRegex(ValueError, "Replay diverged"):
            Sandbox.replay(state, tampered, max_steps=1)

    def test_defensive_copy_and_reject_non_offline(self) -> None:
        state = copy.deepcopy(self.examples["WRITE_AUTHORIZED"]["sandbox_state"])
        sandbox = Sandbox(state)
        state["stock"].clear()
        self.assertTrue(sandbox.state["stock"])
        snapshot = sandbox.state
        snapshot["stock"].clear()
        self.assertTrue(sandbox.state["stock"])
        state["offline"] = False
        with self.assertRaises(ValueError):
            Sandbox(state)


if __name__ == "__main__":
    unittest.main()
