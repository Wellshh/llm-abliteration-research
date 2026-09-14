"""Selected-position, padding, decode, causal and cleanup controls on a toy net."""
from __future__ import annotations

import importlib.util
import types
import unittest

HAS_TORCH = importlib.util.find_spec("torch") is not None
if HAS_TORCH:
    import torch
    from minicpm_research.hooks import PatchSpec, PostBlockHooks, rank_one_projection

    class ToyModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.config = types.SimpleNamespace(num_hidden_layers=2, hidden_size=3)
            self.model = torch.nn.Module()
            self.model.layers = torch.nn.ModuleList([torch.nn.Identity(), torch.nn.Identity()])
            self.embedding = torch.nn.Embedding(12, 3)
            with torch.no_grad():
                self.embedding.weight.copy_(torch.arange(36).reshape(12, 3).float() / 10)

        def forward(self, input_ids, attention_mask=None, cache_position=None):
            value = self.embedding(input_ids)
            for layer in self.model.layers:
                value = layer(value)
            return value


@unittest.skipUnless(HAS_TORCH, "torch is optional; install research dependencies for numerical hook tests")
class HookTests(unittest.TestCase):
    def setUp(self):
        self.model = ToyModel().eval()
        self.inputs = {"input_ids": torch.tensor([[0, 0, 2, 3], [4, 5, 6, 7]]),
                       "attention_mask": torch.tensor([[0, 0, 1, 1], [1, 1, 1, 1]])}
        self.unit = torch.tensor([1.0, 0.0, 0.0])

    def test_identity_zero_self_patch_and_weights_unchanged(self):
        weights = {name: value.clone() for name, value in self.model.state_dict().items()}
        baseline = self.model(**self.inputs)
        with PostBlockHooks(self.model):
            self.assertTrue(torch.equal(baseline, self.model(**self.inputs)))
        with PostBlockHooks(self.model, direction=self.unit, alpha=0):
            self.assertTrue(torch.equal(baseline, self.model(**self.inputs)))
        with PostBlockHooks(self.model, capture_positions={0: [(0, 3)]}) as donor:
            self.model(**self.inputs)
        patch = PatchSpec(0, ((0, 3),), donor.captures[0][(0, 3)].unsqueeze(0), donor_id="same_input_baseline")
        with PostBlockHooks(self.model, patches=[patch]):
            self.assertTrue(torch.equal(baseline, self.model(**self.inputs)))
        for name, value in self.model.state_dict().items():
            self.assertTrue(torch.equal(weights[name], value))

    def test_projection_padding_decode_and_batch(self):
        baseline = self.model(**self.inputs)
        with PostBlockHooks(self.model, self.unit, 1.0) as hooks:
            projected = self.model(**self.inputs)
            decoded = self.model(input_ids=torch.tensor([[8], [9]]),
                attention_mask=torch.tensor([[0, 0, 1, 1, 1], [1, 1, 1, 1, 1]]), cache_position=torch.tensor([4]))
        valid = self.inputs["attention_mask"].bool()
        self.assertTrue(torch.equal(projected[~valid], baseline[~valid]))
        self.assertTrue(torch.equal(projected[valid][:, 0], torch.zeros(6)))
        self.assertTrue(torch.equal(decoded[:, :, 0], torch.zeros(2, 1)))
        self.assertEqual(hooks.manifest()["projected_valid_tokens_across_layers"], 16)
        self.assertEqual(hooks.decode_forward_count, 1)
        standalone = self.model(input_ids=torch.tensor([[2, 3]]), attention_mask=torch.ones(1, 2))
        self.assertTrue(torch.equal(standalone[0], baseline[0, 2:]))

    def test_patch_order_and_future_projection_stays_active(self):
        values = torch.tensor([[5.0, 6.0, 7.0]])
        with PostBlockHooks(self.model, self.unit, 1.0,
                           patches=[PatchSpec(1, ((0, 3),), values, "before_projection")]):
            before = self.model(**self.inputs)
        with PostBlockHooks(self.model, self.unit, 1.0,
                           patches=[PatchSpec(1, ((0, 3),), values, "after_projection")]):
            after = self.model(**self.inputs)
        self.assertEqual(before[0, 3, 0].item(), 0)
        self.assertEqual(after[0, 3, 0].item(), 5)
        with PostBlockHooks(self.model, self.unit, 1.0,
                           patches=[PatchSpec(0, ((0, 3),), values, "after_projection")]) as hooks:
            earlier = self.model(**self.inputs)
        self.assertEqual(earlier[0, 3, 0].item(), 0)
        self.assertTrue(hooks.patch_applications[0]["future_projection_remains_active"])

    def test_controlled_replacement_changes_predictable_output(self):
        patch = PatchSpec(1, ((1, 3),), torch.tensor([[100.0, -100.0, 0.0]]))
        with PostBlockHooks(self.model, patches=[patch]):
            changed = self.model(**self.inputs)
        self.assertEqual(changed[1, 3].argmax().item(), 0)
        self.assertEqual(self.model(**self.inputs)[1, 3].argmax().item(), 2)

    def test_cleanup_on_exception_and_nested_configuration_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "test abort"):
            with PostBlockHooks(self.model):
                raise RuntimeError("test abort")
        self.assertFalse(self.model._forward_pre_hooks)
        self.assertTrue(all(not layer._forward_hooks for layer in self.model.model.layers))
        with PostBlockHooks(self.model):
            with self.assertRaises(ValueError):
                with PostBlockHooks(self.model):
                    pass

    def test_padding_patch_and_mask_omission_fail(self):
        with PostBlockHooks(self.model, patches=[PatchSpec(0, ((0, 0),), torch.ones(1, 3))]):
            with self.assertRaisesRegex(ValueError, "padding"):
                self.model(**self.inputs)
        with PostBlockHooks(self.model):
            with self.assertRaisesRegex(ValueError, "attention_mask"):
                self.model(input_ids=self.inputs["input_ids"])

    def test_projection_computes_bfloat16_input_in_fp32(self):
        hidden = torch.tensor([[[1.1, 2.2, -3.3]]], dtype=torch.bfloat16)
        direction = torch.tensor([0.3, -0.7, 0.5], dtype=torch.bfloat16)
        unit = direction.float() / direction.float().norm()
        expected = (hidden.float() - .5 * (hidden.float() @ unit).unsqueeze(-1) * unit).bfloat16()
        actual = rank_one_projection(hidden, direction, .5, torch.ones(1, 1, dtype=torch.bool))
        self.assertTrue(torch.equal(actual, expected))


if __name__ == "__main__":
    unittest.main()
