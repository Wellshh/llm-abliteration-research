"""Real token-by-token C KV/full diagnostic tests; CPU tiny model, no GPU, no model lock.

These verify the corrected check_hooks.py A/B/C comparison:
  * C really executes one forward per input token through a persistent, growing
    cache (independently observed via a forward pre-hook, not trusting the
    recorded C_call_sequence), and is not a copy of B;
  * left-padding, position_ids and cache_position are correct at every step;
  * a failed numerical control still persists the full structured diagnostic;
  * an existing output file is never overwritten.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SCRIPTS = ROOT / "scripts"

HAS_TORCH = importlib.util.find_spec("torch") is not None
HAS_TRANSFORMERS = importlib.util.find_spec("transformers") is not None
SEQ_LEN = 4   # input tokens per row before the decoded next token
ROWS = 2


def _load_check_hooks():
    spec = importlib.util.spec_from_file_location("check_hooks_under_test", SCRIPTS / "check_hooks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if HAS_TORCH and HAS_TRANSFORMERS:
    import torch
    from transformers import LlamaConfig, LlamaForCausalLM

    ch = _load_check_hooks()

    def tiny_model(dtype=torch.bfloat16, vocab: int = 64):
        torch.manual_seed(17)
        cfg = LlamaConfig(vocab_size=vocab, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                          num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=128,
                          pad_token_id=0, bos_token_id=1, eos_token_id=2, attention_dropout=0.0)
        cfg._attn_implementation = "eager"
        return LlamaForCausalLM(cfg).to(dtype=dtype).eval()

    def spy_forwards(model):
        """Record every top-level forward's shapes/cache state; returns (records, handle)."""
        records: list[dict] = []

        def pre_hook(_module, _args, kwargs):
            ids = kwargs.get("input_ids")
            pv = kwargs.get("past_key_values")
            cp = kwargs.get("cache_position")
            records.append({
                "ids_shape": tuple(ids.shape) if ids is not None else None,
                "cache_position": cp.detach().cpu().tolist() if cp is not None else None,
                "use_cache": kwargs.get("use_cache"),
                "incoming_cache_len": int(pv.get_seq_length()) if pv is not None and hasattr(pv, "get_seq_length") else None,
            })
        return records, model.register_forward_pre_hook(pre_hook, with_kwargs=True)


