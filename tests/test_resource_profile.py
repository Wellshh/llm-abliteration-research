"""B8-02 RESOURCE_PROFILE tests — CPU-only, deterministic, no GPU, no model weights
beyond a tiny random Llama harness control. Covers the §14 budget re-estimation math,
profile-rate selection, prefill/decode measurement structure + labelling, and the CLI
gates (cpu output naming, gated cuda ticket, budget-only illustrative guard, refuse-overwrite).
"""
from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from minicpm_research.resource_profile import (
    DEFAULT_PRE_ADMISSION_AUDIT_S,
    PHASE_CAP_HOURS,
    PhasePlan,
    measure_prefill_decode,
    rates_from_profile,
    reestimate_phase_budgets,
)


def _tiny_llama():
    import torch
    from transformers import LlamaConfig, LlamaForCausalLM
    cfg = LlamaConfig(vocab_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                      num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=512,
                      pad_token_id=0, bos_token_id=1, eos_token_id=2, attention_dropout=0.0)
    cfg._attn_implementation = "eager"
    torch.manual_seed(17)
    return LlamaForCausalLM(cfg).to(device="cpu", dtype=torch.float32)


class BudgetMathTests(unittest.TestCase):
    def test_reestimate_exact_arithmetic(self):
        plans = [PhasePlan(phase="P1", n_runs=10, prefill_tokens_per_run=200, decode_tokens_per_run=10)]
        out = reestimate_phase_budgets(plans, prefill_tokens_per_s=1000.0, decode_forward_per_s=50.0,
                                       fixed_overhead_per_run_s=10.0, pre_admission_audit_s=60.0)
        ph = out["per_phase"][0]
        self.assertAlmostEqual(ph["prefill_s_per_run"], 0.2)          # 200/1000
        self.assertAlmostEqual(ph["decode_s_per_run"], 0.2)           # 10/50
        self.assertAlmostEqual(ph["compute_s_per_run"], 10.4)         # 10 + 0.2 + 0.2
        self.assertAlmostEqual(ph["charged_compute_s"], 104.0)        # 10 * 10.4 (excludes audit, RES-04)
        self.assertAlmostEqual(ph["true_occupancy_s"], 704.0)         # 10 * (10.4 + 60) (includes audit)
        self.assertAlmostEqual(ph["cap_s"], PHASE_CAP_HOURS["P1"] * 3600)
        self.assertTrue(ph["charged_within_cap"] and ph["occupancy_within_cap"])
        self.assertAlmostEqual(out["total_charged_compute_s"], 104.0)
        self.assertAlmostEqual(out["total_true_occupancy_s"], 704.0)
        self.assertTrue(out["total_charged_within_main_cap"])

    def test_attempts_per_run_scales_occupancy_not_charged(self):
        plans = [PhasePlan(phase="P0", n_runs=2, prefill_tokens_per_run=100, decode_tokens_per_run=4, attempts_per_run=3.0)]
        out = reestimate_phase_budgets(plans, prefill_tokens_per_s=100.0, decode_forward_per_s=10.0,
                                       fixed_overhead_per_run_s=5.0, pre_admission_audit_s=60.0)
        ph = out["per_phase"][0]
        # compute/run = 5 + 100/100 + 4/10 = 5 + 1 + 0.4 = 6.4 ; charged = 2*6.4 = 12.8
        self.assertAlmostEqual(ph["charged_compute_s"], 12.8)
        # occupancy = 2*(6.4 + 3*60) = 2*186.4 = 372.8
        self.assertAlmostEqual(ph["true_occupancy_s"], 372.8)

    def test_cap_exceeded_flagged(self):
        # P0 cap = 5h = 18000s; force charged over it.
        plans = [PhasePlan(phase="P0", n_runs=100000, prefill_tokens_per_run=1000, decode_tokens_per_run=100)]
        out = reestimate_phase_budgets(plans, prefill_tokens_per_s=10.0, decode_forward_per_s=5.0,
                                       fixed_overhead_per_run_s=1.0)
        ph = out["per_phase"][0]
        self.assertFalse(ph["charged_within_cap"])
        self.assertFalse(out["total_charged_within_main_cap"])

    def test_fail_closed_on_bad_rates(self):
        plans = [PhasePlan(phase="P1", n_runs=1, prefill_tokens_per_run=10, decode_tokens_per_run=2)]
        for bad in (0.0, -1.0, math.inf, math.nan, True, "x", None):
            with self.assertRaises(ValueError):
                reestimate_phase_budgets(plans, prefill_tokens_per_s=bad, decode_forward_per_s=50.0,
                                         fixed_overhead_per_run_s=10.0)
            with self.assertRaises(ValueError):
                reestimate_phase_budgets(plans, prefill_tokens_per_s=50.0, decode_forward_per_s=bad,
                                         fixed_overhead_per_run_s=10.0)

    def test_default_audit_constant(self):
        self.assertEqual(DEFAULT_PRE_ADMISSION_AUDIT_S, 60.0)


