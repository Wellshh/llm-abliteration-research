"""Model metadata checks run without torch or network access."""
from __future__ import annotations

import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from huggingface_hub.hf_api import RepoFile

from minicpm_research.model import (OFFICIAL_MODEL, audit_model, inspect_safetensors,
                                    token_anchors, verify_lock, verify_official_file_hashes)


def write_tensor(path: Path, *, dtype: str = "BF16", offsets: list[int] | None = None) -> None:
    header = json.dumps({"weight": {"dtype": dtype, "shape": [2, 3],
                                    "data_offsets": offsets or [0, 12]}}).encode()
    path.write_bytes(struct.pack("<Q", len(header)) + header + bytes(12))


class ModelAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "config.json").write_text(json.dumps({"model_type": "llama",
            "architectures": ["LlamaForCausalLM"], "num_hidden_layers": 1, "hidden_size": 3}), encoding="utf-8")
        (self.root / "tokenizer_config.json").write_text(json.dumps({"chat_template": "{% if enable_thinking %}thinking{% endif %}"}), encoding="utf-8")
        write_tensor(self.root / "model.safetensors")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_actual_header_count_and_dtype(self) -> None:
        result = audit_model(self.root, "a" * 40)
        self.assertEqual(result["stored_tensor_element_count"], 6)
        self.assertEqual(result["stored_dtype_elements"], {"BF16": 6})
        self.assertEqual(len(result["files"]["model.safetensors"]["sha256"]), 64)
        self.assertFalse(result["trust_remote_code"])

    def test_revision_must_be_immutable(self) -> None:
        with self.assertRaisesRegex(ValueError, "40-character"):
            audit_model(self.root, "main")

    def test_truncated_or_inconsistent_tensor_fails(self) -> None:
        for offsets in ([0, 13], [1, 12], [12, 0]):
            write_tensor(self.root / "model.safetensors", offsets=offsets)
            with self.assertRaises(ValueError):
                inspect_safetensors(self.root / "model.safetensors")
        (self.root / "model.safetensors").write_bytes(bytes(3))
        with self.assertRaises(ValueError):
            inspect_safetensors(self.root / "model.safetensors")

    def test_wrong_precision_and_architecture_fail(self) -> None:
        write_tensor(self.root / "model.safetensors", dtype="F16")
        with self.assertRaisesRegex(ValueError, "BF16"):
            audit_model(self.root, "a" * 40)
        (self.root / "config.json").write_text('{"model_type":"custom"}')
        with self.assertRaisesRegex(ValueError, "LlamaForCausalLM"):
            audit_model(self.root, "a" * 40)

    def test_missing_weight_is_explicitly_incomplete(self) -> None:
        (self.root / "model.safetensors").unlink()
        with self.assertRaisesRegex(ValueError, "no safetensors"):
            audit_model(self.root, "a" * 40)
        result = audit_model(self.root, "a" * 40, require_weights=False)
        self.assertFalse(result["weights_verified"])

    def test_lock_detects_file_change(self) -> None:
        result = audit_model(self.root, "a" * 40)
        result["token_anchors"] = {"thinking_false_verified": True}
        result["provenance"] = "official_file_hashes_verified"
        self.assertEqual(verify_lock(result), self.root.resolve())
        (self.root / "config.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            verify_lock(result)


class FakeTokenizer:
    def apply_chat_template(self, messages, *, enable_thinking, **kwargs):
        return "think:" if enable_thinking else "answer:"

    def encode(self, text, *, add_special_tokens):
        return list(text.encode())


class TokenAnchorTests(unittest.TestCase):
    def test_context_ids_are_actual_continuations(self) -> None:
        anchors = token_anchors(FakeTokenizer())
        self.assertTrue(anchors["thinking_false_verified"])
        self.assertEqual(anchors["label_contexts"]["A"]["continuation_token_ids"], [65])
        self.assertFalse(anchors["label_probabilities_require_sequence_scoring"])

    def test_silently_ignored_thinking_flag_is_rejected(self) -> None:
        tokenizer = FakeTokenizer()
        tokenizer.apply_chat_template = lambda *args, **kwargs: "same"
        with self.assertRaisesRegex(ValueError, "identical"):
            token_anchors(tokenizer)


class HashVerificationTests(unittest.TestCase):
    """verify_official_file_hashes via the tree endpoint; no network access."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "config.json").write_text(json.dumps({"model_type": "llama",
            "architectures": ["LlamaForCausalLM"], "num_hidden_layers": 1, "hidden_size": 3}), encoding="utf-8")
        (self.root / "tokenizer_config.json").write_text(json.dumps({"chat_template": "{% if enable_thinking %}t{% endif %}"}), encoding="utf-8")
        write_tensor(self.root / "model.safetensors")
        self.manifest = audit_model(self.root, "a" * 40)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _fakes(self, *, flip: str | None = None) -> list[RepoFile]:
        fakes: list[RepoFile] = []
        for name in self.manifest["files"]:
            content = (self.root / name).read_bytes()
            oid = hashlib.sha1(b"blob %d\0" % len(content) + content).hexdigest()
            lfs = None
            if name.endswith(".safetensors"):
                lfs = {"size": len(content), "oid": hashlib.sha256(content).hexdigest(), "pointerSize": 134}
            if flip == name:
                oid = "0" * 40
                if lfs is not None:
                    lfs = {"size": len(content), "oid": "0" * 64, "pointerSize": 134}
            fakes.append(RepoFile(path=name, size=len(content), oid=oid, type="file", lfs=lfs))
        return fakes

    def _patched(self, endpoint: str | None, api_endpoint: str, fakes: list[RepoFile]):
        patcher = mock.patch("huggingface_hub.HfApi")
        mocked = patcher.start()
        self.addCleanup(patcher.stop)
        mocked.return_value.endpoint = api_endpoint
        mocked.return_value.list_repo_tree.return_value = fakes
        return mocked

    def test_mirror_endpoint_binds_and_marks_provenance(self) -> None:
        mocked = self._patched("https://hf-mirror.com", "https://hf-mirror.com", self._fakes())
        verify_official_file_hashes(self.manifest, endpoint="https://hf-mirror.com")
        mocked.assert_called_once_with(endpoint="https://hf-mirror.com")
        mocked.return_value.list_repo_tree.assert_called_once_with(OFFICIAL_MODEL, revision="a" * 40, recursive=False)
        self.assertEqual(self.manifest["provenance"], "mirror_file_hashes_verified")
        self.assertEqual(self.manifest["hash_verification_endpoint"], "https://hf-mirror.com")
        self.assertEqual(self.manifest["official_file_hashes"]["config.json"]["algorithm"], "git_blob_sha1")
        self.assertEqual(self.manifest["official_file_hashes"]["model.safetensors"]["algorithm"], "sha256")

    def test_official_endpoint_marks_official_provenance(self) -> None:
        mocked = self._patched(None, "https://huggingface.co", self._fakes())
        verify_official_file_hashes(self.manifest, endpoint=None)
        mocked.assert_called_once_with(endpoint=None)
        self.assertEqual(self.manifest["provenance"], "official_file_hashes_verified")

    def test_hash_mismatch_fails_closed(self) -> None:
        self._patched("https://hf-mirror.com", "https://hf-mirror.com", self._fakes(flip="config.json"))
        with self.assertRaisesRegex(ValueError, "differ from the pinned tree"):
            verify_official_file_hashes(self.manifest, endpoint="https://hf-mirror.com")

    def test_missing_remote_file_fails_closed(self) -> None:
        fakes = [f for f in self._fakes() if f.path != "config.json"]
        self._patched("https://hf-mirror.com", "https://hf-mirror.com", fakes)
        with self.assertRaisesRegex(ValueError, "absent from the pinned tree"):
            verify_official_file_hashes(self.manifest, endpoint="https://hf-mirror.com")

    def test_verify_lock_accepts_mirror_provenance(self) -> None:
        lock = dict(self.manifest)
        lock["provenance"] = "mirror_file_hashes_verified"
        lock["token_anchors"] = {"thinking_false_verified": True}
        self.assertEqual(verify_lock(lock), self.root.resolve())
        lock["provenance"] = "snapshot_path_matches_revision"
        with self.assertRaisesRegex(ValueError, "provenance is unverified"):
            verify_lock(lock)


if __name__ == "__main__":
    unittest.main()