@unittest.skipUnless(HAS_TORCH and HAS_TRANSFORMERS, "requires torch + transformers for the tiny-model numerical control")
class RealTokenwiseCTests(unittest.TestCase):
    def test_C_executes_token_by_token_with_growing_cache_not_copy_of_B(self):
        model = tiny_model()
        records, handle = spy_forwards(model)
        try:
            result = ch.run_checks(model, "cpu")
        finally:
            handle.remove()
        self.assertEqual(result["status"], "passed")
        # Independently isolate C's token-by-token prefill steps: a single-token
        # forward whose cache_position is strictly inside the prompt (< SEQ_LEN).
        # B's prefill is one 4-token call (cache_position None) and B's decode uses
        # cache_position [SEQ_LEN]; nothing else uses single-token cache_position < SEQ_LEN.
        tokenwise = [r for r in records
                     if r["ids_shape"] is not None and r["ids_shape"][1] == 1
                     and r["cache_position"] is not None and max(r["cache_position"]) < SEQ_LEN]
        # batched C (SEQ_LEN steps) + single-row C (ROWS * SEQ_LEN steps)
        self.assertEqual(len(tokenwise), SEQ_LEN * (1 + ROWS))
        # The cache fed into each C sequence must grow 0 -> 1 -> 2 -> 3 (persistent cache).
        incoming = sorted(r["incoming_cache_len"] for r in tokenwise)
        self.assertEqual(incoming, sorted([0, 1, 2, 3] * (1 + ROWS)))
        # The recorded call sequence must agree: 4 prefill_token + 1 decode_next, cache 1..5.
        seq = result["kv_full_diagnostics"]["C_call_sequence"]
        self.assertEqual([s["kind"] for s in seq], ["prefill_token"] * SEQ_LEN + ["decode_next"])
        self.assertEqual([s["cache_len_after"] for s in seq], [1, 2, 3, 4, 5])
        self.assertEqual([s["cache_position"] for s in seq], [0, 1, 2, 3, 4])
        self.assertTrue(all(s["logits_finite"] for s in seq))
        self.assertTrue(all(s["cache_type"] == "DynamicCache" for s in seq))

    def test_C_is_numerically_independent_path_and_matches_on_cpu(self):
        model = tiny_model()
        diag = ch.run_checks(model, "cpu")["kv_full_diagnostics"]
        # On CPU all three paths are bit-identical for the tiny control model.
        for pair in ("A-B", "A-C", "B-C"):
            for row in diag["batched_pairwise"][pair]:
                self.assertEqual(row["abs_max"], 0.0, msg=f"batched {pair} row {row['row']}")
                self.assertTrue(row["argmax_equal"])
        for sr in diag["single_row"]:
            self.assertEqual(sr["c_cache_lengths_per_step"], [1, 2, 3, 4])
            self.assertEqual(sr["b_prefill_cache_len"], SEQ_LEN)
            self.assertEqual(sr["b_post_decode_cache_len"], SEQ_LEN + 1)
            for pair in ("A-B", "A-C", "B-C"):
                self.assertEqual(sr[pair]["abs_max"], 0.0)
        # B's prefill cache is mutated in place by its decode (4 -> 5); documented, not hidden.
        self.assertEqual(diag["prefill_cache_len"], SEQ_LEN)
        self.assertEqual(diag["b_post_decode_cache_len"], SEQ_LEN + 1)
        self.assertTrue(diag["cache_update_is_in_place"])

    def test_padding_positions_and_cache_position_per_step(self):
        model = tiny_model()
        diag = ch.run_checks(model, "cpu")["kv_full_diagnostics"]
        self.assertEqual(diag["fixed_input_ids"], [[0, 0, 5, 6], [7, 8, 9, 10]])
        self.assertEqual(diag["attention_mask"], [[0, 0, 1, 1], [1, 1, 1, 1]])
        # Left-padding: clamped cumsum positions; row 0 has two leading pad tokens.
        self.assertEqual(diag["position_ids"], [[0, 0, 0, 1], [0, 1, 2, 3]])
        self.assertEqual(diag["extended_mask"], [[0, 0, 1, 1, 1], [1, 1, 1, 1, 1]])
        self.assertEqual(diag["decode_position_ids"], [[2], [4]])
        self.assertEqual(diag["decode_cache_position"], [SEQ_LEN])
        seq = diag["C_call_sequence"]
        for t in range(SEQ_LEN):
            self.assertEqual(seq[t]["mask_prefix_length"], t + 1)
            self.assertEqual(seq[t]["cache_position"], t)
            self.assertEqual(seq[t]["token_column"], t)
            # per-step position_ids equal column t of the full position_ids
            self.assertEqual(seq[t]["position_ids"], [[diag["position_ids"][0][t]], [diag["position_ids"][1][t]]])
        self.assertEqual(seq[SEQ_LEN]["kind"], "decode_next")
        self.assertEqual(seq[SEQ_LEN]["position_ids"], [[2], [4]])
        self.assertEqual(seq[SEQ_LEN]["mask_prefix_length"], SEQ_LEN + 1)

    def test_fixed_next_token_clamped_to_vocab(self):
        # vocab 64 -> 350 clamps to 63; the official checkpoint (vocab 130560) keeps [[49],[350]].
        small = ch.run_checks(tiny_model(vocab=64), "cpu")["kv_full_diagnostics"]
        self.assertEqual(small["next_token_fixed"], [[49], [63]])
        self.assertEqual(small["next_token_selection"], "fixed_[[49],[350]]_clamped_to_vocab_size")
        big = ch.run_checks(tiny_model(vocab=512), "cpu")["kv_full_diagnostics"]
        self.assertEqual(big["next_token_fixed"], [[49], [350]])


