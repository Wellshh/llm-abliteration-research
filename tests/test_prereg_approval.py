import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path


def _load():
    spec = importlib.util.spec_from_file_location('validate_prereg_approval', Path('scripts/validate_prereg_approval.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PreregApprovalValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load()
        cls.root = Path(__file__).resolve().parents[1]
        cls.protocol = cls.root / 'reports/PREREGISTRATION_PHASE0_REVISION_v2_1.yaml'
        cls.sidecar = cls.root / 'reports/PREREGISTRATION_PHASE0_REVISION_v2_1_APPROVAL.json'

    def _copy(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        (root / 'reports').mkdir()
        shutil.copy2(self.protocol, root / self.protocol.relative_to(self.root))
        shutil.copy2(self.sidecar, root / self.sidecar.relative_to(self.root))
        return td, root

    def _call(self, root):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                result = self.mod.validate_prereg_approval(root)
            except SystemExit:
                self.assertEqual(buf.getvalue(), '')
                raise
        return result, buf.getvalue()

    def test_approved_v21_passes_without_output(self):
        td, root = self._copy()
        with td:
            result, out = self._call(root)
            self.assertTrue(result['effective'])
            self.assertEqual(result['choices']['C-07'], '(a)')
            self.assertEqual(out, '')

    def _reject_sidecar_mutation(self, mutate):
        td, root = self._copy()
        with td:
            path = root / self.sidecar.relative_to(self.root)
            data = json.loads(path.read_text())
            mutate(data)
            path.write_text(json.dumps(data))
            with self.assertRaises(SystemExit):
                self._call(root)

    def test_rejects_sha_mismatch(self):
        self._reject_sidecar_mutation(lambda d: d.__setitem__('protocol_sha256', '00' * 32))

    def test_rejects_pending(self):
        self._reject_sidecar_mutation(lambda d: d.__setitem__('status', 'pending_approval'))

    def test_rejects_choice_mismatch(self):
        self._reject_sidecar_mutation(lambda d: d['approver_choice_record']['C-07'].__setitem__('choice', '(b)'))

    def test_rejects_noncanonical_old_v2_path(self):
        td, root = self._copy()
        with td:
            with self.assertRaises(SystemExit):
                self.mod.validate_prereg_approval(root, root / 'reports/PREREGISTRATION_PHASE0_REVISION_v2.yaml', root / self.sidecar.relative_to(self.root))

    def test_rejects_protocol_tamper_even_with_old_hash(self):
        td, root = self._copy()
        with td:
            p = root / self.protocol.relative_to(self.root)
            p.write_text(p.read_text() + '\n# tampered\n')
            with self.assertRaises(SystemExit):
                self._call(root)

    def test_rejects_coordinated_protocol_and_sidecar_tamper(self):
        td, root = self._copy()
        with td:
            p = root / self.protocol.relative_to(self.root)
            a = root / self.sidecar.relative_to(self.root)
            p.write_text(p.read_text() + '\n# coordinated tamper\n')
            data = json.loads(a.read_text())
            import hashlib
            data['protocol_sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
            a.write_text(json.dumps(data))
            with self.assertRaises(SystemExit):
                self._call(root)


class SemanticPinTests(unittest.TestCase):
    """Review-F1 regression battery: the semantic battery must refuse CS-1-class
    denominator/pair/threshold regressions even when they are crafted to keep the
    magic substrings. Tests the extracted _validate_semantics directly — the pin
    layer already refuses tampered bytes from reaching it upstream (see
    PreregApprovalValidatorTests); these protect the future re-pin moment."""

    @classmethod
    def setUpClass(cls):
        import copy
        import yaml
        cls.mod = _load()
        root = Path(__file__).resolve().parents[1]
        cls.base_proto = yaml.safe_load((root / 'reports/PREREGISTRATION_PHASE0_REVISION_v2_1.yaml').read_text(encoding='utf-8'))
        cls.card = json.loads((root / 'reports/PREREGISTRATION_PHASE0_REVISION_v2_1_APPROVAL.json').read_text(encoding='utf-8'))
        cls.copy = copy

    def _refuse(self, mutate):
        proto = self.copy.deepcopy(self.base_proto)
        mutate(proto)
        with self.assertRaises(SystemExit):
            self.mod._validate_semantics(proto, self.card)

    def test_approved_semantics_pass(self):
        self.mod._validate_semantics(self.copy.deepcopy(self.base_proto), self.card)  # must not raise

    def test_output_dependent_denominator_missing_required_clauses_refused(self):
        evil = ("The consistency denominator is the FROZEN pair count recorded at freeze; it "
                "REMAINS in the denominator; invalid pairs are DROPPED and the count is "
                "recomputed from the outputs.")
        self._refuse(lambda p: p['c_round_gate']['label_swap_consistency'].__setitem__('denominator_semantics', evil))

    def test_reversal_sentence_appended_to_approved_text_refused(self):
        base = self.base_proto['c_round_gate']['label_swap_consistency']['denominator_semantics']
        reversal = base + " Exception: pairs with an invalid side are DROPPED and the count is recomputed from the outputs."
        self._refuse(lambda p: p['c_round_gate']['label_swap_consistency'].__setitem__('denominator_semantics', reversal))

    def test_swap_threshold_relaxation_refused(self):
        self._refuse(lambda p: p['c_round_gate']['label_swap_consistency'].__setitem__('min', 0.50))
        self._refuse(lambda p: p['c_round_gate']['label_swap_consistency'].__setitem__('min', True))

    def test_pair_count_shrinkage_refused(self):
        self._refuse(lambda p: p['c_round_gate']['label_swap_consistency'].__setitem__('expected_pair_count_round1', 3))
        self._refuse(lambda p: p['c_round_gate']['label_swap_consistency'].__setitem__('expected_pair_count_round1', True))

    def test_merged_pair_set_refused(self):
        self._refuse(lambda p: p['c_round_gate']['label_swap_consistency'].__setitem__(
            'pair_set', 'within-family (primary_map_1, primary_map_2, stance_agree, stance_oppose) pairs; merged invariant consistency'))

    def test_stance_gating_refused(self):
        self._refuse(lambda p: p['c_round_gate']['stance_consistency'].__setitem__('min', 0.85))
        self._refuse(lambda p: p['c_round_gate'].__setitem__('stance_consistency', None))


if __name__ == '__main__':
    unittest.main()
