"""Model metadata checks run without torch or network access."""
from __future__ import annotations

import json
import hashlib
import os
import sys
import types
import struct
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from minicpm_research.model import audit_model, inspect_safetensors, token_anchors, verify_lock, verify_official_file_hashes, model_endpoint, resolve_revision, download_model


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

    def test_local_revision_claim_is_not_trusted_provenance(self) -> None:
        result = audit_model(self.root, "a" * 40)
        result["token_anchors"] = {"thinking_false_verified": True}
        with self.assertRaisesRegex(ValueError, "provenance"):
            verify_lock(result)

    def test_official_tree_verification_checks_lfs_and_git_blobs(self) -> None:
        result = audit_model(self.root, "a" * 40)
        siblings = []
        for name, info in result["files"].items():
            content = (self.root / name).read_bytes()
            lfs = {"sha256": info["sha256"]} if name.endswith("safetensors") else None
            siblings.append(types.SimpleNamespace(rfilename=name, lfs=lfs,
                blob_id=hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()))
        api = types.SimpleNamespace(model_info=lambda *args, **kwargs:
                                    types.SimpleNamespace(sha="a" * 40, siblings=siblings))
        hub = types.SimpleNamespace(HfApi=lambda **kwargs: api)
        with mock.patch.dict(sys.modules, {"huggingface_hub": hub}):
            verify_official_file_hashes(result, endpoint="https://huggingface.co")
            self.assertEqual(result["provenance"], "official_file_hashes_verified")
            self.assertEqual(result["official_file_hashes"]["model.safetensors"]["algorithm"], "sha256")
            self.assertEqual(result["official_file_hashes"]["config.json"]["algorithm"], "git_blob_sha1")
            def mirror_info(*args, **kwargs):
                self.assertEqual(kwargs["timeout"], 30)
                return types.SimpleNamespace(sha="a" * 40, siblings=siblings)
            api.model_info = mirror_info
            verify_official_file_hashes(result, endpoint="https://hf-mirror.com")
            self.assertEqual(result["provenance"], "repository_file_hashes_verified")
            self.assertEqual(result["metadata_endpoint"], "https://hf-mirror.com")
            self.assertFalse(result["direct_official_endpoint_verification"])
            self.assertNotIn("official_file_hashes", result)
            siblings[-1].blob_id = "0" * 40
            if siblings[-1].lfs:
                siblings[-1].lfs["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "pinned repository"):
                verify_official_file_hashes(result, endpoint="https://huggingface.co")

    def test_mirror_lock_is_accepted_without_claiming_direct_official_verification(self) -> None:
        result = audit_model(self.root, "a" * 40)
        result.update({"token_anchors": {"thinking_false_verified": True},
            "provenance": "repository_file_hashes_verified", "repository_endpoint": "https://hf-mirror.com",
            "metadata_endpoint": "https://hf-mirror.com", "download_endpoint": "https://hf-mirror.com"})
        self.assertEqual(verify_lock(result), self.root.resolve())
        result["provenance"] = "official_file_hashes_verified"
        with self.assertRaisesRegex(ValueError, "mirror provenance"):
            verify_lock(result)

    def test_locked_bytes_and_path_inventory_are_checked(self) -> None:
        result = audit_model(self.root, "a" * 40)
        result.update({"token_anchors": {"thinking_false_verified": True}, "provenance": "official_file_hashes_verified"})
        result["files"]["config.json"]["bytes"] += 1
        with self.assertRaisesRegex(ValueError, "byte count"):
            verify_lock(result)
        result["files"]["../outside.json"] = result["files"].pop("config.json")
        with self.assertRaisesRegex(ValueError, "inventory"):
            verify_lock(result)

    def test_unlocked_named_template_directory_is_rejected(self) -> None:
        result = audit_model(self.root, "a" * 40)
        result.update({"token_anchors": {"thinking_false_verified": True}, "provenance": "official_file_hashes_verified"})
        (self.root / "chat_templates").mkdir()
        (self.root / "chat_templates" / "tool_use.jinja").write_text("unlocked", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "chat_templates"):
            verify_lock(result)
        with self.assertRaisesRegex(ValueError, "chat_templates"):
            audit_model(self.root, "a" * 40)

    def test_lock_detects_file_change(self) -> None:
        result = audit_model(self.root, "a" * 40)
        result["token_anchors"] = {"thinking_false_verified": True}
        result["provenance"] = "official_file_hashes_verified"
        self.assertEqual(verify_lock(result), self.root.resolve())
        (self.root / "config.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "hash changed|byte count"):
            verify_lock(result)


class EndpointTests(unittest.TestCase):
    def test_environment_mirror_and_endpoint_allowlist(self) -> None:
        with mock.patch.dict(os.environ, {"HF_ENDPOINT": "https://hf-mirror.com/"}):
            self.assertEqual(model_endpoint(), "https://hf-mirror.com")
        with self.assertRaises(ValueError):
            model_endpoint("https://unapproved.invalid")

    def test_resolve_download_forward_endpoint_and_metadata_timeout(self) -> None:
        requests = []
        downloads = []
        api = types.SimpleNamespace(model_info=lambda *args, **kwargs:
            (requests.append(kwargs) or types.SimpleNamespace(sha="b" * 40)))
        endpoints = []
        def make_api(**kwargs):
            endpoints.append(kwargs["endpoint"])
            return api
        hub = types.SimpleNamespace(HfApi=make_api, snapshot_download=lambda *args, **kwargs:
            (downloads.append(kwargs) or "/fake/pinned/snapshot"))
        with mock.patch.dict(sys.modules, {"huggingface_hub": hub}):
            self.assertEqual(resolve_revision(endpoint="https://hf-mirror.com"), "b" * 40)
            download_model("b" * 40, endpoint="https://hf-mirror.com")
        self.assertEqual(endpoints, ["https://hf-mirror.com", "https://hf-mirror.com"])
        self.assertTrue(all(request["timeout"] == 30 for request in requests))
        self.assertEqual(downloads[0]["endpoint"], "https://hf-mirror.com")
        self.assertEqual(downloads[0]["etag_timeout"], 30)


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


if __name__ == "__main__":
    unittest.main()