@unittest.skipUnless(HAS_TORCH and HAS_TRANSFORMERS, "requires torch + transformers")
class FailureEvidenceTests(unittest.TestCase):
    def test_assertion_failure_embeds_and_recovers_full_diagnostic(self):
        model = tiny_model()
        original_forward = model.forward

        def perturbed(*args, **kwargs):
            out = original_forward(*args, **kwargs)
            ids = kwargs.get("input_ids")
            # Perturb ONLY the full-sequence A path (5 tokens, no cache) so A diverges
            # from B and C beyond the 0.5 tolerance, forcing the real assertion.
            if kwargs.get("use_cache") is False and ids is not None and ids.shape[1] == SEQ_LEN + 1:
                out.logits = out.logits + 1.0
            return out

        model.forward = perturbed
        try:
            with self.assertRaises(AssertionError) as ctx:
                ch.run_checks(model, "cpu")
        finally:
            model.forward = original_forward
        message = str(ctx.exception)
        self.assertIn("structured_diagnostics=", message)
        diag = json.loads(message.split("structured_diagnostics=", 1)[1])
        self.assertEqual(diag["schema"], "kv_full_abc_v2_real_tokenwise_C")
        self.assertEqual(diag["original_threshold"], 0.5)
        self.assertEqual(diag["original_threshold_formula"], "64 * torch.finfo(dtype).eps")
        # A was perturbed; B and C were not, so A-B and A-C exceed tolerance while B-C stays 0.
        self.assertGreater(diag["batched_pairwise"]["A-B"][0]["abs_max"], 0.5)
        self.assertGreater(diag["batched_pairwise"]["A-C"][0]["abs_max"], 0.5)
        self.assertEqual(diag["batched_pairwise"]["B-C"][0]["abs_max"], 0.0)
        self.assertIn("C_call_sequence", diag)
        self.assertEqual(len(diag["C_call_sequence"]), SEQ_LEN + 1)
        self.assertIn("weights_before_sha256", diag)
        self.assertIn("weights_after_sha256", diag)
        # Required evidence "dtype/backend/versions" must ride in the FAILURE-path
        # diagnostic too (run_checks raises before execute() can inject versions).
        self.assertIn("environment", diag)
        for pkg in ("python", "torch", "transformers"):
            self.assertIn(pkg, diag["environment"])
        self.assertEqual(diag["dtype"], "torch.bfloat16")
        self.assertEqual(diag["attention_backend"], "eager")
        # Concern #2: the recoverable diagnostic must carry the early numerical
        # controls + repeat-noise baseline and thresholds, not only A/B/C.
        self.assertIn("numerical_controls", diag)
        self.assertIn("value", diag["numerical_controls"]["baseline_repeat_max_abs"])
        kv = diag["numerical_controls"]["kv_vs_full_last_logit_max_abs"]
        self.assertFalse(kv["passed"])
        self.assertEqual(kv["threshold"], 0.5)
        # The recovery helper used by main() must preserve the evidence and mark it completed.
        result: dict = {}
        ch._recover_diagnostics(result, ctx.exception)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["diagnostic_status"], "completed")
        self.assertEqual(result["kv_full_diagnostics"]["schema"], "kv_full_abc_v2_real_tokenwise_C")

    def test_recover_diagnostics_marks_unparseable_as_failed_to_parse(self):
        result: dict = {}
        ch._recover_diagnostics(result, AssertionError("structured_diagnostics={not json"))
        self.assertEqual(result["diagnostic_status"], "failed_to_parse")
        self.assertNotIn("kv_full_diagnostics", result)

    def test_recover_diagnostics_plain_error_has_no_diagnostic_status(self):
        result: dict = {}
        ch._recover_diagnostics(result, RuntimeError("ordinary failure"))
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("diagnostic_status", result)


@unittest.skipUnless(HAS_TORCH and HAS_TRANSFORMERS, "requires torch + transformers")
class NoOverwriteTests(unittest.TestCase):
    def test_existing_output_file_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "existing_validation.json"
            sentinel = "SENTINEL_DO_NOT_OVERWRITE"
            out.write_text(sentinel, encoding="utf-8")
            argv = ["check_hooks.py", "--device", "cpu", "--output", str(out)]
            with mock.patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit) as ctx:
                    ch.main()
            self.assertEqual(ctx.exception.code, 2)  # argparse parser.error
            self.assertEqual(out.read_text(encoding="utf-8"), sentinel)


