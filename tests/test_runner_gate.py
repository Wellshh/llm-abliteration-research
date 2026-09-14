from __future__ import annotations
import json, sys, tempfile, unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_pilot
from minicpm_research.runs import file_hash

class RunnerGateTests(unittest.TestCase):
    def test_encode_generation_prompt_requests_and_accepts_strict_inputs(self):
        class Tensor:
            def __init__(self, shape): self.shape = shape
        class Tokenizer:
            def __call__(self, *args, **kwargs):
                self.kwargs = kwargs
                return {'input_ids': Tensor((1, 4)), 'attention_mask': Tensor((1, 4))}
        tok = Tokenizer()
        result = run_pilot.encode_generation_prompt(tok, 'prompt')
        self.assertEqual(set(result), {'input_ids', 'attention_mask'})
        self.assertFalse(tok.kwargs['return_token_type_ids'])

    def test_encode_generation_prompt_rejects_unsupported_or_bad_shapes(self):
        class Tensor:
            def __init__(self, shape): self.shape = shape
        cases = [
            {'attention_mask': Tensor((1, 4))},
            {'input_ids': Tensor((1, 4)), 'token_type_ids': Tensor((1, 4))},
            {'input_ids': Tensor((1, 4)), 'position_ids': Tensor((1, 4))},
            {'input_ids': Tensor((4,))},
            {'input_ids': Tensor((1, 4)), 'attention_mask': Tensor((1, 3))},
        ]
        for output in cases:
            with self.subTest(output=output):
                with self.assertRaises(ValueError):
                    run_pilot.encode_generation_prompt(lambda *a, **k: output, 'prompt')

    def test_task_aware_decode_preserves_tool_markers_and_removes_eos(self):
        class Tokenizer:
            def decode(self, ids, skip_special_tokens):
                return (tuple(ids), skip_special_tokens)
        tok = Tokenizer()
        self.assertEqual(run_pilot.decode_generated_tokens(tok, [10, 20, 99], 'T', [99]), ((10, 20), False))
        self.assertEqual(run_pilot.decode_generated_tokens(tok, [10, 20, 99], 'V', [99]), ((10, 20, 99), True))
        self.assertEqual(run_pilot.decode_generated_tokens(tok, [10, 20], 'T', [99]), ((10, 20), False))
    def test_parser_manifest_hash_is_parser_file(self):
        self.assertEqual(run_pilot.parser_code_sha256(), file_hash(Path(run_pilot.native_tool_parser.__file__).resolve()))
        self.assertNotEqual(run_pilot.parser_code_sha256(), file_hash(Path(run_pilot.__file__).resolve()))
    def test_gate_binds_report_to_lock_and_runtime(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); lock=root/'lock.json'; report=root/'hook.json'; lock.write_text('{}',encoding='utf-8')
            report.write_text(json.dumps({'status':'passed','model_source':'locked_official_checkpoint','model_manifest_sha256':file_hash(lock),'device':'cpu','dtype':'bfloat16','attention_backend':'eager'}),encoding='utf-8')
            gate=run_pilot.validate_hook_gate(report,lock,'cpu','bfloat16','eager')
            self.assertEqual(gate['model_manifest_sha256'],file_hash(lock)); self.assertTrue(gate['report_sha256'])
    def test_gate_rejects_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); lock=root/'lock.json'; report=root/'hook.json'; lock.write_text('{}',encoding='utf-8')
            report.write_text(json.dumps({'status':'passed','model_source':'locked_official_checkpoint','model_manifest_sha256':'0'*64,'device':'cpu','dtype':'bfloat16','attention_backend':'eager'}),encoding='utf-8')
            with self.assertRaises(ValueError): run_pilot.validate_hook_gate(report,lock,'cpu','bfloat16','eager')
    def test_missing_report_rejected_without_model_load(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); lock=root/'lock.json'; lock.write_text('{}',encoding='utf-8')
            with self.assertRaises(ValueError): run_pilot.validate_hook_gate(root/'missing.json',lock,'cpu','bfloat16','eager')
    def test_template_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            lock=Path(td)/'lock.json'; lock.write_text(json.dumps({'chat_template_sha256':'0'*64}),encoding='utf-8')
            with self.assertRaises(ValueError): run_pilot.validate_parser_template(lock)
    def test_gate_rejects_characterization_report_even_if_passed(self):
        # An exploratory FP32 characterization report must NEVER unlock T04, even when
        # it otherwise looks like a valid passed locked-checkpoint hook-validation.
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); lock=root/'lock.json'; report=root/'fp32_control.json'; lock.write_text('{}',encoding='utf-8')
            report.write_text(json.dumps({'status':'passed','model_source':'locked_official_checkpoint',
                'model_manifest_sha256':file_hash(lock),'device':'cpu','dtype':'bfloat16','attention_backend':'eager',
                'role':'characterization_not_validation','exploratory_precision_control':True,
                'authoritative_t03_status':'failed_bf16_primary_unchanged','does_not_unlock_t04':True}),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'characterization'):
                run_pilot.validate_hook_gate(report,lock,'cpu','bfloat16','eager')
    def test_gate_rejects_exploratory_flag_alone(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); lock=root/'lock.json'; report=root/'ctrl.json'; lock.write_text('{}',encoding='utf-8')
            report.write_text(json.dumps({'status':'passed','model_source':'locked_official_checkpoint',
                'model_manifest_sha256':file_hash(lock),'device':'cpu','dtype':'bfloat16','attention_backend':'eager',
                'exploratory_precision_control':True}),encoding='utf-8')
            with self.assertRaises(ValueError):
                run_pilot.validate_hook_gate(report,lock,'cpu','bfloat16','eager')

    def test_split_gate_accepts_locked_aggregation_and_sidecar(self):
        config = json.loads((run_pilot.ROOT / 'configs' / 'pilot.json').read_text(encoding='utf-8'))
        config['condition'] = 'baseline'
        gate = run_pilot.validate_split_gate(
            run_pilot.ROOT / 'reports' / 'T03_GATE_SPLIT_AMENDMENT_v1.yaml',
            run_pilot.ROOT / 'reports' / 'T03_GATE_SPLIT_AMENDMENT_v1_APPROVAL.json',
            run_pilot.ROOT / 'reports' / 'T03_HOOK_GATE_v1.json', config)
        self.assertEqual(gate['mode'], 'split_v1')
        self.assertEqual(gate['status'], 'passed_under_gate_split_v1')
        self.assertEqual(gate['historical_T03_bf16_gate'], 'failed')

    def test_split_gate_rejects_nonpilot_or_nonidentity_condition(self):
        config = json.loads((run_pilot.ROOT / 'configs' / 'pilot.json').read_text(encoding='utf-8'))
        config['condition'] = 'selected_refusal_edit'
        with self.assertRaisesRegex(ValueError, 'baseline or identity_hook'):
            run_pilot.validate_split_gate(
                run_pilot.ROOT / 'reports' / 'T03_GATE_SPLIT_AMENDMENT_v1.yaml',
                run_pilot.ROOT / 'reports' / 'T03_GATE_SPLIT_AMENDMENT_v1_APPROVAL.json',
                run_pilot.ROOT / 'reports' / 'T03_HOOK_GATE_v1.json', config)

    def test_split_gate_rejects_sidecar_mismatch(self):
        config = json.loads((run_pilot.ROOT / 'configs' / 'pilot.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory(dir=run_pilot.ROOT) as td:
            bad = Path(td) / 'bad_sidecar.json'
            sidecar = json.loads((run_pilot.ROOT / 'reports' / 'T03_GATE_SPLIT_AMENDMENT_v1_APPROVAL.json').read_text(encoding='utf-8'))
            sidecar['amendment_sha256'] = '0' * 64
            bad.write_text(json.dumps(sidecar), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'approval sidecar path mismatch'):
                run_pilot.validate_split_gate(
                    run_pilot.ROOT / 'reports' / 'T03_GATE_SPLIT_AMENDMENT_v1.yaml', bad,
                    run_pilot.ROOT / 'reports' / 'T03_HOOK_GATE_v1.json', config)

    def test_split_gate_rejects_sidecar_sha_mismatch(self):
        config = json.loads((run_pilot.ROOT / 'configs' / 'pilot.json').read_text(encoding='utf-8'))
        original = run_pilot.file_hash
        sidecar_path = run_pilot.ROOT / 'reports' / 'T03_GATE_SPLIT_AMENDMENT_v1_APPROVAL.json'
        amendment_path = run_pilot.ROOT / 'reports' / 'T03_GATE_SPLIT_AMENDMENT_v1.yaml'
        def fake_hash(path):
            return '0' * 64 if Path(path).resolve() == amendment_path.resolve() else original(path)
        with patch.object(run_pilot, 'file_hash', side_effect=fake_hash):
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                run_pilot.validate_split_gate(amendment_path, sidecar_path,
                                              run_pilot.ROOT / 'reports' / 'T03_HOOK_GATE_v1.json', config)

    def test_yaml_loader_uses_nested_safe_parse_and_rejects_missing_parser(self):
        amendment = run_pilot.ROOT / 'reports' / 'T03_GATE_SPLIT_AMENDMENT_v1.yaml'
        parsed = run_pilot._load_split_yaml(amendment)
        self.assertEqual(parsed['historical_status']['historical_T03_bf16_gate'], 'failed')
        real_import = __import__
        def no_yaml(name, *args, **kwargs):
            if name == 'yaml':
                raise ImportError('forced missing yaml')
            return real_import(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=no_yaml):
            with self.assertRaisesRegex(ValueError, 'PyYAML is required'):
                run_pilot._load_split_yaml(amendment)

    def test_split_gate_rejects_condition_set_mismatch(self):
        config = json.loads((run_pilot.ROOT / 'configs' / 'pilot.json').read_text(encoding='utf-8'))
        sidecar = json.loads(self._split_paths()[1].read_text(encoding='utf-8'))
        aggregate = json.loads(self._split_paths()[2].read_text(encoding='utf-8'))
        aggregate['conditions'] = aggregate['conditions'][:-1]
        with patch.object(run_pilot.json, 'loads', side_effect=[sidecar, aggregate]):
            with self.assertRaisesRegex(ValueError, 'condition sets'):
                run_pilot.validate_split_gate(*self._split_paths(), config)

    def _split_paths(self):
        return (run_pilot.ROOT / 'reports' / 'T03_GATE_SPLIT_AMENDMENT_v1.yaml',
                run_pilot.ROOT / 'reports' / 'T03_GATE_SPLIT_AMENDMENT_v1_APPROVAL.json',
                run_pilot.ROOT / 'reports' / 'T03_HOOK_GATE_v1.json')

    def test_split_gate_rejects_aggregation_status_threshold_t04_and_model_mutations(self):
        config = json.loads((run_pilot.ROOT / 'configs' / 'pilot.json').read_text(encoding='utf-8'))
        mutations = [
            ('status', 'wrong split status', 'effective passed split gate'),
            ('new_full_cache_threshold', 0.1, 'new full/cache threshold'),
            ('does_not_unlock_T04_automatically', False, 'must not unlock'),
            ('model_lock', {'path': 'artifacts/model/MODEL_MANIFEST.json', 'sha256': '0' * 64}, 'model lock mismatch'),
        ]
        for key, value, message in mutations:
            with self.subTest(key=key), tempfile.TemporaryDirectory(dir=run_pilot.ROOT) as td:
                bad = Path(td) / 'bad.json'
                aggregate = json.loads(self._split_paths()[2].read_text(encoding='utf-8'))
                if key == 'new_full_cache_threshold':
                    aggregate['scope'][key] = value
                elif key == 'model_lock':
                    aggregate[key] = value
                else:
                    aggregate[key] = value
                bad.write_text(json.dumps(aggregate), encoding='utf-8')
                sidecar = self._split_paths()[1]
                lock = None
                if key == 'model_lock':
                    lock = Path(td) / 'wrong_model.json'
                    lock.write_text(json.dumps({'revision_sha': 'wrong'}), encoding='utf-8')
                aggregation_path = self._split_paths()[2] if key == 'model_lock' else bad
                with self.assertRaisesRegex(ValueError, message):
                    run_pilot.validate_split_gate(self._split_paths()[0], sidecar, aggregation_path, config, lock)

    def test_split_gate_rejects_wrong_dtype_and_eager_backend(self):
        config = json.loads((run_pilot.ROOT / 'configs' / 'pilot.json').read_text(encoding='utf-8'))
        for key, value in [('dtype', 'float32'), ('attention_backend', 'sdpa')]:
            with self.subTest(key=key):
                bad = dict(config)
                bad[key] = value
                with self.assertRaisesRegex(ValueError, 'requires BF16 eager'):
                    run_pilot.validate_split_gate(*self._split_paths(), bad)

    def test_split_gate_rejects_alternate_exact_copy_paths(self):
        config = json.loads((run_pilot.ROOT / 'configs' / 'pilot.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory(dir=run_pilot.ROOT) as td:
            alternate = Path(td) / 'amendment.yaml'
            alternate.write_bytes(self._split_paths()[0].read_bytes())
            with self.assertRaisesRegex(ValueError, 'amendment path mismatch'):
                run_pilot.validate_split_gate(alternate, self._split_paths()[1], self._split_paths()[2], config)
            model_copy = Path(td) / 'MODEL_MANIFEST.json'
            model_copy.write_bytes((run_pilot.ROOT / 'artifacts/model/MODEL_MANIFEST.json').read_bytes())
            with self.assertRaisesRegex(ValueError, 'model lock path mismatch'):
                run_pilot.validate_split_gate(self._split_paths()[0], self._split_paths()[1], self._split_paths()[2], config, model_copy)

    def test_pending_t04_approval_is_rejected(self):
        config = json.loads((run_pilot.ROOT / 'configs' / 'pilot-baseline.json').read_text(encoding='utf-8'))
        gate = run_pilot.validate_split_gate(*self._split_paths(), config)
        with self.assertRaisesRegex(ValueError, 'pending or ineffective'):
            run_pilot.validate_t04_execution_approval(
                run_pilot.ROOT / 'reports' / 'T04_EXECUTION_APPROVAL_TEMPLATE.json', config, gate,
                run_pilot.ROOT / 'configs' / 'pilot-baseline.json',
                run_pilot.ROOT / 'artifacts/data/pilot.jsonl', 'both', 1, 'cuda:0', run_pilot.ROOT / 'artifacts/runs/t04-baseline-V')

    def _write_approved_t04(self, directory, **changes):
        config_path = run_pilot.ROOT / 'configs' / 'pilot-baseline.json'
        data_path = run_pilot.ROOT / 'artifacts/data/pilot.jsonl'
        config = json.loads(config_path.read_text(encoding='utf-8'))
        gate = run_pilot.validate_split_gate(*self._split_paths(), config)
        approval = json.loads((run_pilot.ROOT / 'reports/T04_EXECUTION_APPROVAL_TEMPLATE.json').read_text(encoding='utf-8'))
        approval['status'] = 'approved'; approval['effective'] = True
        approval['approval_id'] = 'approval-test-baseline-v'
        approval['bindings'].update({
            'amendment_sha256': gate['amendment_sha256'],
            'aggregation_sha256': gate['aggregation_sha256'],
            'approval_sidecar_sha256': gate['approval_sidecar_sha256'],
            'amendment_path': 'reports/T03_GATE_SPLIT_AMENDMENT_v1.yaml',
            'aggregation_path': 'reports/T03_HOOK_GATE_v1.json',
            'approval_sidecar_path': 'reports/T03_GATE_SPLIT_AMENDMENT_v1_APPROVAL.json',
            'config_path': 'configs/pilot-baseline.json',
            'config_sha256': run_pilot.file_hash(config_path),
            'data_path': 'artifacts/data/pilot.jsonl',
            'data_sha256': run_pilot.file_hash(data_path),
            'output_dir': 'artifacts/runs/t04-baseline-V',
            'condition': 'baseline', 'task': 'V', 'max_families': 1,
            'device': 'cuda:0', 'gpu_uuid': config['gpu_uuid'],
            'approval_id': 'approval-test-baseline-v',
            'execution_scope': 'single_content_addressed_run_allow_resume',
        })
        approval['approval_record'] = {
            'approved_at': '2026-09-14T12:00:00+08:00',
            'approval_semantics': 'user_approved_t04_execution_after_final_ticket',
        }
        approval.update(changes)
        path = Path(directory) / 'approved.json'
        path.write_text(json.dumps(approval), encoding='utf-8')
        return path, config, gate, config_path, data_path

    def test_t04_approval_validates_all_cli_bindings(self):
        with tempfile.TemporaryDirectory(dir=run_pilot.ROOT) as td:
            path, config, gate, config_path, data_path = self._write_approved_t04(td)
            result = run_pilot.validate_t04_execution_approval(
                path, config, gate, config_path, data_path, 'V', 1, 'cuda:0', run_pilot.ROOT / 'artifacts/runs/t04-baseline-V')
            self.assertEqual(result['status'], 'approved')

    def test_t04_approval_rejects_task_family_config_data_and_device_mismatch(self):
        with tempfile.TemporaryDirectory(dir=run_pilot.ROOT) as td:
            for label, mutation, actual_task, actual_max, actual_device in [
                ('task', lambda a: a['bindings'].__setitem__('task', 'V'), 'both', 12, 'cuda:0'),
                ('max_families', lambda a: a['bindings'].__setitem__('max_families', 12), 'V', 1, 'cuda:0'),
                ('config', lambda a: a['bindings'].__setitem__('config_path', 'configs/pilot-identity.json'), 'V', 1, 'cuda:0'),
                ('data', lambda a: a['bindings'].__setitem__('data_path', 'artifacts/data/test.jsonl'), 'V', 1, 'cuda:0'),
                ('device', lambda a: a['bindings'].__setitem__('device', 'cuda:1'), 'V', 1, 'cuda:0'),
            ]:
                with self.subTest(label=label):
                    path, config, gate, config_path, data_path = self._write_approved_t04(td)
                    approval = json.loads(path.read_text(encoding='utf-8')); mutation(approval)
                    path.write_text(json.dumps(approval), encoding='utf-8')
                    with self.assertRaises(ValueError):
                        run_pilot.validate_t04_execution_approval(
                            path, config, gate, config_path, data_path,
                            actual_task, actual_max, actual_device, run_pilot.ROOT / 'artifacts/runs/t04-baseline-V')

    def test_t04_approval_rejects_exact_copy_config_path_and_data_hash(self):
        with tempfile.TemporaryDirectory(dir=run_pilot.ROOT) as td:
            path, config, gate, config_path, data_path = self._write_approved_t04(td)
            copy_path = Path(td) / 'pilot-copy.json'; copy_path.write_bytes(config_path.read_bytes())
            approval = json.loads(path.read_text(encoding='utf-8'))
            approval['bindings']['config_path'] = str(copy_path.relative_to(run_pilot.ROOT)).replace('\\', '/')
            path.write_text(json.dumps(approval), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'config path'):
                run_pilot.validate_t04_execution_approval(path, config, gate, config_path, data_path, 'V', 1, 'cuda:0', run_pilot.ROOT / 'artifacts/runs/t04-baseline-V')
            approval['bindings']['config_path'] = 'configs/pilot-baseline.json'
            approval['bindings']['data_sha256'] = '0' * 64
            path.write_text(json.dumps(approval), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'data binding'):
                run_pilot.validate_t04_execution_approval(path, config, gate, config_path, data_path, 'V', 1, 'cuda:0', run_pilot.ROOT / 'artifacts/runs/t04-baseline-V')

    def test_t04_approval_rejects_output_directory_mismatch(self):
        with tempfile.TemporaryDirectory(dir=run_pilot.ROOT) as td:
            path, config, gate, config_path, data_path = self._write_approved_t04(td)
            approval = json.loads(path.read_text(encoding='utf-8'))
            approval['bindings']['output_dir'] = 'artifacts/runs/other-ticket'
            path.write_text(json.dumps(approval), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'output directory'):
                run_pilot.validate_t04_execution_approval(path, config, gate, config_path, data_path, 'V', 1, 'cuda:0', run_pilot.ROOT / 'artifacts/runs/t04-baseline-V')

    def test_split_gate_rejects_condition_status_duplicate_and_non_mapping(self):
        config = json.loads((run_pilot.ROOT / 'configs' / 'pilot.json').read_text(encoding='utf-8'))
        for kind in ('wrong_status', 'duplicate', 'non_mapping'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=run_pilot.ROOT) as td:
                bad = Path(td) / 'bad.json'
                aggregate = json.loads(self._split_paths()[2].read_text(encoding='utf-8'))
                if kind == 'wrong_status':
                    aggregate['conditions'][0]['status'] = 'passed'
                elif kind == 'duplicate':
                    aggregate['conditions'][1]['condition'] = aggregate['conditions'][0]['condition']
                else:
                    aggregate['conditions'][0] = 'not-a-mapping'
                bad.write_text(json.dumps(aggregate), encoding='utf-8')
                expected = 'condition status' if kind == 'wrong_status' else ('condition sets' if kind == 'duplicate' else 'contain mappings')
                with self.assertRaisesRegex(ValueError, expected):
                    run_pilot.validate_split_gate(*self._split_paths()[:2], bad, config)