class PhasePlanTests(unittest.TestCase):
    def test_unknown_phase_rejected(self):
        with self.assertRaises(ValueError):
            PhasePlan(phase="P9", n_runs=1, prefill_tokens_per_run=1, decode_tokens_per_run=1)

    def test_negative_rejected(self):
        with self.assertRaises(ValueError):
            PhasePlan(phase="P1", n_runs=-1, prefill_tokens_per_run=1, decode_tokens_per_run=1)
        with self.assertRaises(ValueError):
            PhasePlan(phase="P1", n_runs=1, prefill_tokens_per_run=-5, decode_tokens_per_run=1)

    def test_attempts_below_one_rejected(self):
        with self.assertRaises(ValueError):
            PhasePlan(phase="P1", n_runs=1, prefill_tokens_per_run=1, decode_tokens_per_run=1, attempts_per_run=0.5)


class RatesFromProfileTests(unittest.TestCase):
    def _profile(self):
        return {"prefill": [{"prefill_length": 128, "tokens_per_s": 1000.0},
                            {"prefill_length": 512, "tokens_per_s": 4000.0},
                            {"prefill_length": 2048, "tokens_per_s": 8000.0}],
                "decode": [{"forward_per_s": 40.0}, {"forward_per_s": 60.0}, {"forward_per_s": 50.0}],
                "decode_forward_per_s_median": 50.0}

    def test_picks_closest_prefill_length(self):
        r = rates_from_profile(self._profile(), planned_prefill_len=500)
        self.assertEqual(r["prefill_length_used"], 512)
        self.assertAlmostEqual(r["prefill_tokens_per_s"], 4000.0)
        self.assertAlmostEqual(r["decode_forward_per_s"], 50.0)  # median

    def test_decode_median_fallback_when_field_absent(self):
        prof = self._profile()
        del prof["decode_forward_per_s_median"]
        r = rates_from_profile(prof, planned_prefill_len=128)
        self.assertAlmostEqual(r["decode_forward_per_s"], 50.0)

    def test_no_prefill_raises(self):
        with self.assertRaises(ValueError):
            rates_from_profile({"prefill": [], "decode": []}, planned_prefill_len=128)


class MeasureHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_llama()

    def test_cpu_harness_structure_and_labels(self):
        prof = measure_prefill_decode(self.model, device="cpu", prefill_lengths=[8, 16],
                                      decode_steps=4, prefill_repeats=2, decode_repeats=1, warmup=1)
        self.assertEqual(prof["schema"], "resource_profile_prefill_decode_v1")
        self.assertEqual(prof["measurement_kind"], "cpu_harness_validation_NOT_a_real_profile")
        self.assertFalse(prof["is_real_profile"])
        self.assertEqual(len(prof["prefill"]), 2)
        self.assertEqual([p["prefill_length"] for p in prof["prefill"]], [8, 16])
        for p in prof["prefill"]:
            self.assertIsNotNone(p["forward_per_s"])
            self.assertIsNotNone(p["tokens_per_s"])
            self.assertGreater(p["seconds"], 0)
        self.assertEqual(len(prof["decode"]), 1)
        self.assertEqual(prof["decode"][0]["decode_steps"], 4)
        self.assertIsNotNone(prof["decode"][0]["forward_per_s"])
        self.assertIsNotNone(prof["decode_forward_per_s_median"])
        # RES-05: cpu has no cuda allocator peak
        self.assertIsNone(prof["allocator"]["allocator_peak_allocated_bytes"])
        self.assertEqual(prof["timing_method"], "perf_counter_no_cuda_sync")

    def test_invalid_args_rejected(self):
        with self.assertRaises(ValueError):
            measure_prefill_decode(self.model, device="cpu", prefill_lengths=[])
        with self.assertRaises(ValueError):
            measure_prefill_decode(self.model, device="cpu", prefill_lengths=[8], decode_steps=0)
        with self.assertRaises(ValueError):
            measure_prefill_decode(self.model, device="cpu", prefill_lengths=[8], prefill_repeats=0)

    def test_weights_unchanged(self):
        import hashlib
        import torch
        def digest(m):
            h = hashlib.sha256()
            for n, v in sorted(m.state_dict().items()):
                h.update(n.encode()); h.update(v.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
            return h.hexdigest()
        before = digest(self.model)
        measure_prefill_decode(self.model, device="cpu", prefill_lengths=[8], decode_steps=2,
                               prefill_repeats=1, decode_repeats=1, warmup=0)
        self.assertEqual(before, digest(self.model))


class CliGateTests(unittest.TestCase):
    def _main(self, argv):
        import importlib.util
        spec = importlib.util.spec_from_file_location("profile_resources", Path("scripts/profile_resources.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.main(argv)

    def test_cpu_refuses_resource_profile_name(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                self._main(["--device", "cpu", "--output", str(Path(d) / "RESOURCE_PROFILE.json")])

    def test_cuda_requires_ticket(self):
        with tempfile.TemporaryDirectory() as d:
            # no --execution-ticket -> parser.error (SystemExit 2), BEFORE any admission/torch import
            with self.assertRaises(SystemExit) as ctx:
                self._main(["--device", "cuda:0", "--model-lock", "artifacts/model/MODEL_MANIFEST.json",
                            "--output", str(Path(d) / "RESOURCE_PROFILE.json")])
            self.assertEqual(ctx.exception.code, 2)

    def test_cuda_requires_model_lock(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as ctx:
                self._main(["--device", "cuda:0", "--execution-ticket", "T", "--output", str(Path(d) / "x.json")])
            self.assertEqual(ctx.exception.code, 2)

    def test_cpu_harness_writes_labelled_output(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "RESOURCE_PROFILE_HARNESS_VALIDATION.json"
            rc = self._main(["--device", "cpu", "--prefill-lengths", "8,16", "--decode-steps", "3",
                             "--prefill-repeats", "1", "--decode-repeats", "1", "--warmup", "0", "--output", str(out)])
            self.assertEqual(rc, 0)
            doc = json.loads(out.read_text())
            self.assertEqual(doc["status"], "harness_validation_completed")
            self.assertFalse(doc["is_real_profile"])
            self.assertIn("harness_note", doc)

    def test_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "RESOURCE_PROFILE_HARNESS_VALIDATION.json"
            out.write_text("{}")  # pre-existing
            with self.assertRaises(SystemExit):
                self._main(["--device", "cpu", "--prefill-lengths", "8", "--decode-steps", "2",
                            "--prefill-repeats", "1", "--decode-repeats", "1", "--warmup", "0", "--output", str(out)])

    def test_budget_only_refuses_nonreal_profile_without_illustrative(self):
        with tempfile.TemporaryDirectory() as d:
            prof = Path(d) / "prof.json"
            prof.write_text(json.dumps({"is_real_profile": False, "measurement_kind": "cpu_harness_validation_NOT_a_real_profile",
                                        "prefill": [{"prefill_length": 8, "tokens_per_s": 100.0}],
                                        "decode": [{"forward_per_s": 20.0}], "decode_forward_per_s_median": 20.0}))
            plan = Path(d) / "plan.json"
            plan.write_text(json.dumps({"fixed_overhead_per_run_s": 1.0, "phases": [
                {"phase": "P1", "n_runs": 1, "prefill_tokens_per_run": 8, "decode_tokens_per_run": 2}]}))
            with self.assertRaises(SystemExit):
                self._main(["--budget-only", "--profile", str(prof), "--plan", str(plan),
                            "--output", str(Path(d) / "BUDGET_REESTIMATE.json")])
            # with --illustrative it succeeds and is labelled
            rc = self._main(["--budget-only", "--illustrative", "--profile", str(prof), "--plan", str(plan),
                             "--output", str(Path(d) / "BUDGET_REESTIMATE.json")])
            self.assertEqual(rc, 0)
            doc = json.loads((Path(d) / "BUDGET_REESTIMATE.json").read_text())
            self.assertEqual(doc["reestimate_kind"], "illustrative_not_a_real_reestimate")

    def test_budget_only_output_name_guard(self):
        with tempfile.TemporaryDirectory() as d:
            prof = Path(d) / "prof.json"; prof.write_text(json.dumps({"is_real_profile": True, "measurement_kind": "real_gpu_measurement",
                                                                      "prefill": [{"prefill_length": 8, "tokens_per_s": 100.0}],
                                                                      "decode": [{"forward_per_s": 20.0}], "decode_forward_per_s_median": 20.0}))
            plan = Path(d) / "plan.json"; plan.write_text(json.dumps({"phases": [{"phase": "P1", "n_runs": 1, "prefill_tokens_per_run": 8, "decode_tokens_per_run": 2}]}))
            with self.assertRaises(SystemExit):
                self._main(["--budget-only", "--profile", str(prof), "--plan", str(plan), "--output", str(Path(d) / "RESOURCE_PROFILE.json")])


if __name__ == "__main__":
    unittest.main()