@unittest.skipUnless(HAS_TORCH and HAS_TRANSFORMERS, "requires torch + transformers")
class ExploratoryFp32ModeTests(unittest.TestCase):
    """The FP32 control is characterization-only: TF32 off, recorded, non-credential."""

    def setUp(self):
        import torch
        self._saved = (torch.backends.cuda.matmul.allow_tf32,
                       torch.backends.cudnn.allow_tf32,
                       torch.get_float32_matmul_precision())

    def tearDown(self):
        import torch
        torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = self._saved[0], self._saved[1]
        torch.set_float32_matmul_precision(self._saved[2])

    def test_exploratory_fp32_disables_tf32_and_records_both_states(self):
        import torch
        # Force TF32 ON to prove the control turns it OFF and records the change.
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.set_float32_matmul_precision("high")
        args = types.SimpleNamespace(device="cpu", dtype="float32", model_lock=None, gpu_uuid="GPU-x",
                                     budget_gib=32, exploratory_precision_control=True, resource_guard=None,
                                     output=Path("unused.json"))
        result = ch.execute(args)
        pb = result["kv_full_diagnostics"]["precision_backend"]
        self.assertTrue(pb["tf32_disabled_for_fp32_control"])
        self.assertFalse(pb["active_during_run"]["cuda_matmul_allow_tf32"])
        self.assertFalse(pb["active_during_run"]["cudnn_allow_tf32"])
        self.assertEqual(pb["active_during_run"]["float32_matmul_precision"], "highest")
        # default_at_entry preserves the pre-disable state (what the BF16 primary ran under)
        self.assertTrue(pb["default_at_entry"]["cuda_matmul_allow_tf32"])
        self.assertEqual(pb["default_at_entry"]["float32_matmul_precision"], "high")
        self.assertIn("entry_state_note", pb)
        self.assertEqual(result["kv_full_diagnostics"]["dtype"], "torch.float32")

    def test_bf16_primary_path_does_not_claim_tf32_disabled(self):
        args = types.SimpleNamespace(device="cpu", dtype="bfloat16", model_lock=None, gpu_uuid="GPU-x",
                                     budget_gib=32, exploratory_precision_control=False, resource_guard=None,
                                     output=Path("unused.json"))
        result = ch.execute(args)
        pb = result["kv_full_diagnostics"]["precision_backend"]
        self.assertFalse(pb["tf32_disabled_for_fp32_control"])
        self.assertEqual(result["kv_full_diagnostics"]["dtype"], "torch.bfloat16")

    def test_early_numerical_failure_still_collects_abc_and_baseline(self):
        # Reviewer fix #1/#2: an early numerical control (left-padding) failing must NOT
        # abort the exploratory control before A/B/C is collected; it is recorded and the
        # run continues. The BF16 formal path must still abort there (original behavior).
        import torch
        model = tiny_model()  # bf16 tiny; batch_tolerance = 0.5
        original = model.forward

        def perturbed(*args, **kwargs):
            out = original(*args, **kwargs)
            ids = kwargs.get("input_ids")
            # Perturb ONLY the 2-token standalone left-padding path so that control fails.
            if kwargs.get("use_cache") is False and ids is not None and ids.shape[1] == 2:
                out.logits = out.logits + 1.0
            return out

        model.forward = perturbed
        try:
            res = ch.run_checks(model, "cpu", exploratory=True)
            self.assertEqual(res["status"], "characterization_completed")
            nc = res["numerical_controls"]
            self.assertFalse(nc["left_padding_batch_last_logit_max_abs"]["passed"])
            self.assertGreater(nc["left_padding_batch_last_logit_max_abs"]["value"], 0.5)
            # repeat-noise baseline + its derived tolerance preserved in the recoverable object
            self.assertIn("value", nc["baseline_repeat_max_abs"])
            self.assertIn("derived_hook_tolerance", nc["baseline_repeat_max_abs"])
            # A/B/C still collected despite the early failure
            diag = res["kv_full_diagnostics"]
            for pair in ("A-B", "A-C", "B-C"):
                self.assertEqual(len(diag["batched_pairwise"][pair]), 2)
            self.assertEqual(len(diag["C_call_sequence"]), 5)
            self.assertFalse(diag["numerical_controls"]["left_padding_batch_last_logit_max_abs"]["passed"])
            # The BF16 formal path (exploratory=False) STILL aborts at the left-padding gate.
            with self.assertRaisesRegex(AssertionError, "left-padding"):
                ch.run_checks(model, "cpu", exploratory=False)
        finally:
            model.forward = original

    def test_exploratory_stops_on_non_finite_not_a_tolerance_failure(self):
        # Non-finite logits are a genuine breakdown: exploratory mode must STOP, not record-and-continue.
        import torch
        model = tiny_model()
        original = model.forward

        def nan_full(*args, **kwargs):
            out = original(*args, **kwargs)
            ids = kwargs.get("input_ids")
            if kwargs.get("use_cache") is False and ids is not None and ids.shape[1] == 5:
                out.logits = out.logits + float("inf")  # corrupt the full-sequence A path
            return out

        model.forward = nan_full
        try:
            with self.assertRaisesRegex(AssertionError, "non-finite"):
                ch.run_checks(model, "cpu", exploratory=True)
        finally:
            model.forward = original

    def test_exploratory_stops_on_non_finite_standalone_only(self):
        # Inject Inf ONLY into the 2-token standalone (left-padding) path; exploratory must STOP,
        # not record-and-continue (a finite over-threshold value would continue; non-finite must not).
        import torch
        model = tiny_model()
        original = model.forward

        def inf_standalone(*args, **kwargs):
            out = original(*args, **kwargs)
            ids = kwargs.get("input_ids")
            if kwargs.get("use_cache") is False and ids is not None and ids.shape[1] == 2:
                out.logits = out.logits + float("inf")
            return out

        model.forward = inf_standalone
        try:
            with self.assertRaisesRegex(AssertionError, "non-finite"):
                ch.run_checks(model, "cpu", exploratory=True)
        finally:
            model.forward = original

    def test_exploratory_stops_on_non_finite_projection_only(self):
        # Inject Inf ONLY into the projected decode. Among batched [2,1] use_cache=True
        # cache_position=[SEQ_LEN] calls the order is: baseline_decode, hooked_decode (identity),
        # c_decode (C), projected_decode -> the 4th is the projection path.
        import torch
        model = tiny_model()
        original = model.forward
        state = {"decode_calls": 0}

        def inf_projection(*args, **kwargs):
            out = original(*args, **kwargs)
            ids = kwargs.get("input_ids")
            cp = kwargs.get("cache_position")
            if (kwargs.get("use_cache") is True and ids is not None and tuple(ids.shape) == (ROWS, 1)
                    and cp is not None and int(cp.flatten()[0]) == SEQ_LEN):
                state["decode_calls"] += 1
                if state["decode_calls"] == 4:
                    out.logits = out.logits + float("inf")
            return out

        model.forward = inf_projection
        try:
            with self.assertRaisesRegex(AssertionError, "non-finite"):
                ch.run_checks(model, "cpu", exploratory=True)
            self.assertEqual(state["decode_calls"], 4)  # confirms the projection call was reached
        finally:
            model.forward = original

    def test_exploratory_stops_on_non_finite_c_intermediate_step(self):
        # Contaminate ONLY a token-by-token C intermediate prefill step (batched, cache_position 1).
        # The perturbation touches the returned logits, not the cache K/V, so the final C decode
        # stays finite -- without a per-step guard the run would wrongly return characterization_completed.
        import torch
        model = tiny_model()
        original = model.forward

        def inf_c_step(*args, **kwargs):
            out = original(*args, **kwargs)
            ids = kwargs.get("input_ids")
            cp = kwargs.get("cache_position")
            if (kwargs.get("use_cache") is True and ids is not None and tuple(ids.shape) == (ROWS, 1)
                    and cp is not None and int(cp.flatten()[0]) == 1):  # batched C prefill step t=1 only
                out.logits = out.logits + float("inf")
            return out

        model.forward = inf_c_step
        try:
            with self.assertRaisesRegex(AssertionError, "non-finite"):
                ch.run_checks(model, "cpu", exploratory=True)
        finally:
            model.forward = original

    def test_exploratory_stops_on_non_finite_single_row_c_intermediate_step(self):
        # Same gap in the single-row C loop: contaminate only a [1,1] cache_position-1 prefill step.
        import torch
        model = tiny_model()
        original = model.forward

        def inf_single_c_step(*args, **kwargs):
            out = original(*args, **kwargs)
            ids = kwargs.get("input_ids")
            cp = kwargs.get("cache_position")
            if (kwargs.get("use_cache") is True and ids is not None and tuple(ids.shape) == (1, 1)
                    and cp is not None and int(cp.flatten()[0]) == 1):  # single-row C prefill step t=1
                out.logits = out.logits + float("inf")
            return out

        model.forward = inf_single_c_step
        try:
            with self.assertRaisesRegex(AssertionError, "non-finite"):
                ch.run_checks(model, "cpu", exploratory=True)
        finally:
            model.forward = original

    def test_finite_over_threshold_continues_but_non_finite_stops(self):
        # Contrast: a FINITE standalone over threshold records+continues (characterization_completed);
        # the same path made NON-finite stops. Guards against treating a breakdown as a tolerance miss.
        import torch
        model = tiny_model()
        original = model.forward

        def perturb(mode):
            def wrapped(*args, **kwargs):
                out = original(*args, **kwargs)
                ids = kwargs.get("input_ids")
                if kwargs.get("use_cache") is False and ids is not None and ids.shape[1] == 2:
                    out.logits = out.logits + (1.0 if mode == "finite" else float("inf"))
                return out
            return wrapped

        try:
            model.forward = perturb("finite")
            res = ch.run_checks(model, "cpu", exploratory=True)
            self.assertEqual(res["status"], "characterization_completed")
            self.assertFalse(res["numerical_controls"]["left_padding_batch_last_logit_max_abs"]["passed"])
            model.forward = perturb("nonfinite")
            with self.assertRaisesRegex(AssertionError, "non-finite"):
                ch.run_checks(model, "cpu", exploratory=True)
        finally:
            model.forward = original

    def test_exploratory_artifact_carries_non_credential_markers(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "KV_FULL_TINY_FP32_CONTROL.json"
            argv = ["check_hooks.py", "--device", "cpu", "--dtype", "float32",
                    "--exploratory-precision-control", "--output", str(out)]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch("minicpm_research.resources.single_worker_lock", lambda p: nullcontext()), \
                 mock.patch("minicpm_research.resources.RuntimeResourceGuard", lambda *a, **k: nullcontext()):
                rc = ch.main()
            self.assertEqual(rc, 0)
            d = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(d["role"], "characterization_not_validation")
            self.assertTrue(d["exploratory_precision_control"])
            self.assertEqual(d["authoritative_t03_status"], "failed_bf16_primary_unchanged")
            self.assertTrue(d["does_not_unlock_t04"])
            self.assertTrue(d["kv_full_diagnostics"]["precision_backend"]["tf32_disabled_for_fp32_control"])

    def test_exploratory_output_may_not_be_named_hook_validation(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "HOOK_VALIDATION_FP32.json"
            lock = Path(td) / "lock.json"
            lock.write_text("{}", encoding="utf-8")
            argv = ["check_hooks.py", "--device", "cpu", "--dtype", "float32", "--model-lock", str(lock),
                    "--exploratory-precision-control", "--output", str(out)]
            with mock.patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit) as ctx:
                    ch.main()
            self.assertEqual(ctx.exception.code, 2)
            self.assertFalse(out.exists())

    def test_bf16_guard_unchanged_without_exploratory_flag(self):
        # The primary guard still refuses float32 on the locked checkpoint unless flagged.
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "x.json"
            lock = Path(td) / "lock.json"
            lock.write_text("{}", encoding="utf-8")
            argv = ["check_hooks.py", "--device", "cpu", "--dtype", "float32", "--model-lock", str(lock),
                    "--output", str(out)]
            with mock.patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit) as ctx:
                    ch.main()
            self.assertEqual(ctx.exception.code, 2)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
