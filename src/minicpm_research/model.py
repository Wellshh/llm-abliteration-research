"""Pinned, read-only official checkpoint inspection and a minimal Llama loader.

The audit reads safetensors headers without importing torch or loading weights.
No remote model code, quantization, device sharding, or training is enabled.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import struct
from collections import Counter
from pathlib import Path
from typing import Any

OFFICIAL_MODEL = "openbmb/MiniCPM5-2B"
OFFICIAL_ENDPOINT = "https://huggingface.co"
ALLOWED_MODEL_ENDPOINTS = (OFFICIAL_ENDPOINT, "https://hf-mirror.com")
HUB_METADATA_TIMEOUT_SECONDS = 30
_SHA = re.compile(r"^[0-9a-f]{40}$")
_DTYPE_BYTES = {"BOOL": 1, "U8": 1, "I8": 1, "I16": 2, "U16": 2,
                "F16": 2, "BF16": 2, "I32": 4, "U32": 4, "F32": 4,
                "I64": 8, "U64": 8, "F64": 8}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _revision(revision: str) -> str:
    if not isinstance(revision, str) or not _SHA.fullmatch(revision):
        raise ValueError("revision must be a full lowercase 40-character commit SHA")
    return revision


def environment_versions() -> dict[str, Any]:
    result: dict[str, Any] = {"python": platform.python_version()}
    for package in ("torch", "transformers", "tokenizers", "safetensors", "huggingface-hub"):
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = None
    return result


def model_endpoint(endpoint: str | None = None) -> str:
    """Only the official endpoint or the user-authorized mirror is supported."""
    value = (endpoint or os.environ.get("HF_ENDPOINT") or OFFICIAL_ENDPOINT).rstrip("/")
    if value not in ALLOWED_MODEL_ENDPOINTS:
        raise ValueError("model endpoint must be https://huggingface.co or the authorized https://hf-mirror.com")
    return value


def _locked_file(root: Path, name: str, metadata: dict[str, Any]) -> Path:
    if (not isinstance(name, str) or not name or name in {".", ".."}
            or any(character in name for character in ("/", "\\", ":", "\0"))):
        raise ValueError("locked model filenames must be plain top-level filenames")
    path = root / name
    size = metadata.get("bytes")
    if type(size) is not int or size < 0 or not path.is_file() or path.stat().st_size != size:
        raise ValueError(f"locked model file byte count differs or file is missing: {name}")
    if not isinstance(metadata.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"]):
        raise ValueError(f"invalid locked SHA256: {name}")
    return path


def resolve_revision(ref: str = "main", *, endpoint: str | None = None) -> str:
    """Resolve once with a bounded metadata request, then persist the returned SHA."""
    from huggingface_hub import HfApi
    selected = model_endpoint(endpoint)
    return _revision(HfApi(endpoint=selected).model_info(
        OFFICIAL_MODEL, revision=ref, timeout=HUB_METADATA_TIMEOUT_SECONDS).sha)


def download_model(revision: str, cache_dir: str | Path | None = None, *, endpoint: str | None = None) -> Path:
    """Download the pinned repository snapshot through the explicitly selected endpoint."""
    from huggingface_hub import HfApi, snapshot_download
    revision = _revision(revision)
    selected = model_endpoint(endpoint)
    if HfApi(endpoint=selected).model_info(
            OFFICIAL_MODEL, revision=revision, timeout=HUB_METADATA_TIMEOUT_SECONDS).sha != revision:
        raise ValueError("the selected repository endpoint did not resolve to the requested SHA")
    return Path(snapshot_download(
        OFFICIAL_MODEL, revision=revision, cache_dir=str(cache_dir) if cache_dir else None,
        endpoint=selected, etag_timeout=HUB_METADATA_TIMEOUT_SECONDS,
        allow_patterns=["*.json", "*.jinja", "*.safetensors", "*.model", "*.txt", "*.tiktoken"],
    ))


def verify_official_file_hashes(manifest: dict[str, Any], *, endpoint: str | None = None) -> None:
    """Verify the pinned repository tree; mirror evidence is explicitly identified.

    The public name is kept for existing callers. A mirror verification is never
    recorded as a direct verification against the official Hugging Face endpoint.
    """
    from huggingface_hub import HfApi
    selected = model_endpoint(endpoint)
    revision = _revision(manifest["revision_sha"])
    if manifest.get("repo_id") != OFFICIAL_MODEL:
        raise ValueError("only the official openbmb repository identifier is permitted")
    api = HfApi(endpoint=selected)
    info = api.model_info(
        OFFICIAL_MODEL, revision=revision, files_metadata=True, timeout=HUB_METADATA_TIMEOUT_SECONDS)
    if info.sha != revision:
        raise ValueError("repository endpoint resolved to a different revision")
    siblings = {s.rfilename: s for s in info.siblings}
    metadata_method = "model_info"
    # hf-mirror may omit blob/LFS details in model_info; its pinned tree
    # exposes them. Keep the user's working tree-endpoint verification.
    if any(name not in siblings or not (
            getattr(siblings[name], "lfs", None) or getattr(siblings[name], "blob_id", None))
            for name in manifest["files"]):
        siblings = {item.path: item for item in api.list_repo_tree(
            OFFICIAL_MODEL, revision=revision, recursive=False) if hasattr(item, "blob_id")}
        metadata_method = "list_repo_tree"
    root = Path(manifest["local_dir"])
    verified = {}
    for name, metadata in manifest["files"].items():
        path = _locked_file(root, name, metadata)
        sibling = siblings.get(name)
        if sibling is None:
            raise ValueError(f"local file is absent from the pinned repository tree: {name}")
        actual_sha256 = sha256_file(path)
        if actual_sha256 != metadata["sha256"]:
            raise ValueError(f"local file changed since its audit: {name}")
        if sibling.lfs:
            expected = sibling.lfs.get("sha256") if isinstance(sibling.lfs, dict) else sibling.lfs.sha256
            actual = actual_sha256
            algorithm = "sha256"
        else:
            digest = hashlib.sha1(f"blob {metadata['bytes']}\0".encode())
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                    digest.update(chunk)
            actual, expected, algorithm = digest.hexdigest(), sibling.blob_id, "git_blob_sha1"
        if actual != expected:
            raise ValueError(f"local contents differ from the pinned repository file: {name}")
        verified[name] = {"algorithm": algorithm, "digest": actual}
    manifest["repository_file_hashes"] = verified
    manifest["repository_endpoint"] = selected
    manifest["metadata_endpoint"] = selected
    manifest["hash_verification_endpoint"] = selected
    manifest["hash_metadata_method"] = metadata_method
    if selected == OFFICIAL_ENDPOINT:
        manifest["official_file_hashes"] = verified
        manifest["provenance"] = "official_file_hashes_verified"
    else:
        manifest.pop("official_file_hashes", None)
        manifest["provenance"] = "repository_file_hashes_verified"
    manifest["direct_official_endpoint_verification"] = selected == OFFICIAL_ENDPOINT


def inspect_safetensors(path: str | Path) -> dict[str, Any]:
    """Validate metadata and byte ranges without deserializing any tensor values."""
    path = Path(path)
    size = path.stat().st_size
    with path.open("rb") as handle:
        raw_length = handle.read(8)
        if len(raw_length) != 8:
            raise ValueError(f"truncated safetensors header: {path.name}")
        length = struct.unpack("<Q", raw_length)[0]
        if not 2 <= length <= min(100_000_000, size - 8):
            raise ValueError(f"invalid safetensors header length: {path.name}")
        header = json.loads(handle.read(length))
    if not isinstance(header, dict):
        raise ValueError("safetensors header is not a JSON object")
    tensors: dict[str, Any] = {}
    ranges = []
    dtype_elements: Counter[str] = Counter()
    for name, item in header.items():
        if name == "__metadata__":
            continue
        dtype, shape, offsets = item["dtype"], item["shape"], item["data_offsets"]
        if dtype not in _DTYPE_BYTES:
            raise ValueError(f"unsupported/unreviewed tensor dtype {dtype}")
        if not isinstance(shape, list) or any(type(d) is not int or d < 0 for d in shape):
            raise ValueError(f"invalid tensor shape: {name}")
        if (not isinstance(offsets, list) or len(offsets) != 2
                or any(type(o) is not int for o in offsets)):
            raise ValueError(f"invalid tensor byte offsets: {name}")
        elements = math.prod(shape)
        start, end = offsets
        if start < 0 or end < start or end > size - 8 - length:
            raise ValueError(f"tensor outside safetensors file: {name}")
        if end - start != elements * _DTYPE_BYTES[dtype]:
            raise ValueError(f"tensor shape/dtype byte length mismatch: {name}")
        ranges.append((start, end, name))
        dtype_elements[dtype] += elements
        tensors[name] = {"shape": shape, "dtype": dtype, "elements": elements}
    end = 0
    for start, stop, name in sorted(ranges):
        if start != end:
            raise ValueError(f"overlapping or noncontiguous safetensors data: {name}")
        end = stop
    if end != size - length - 8:
        raise ValueError("unaccounted safetensors payload bytes")
    return {"tensor_count": len(tensors), "tensor_element_count": sum(dtype_elements.values()),
            "dtype_elements": dict(dtype_elements), "tensors": tensors,
            "header_sha256": hashlib.sha256(json.dumps(header, sort_keys=True).encode()).hexdigest()}


def _template(root: Path, tokenizer_config: dict[str, Any]) -> tuple[str, str]:
    if (root / "chat_templates").exists():
        raise ValueError("named chat_templates directories require explicit per-template locking")
    if (root / "chat_template.jinja").is_file():
        return (root / "chat_template.jinja").read_text(encoding="utf-8"), "chat_template.jinja"
    value = tokenizer_config.get("chat_template")
    if not isinstance(value, str) or not value:
        raise ValueError("a single native chat template is required; inspect multi-template models explicitly")
    return value, "tokenizer_config.json:chat_template"


def audit_model(local_dir: str | Path, revision: str, *, require_weights: bool = True) -> dict[str, Any]:
    root = Path(local_dir).resolve()
    revision = _revision(revision)
    config = _json(root / "config.json")
    tokenizer_config = _json(root / "tokenizer_config.json")
    if config.get("model_type") != "llama" or config.get("architectures") != ["LlamaForCausalLM"]:
        raise ValueError("this minimum loader supports only verified LlamaForCausalLM files")
    if config.get("quantization_config"):
        raise ValueError("quantized primary checkpoints are prohibited")
    template, template_source = _template(root, tokenizer_config)
    files = sorted(p for p in root.iterdir() if p.is_file() and
                   p.suffix in {".json", ".jinja", ".safetensors", ".model", ".txt", ".tiktoken"})
    weights = [p for p in files if p.suffix == ".safetensors"]
    if require_weights and not weights:
        raise ValueError("no safetensors weights found; download the pinned official snapshot first")
    summaries, names, dtype_elements = {}, set(), Counter()
    for path in weights:
        summary = inspect_safetensors(path)
        if names.intersection(summary["tensors"]):
            raise ValueError("tensor names duplicated across weight shards")
        names.update(summary["tensors"])
        dtype_elements.update(summary["dtype_elements"])
        summaries[path.name] = summary
    index_path = root / "model.safetensors.index.json"
    if index_path.is_file():
        weight_map = _json(index_path)["weight_map"]
        if set(weight_map) != names:
            raise ValueError("safetensors index and actual tensors disagree")
        for name, shard in weight_map.items():
            if shard not in summaries or name not in summaries[shard]["tensors"]:
                raise ValueError("safetensors index contains an incorrect shard reference")
    float_dtypes = set(dtype_elements) - {"BF16"}
    if require_weights and float_dtypes:
        raise ValueError(f"primary checkpoint requires BF16 storage; observed {dict(dtype_elements)}")
    return {
        "schema_version": 2, "repo_id": OFFICIAL_MODEL, "revision_sha": revision,
        "local_dir": str(root), "provenance": "snapshot_path_matches_revision" if
        root.name == revision and root.parent.name == "snapshots" else "caller_supplied_revision_requires_provenance_review",
        "config": config, "files": {p.name: {"sha256": sha256_file(p), "bytes": p.stat().st_size} for p in files},
        "chat_template_source": template_source,
        "chat_template_sha256": hashlib.sha256(template.encode()).hexdigest(),
        "thinking_keyword_present": "enable_thinking" in template,
        "weight_headers": summaries, "stored_tensor_element_count": sum(dtype_elements.values()),
        "stored_dtype_elements": dict(dtype_elements), "weights_verified": bool(weights),
        "environment": environment_versions(), "trust_remote_code": False,
        "primary_precision": "bfloat16", "compile_enabled": False,
    }


def render_prompt(tokenizer: Any, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None = None) -> str:
    kwargs: dict[str, Any] = {"tokenize": False, "add_generation_prompt": True, "enable_thinking": False}
    if tools is not None:
        kwargs["tools"] = tools
    return tokenizer.apply_chat_template(messages, **kwargs)


def token_anchors(tokenizer: Any, messages: list[dict[str, Any]] | None = None,
                  labels: tuple[str, ...] = ("A", "B", "C"), *,
                  tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    messages = messages or [{"role": "user", "content": "Reply with exactly one label: A, B, or C."}]
    prompt = render_prompt(tokenizer, messages, tools=tools)
    thinking_kwargs: dict[str, Any] = {"tokenize": False, "add_generation_prompt": True, "enable_thinking": True}
    if tools is not None:
        # The thinking-branch verification must compare the SAME tool context (review P2:
        # T anchors rendered without tools do not describe the real generation input).
        thinking_kwargs["tools"] = tools
    with_thinking = tokenizer.apply_chat_template(messages, **thinking_kwargs)
    if prompt == with_thinking:
        raise ValueError("enable_thinking=False has not been verified: rendered templates are identical")
    ids = tokenizer.encode(prompt, add_special_tokens=False)
    contexts = {}
    for label in labels:
        combined = tokenizer.encode(prompt + label, add_special_tokens=False)
        prefix = 0
        while prefix < min(len(ids), len(combined)) and ids[prefix] == combined[prefix]:
            prefix += 1
        contexts[label] = {"context_token_ids": combined, "common_prefix_length": prefix,
                           "prompt_tail_retokenized": prefix != len(ids),
                           "continuation_token_ids": combined[prefix:]}
    return {"messages": messages, "rendered_prompt": prompt, "prompt_token_ids": ids,
            "last_prompt_token_index": len(ids) - 1, "thinking_false_verified": True,
            "label_contexts": contexts, "label_probabilities_require_sequence_scoring":
            any(v["prompt_tail_retokenized"] or len(v["continuation_token_ids"]) != 1 for v in contexts.values())}


def verify_lock(lock: dict[str, Any], local_dir: str | Path | None = None) -> Path:
    if lock.get("repo_id") != OFFICIAL_MODEL or not lock.get("weights_verified"):
        raise ValueError("a complete official-model lock is required")
    _revision(lock["revision_sha"])
    provenance = lock.get("provenance")
    if provenance not in {"official_file_hashes_verified", "repository_file_hashes_verified", "mirror_file_hashes_verified"}:
        raise ValueError("model provenance is unverified; compare local files with a permitted pinned repository endpoint")
    endpoint = lock.get("repository_endpoint", lock.get("hash_verification_endpoint",
        OFFICIAL_ENDPOINT if provenance == "official_file_hashes_verified" else None))
    if endpoint not in ALLOWED_MODEL_ENDPOINTS:
        raise ValueError("model lock has an unapproved or missing repository endpoint")
    if provenance == "official_file_hashes_verified" and endpoint != OFFICIAL_ENDPOINT:
        raise ValueError("mirror provenance must not claim direct official endpoint verification")
    if provenance == "mirror_file_hashes_verified" and endpoint != "https://hf-mirror.com":
        raise ValueError("legacy mirror lock must identify the user-authorized mirror endpoint")
    if lock.get("metadata_endpoint", endpoint) != endpoint or lock.get("download_endpoint") not in (None, endpoint):
        raise ValueError("model lock has inconsistent metadata/download endpoints")
    if not lock.get("token_anchors", {}).get("thinking_false_verified"):
        raise ValueError("native thinking=False/tokenization audit is missing")
    root = Path(local_dir or lock["local_dir"]).resolve()
    if (root / "chat_templates").exists():
        raise ValueError("unlocked named chat_templates directory is not supported")
    current_files = {p.name for p in root.iterdir() if p.is_file() and
                     p.suffix in {".json", ".jinja", ".safetensors", ".model", ".txt", ".tiktoken"}}
    if current_files != set(lock["files"]):
        raise ValueError("model file inventory changed since the lock was created")
    for name, info in lock["files"].items():
        path = _locked_file(root, name, info)
        if sha256_file(path) != info["sha256"]:
            raise ValueError(f"locked model file hash changed: {name}")
    return root


def load_locked_model(lock_path: str | Path, *, device: str = "cpu", dtype: str = "bfloat16",
                      attention_backend: str = "eager", local_dir: str | Path | None = None) -> tuple[Any, Any]:
    """Resource admission must precede CUDA calls; the runner owns that gate."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if dtype not in {"bfloat16", "float32"} or attention_backend not in {"eager", "sdpa"}:
        raise ValueError("unsupported precision or attention backend")
    if device not in {"cpu", "cuda:0"}:
        raise ValueError("only CPU or the single admitted logical cuda:0 is supported")
    lock = _json(Path(lock_path))
    root = verify_lock(lock, local_dir)
    current_versions = environment_versions()
    for package in ("torch", "transformers", "tokenizers", "safetensors"):
        locked = lock.get("environment", {}).get(package)
        if locked and current_versions[package] != locked:
            raise ValueError(f"locked runtime version mismatch for {package}: re-audit environment explicitly")
    tokenizer = AutoTokenizer.from_pretrained(root, local_files_only=True, trust_remote_code=False)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        if tokenizer.eos_token_id is None:
            raise ValueError("tokenizer has neither pad nor EOS token")
        tokenizer.pad_token = tokenizer.eos_token
    if token_anchors(tokenizer) != lock["token_anchors"]:
        raise ValueError("rendering or label tokenization differs from locked native template")
    model = AutoModelForCausalLM.from_pretrained(
        root, local_files_only=True, trust_remote_code=False, use_safetensors=True,
        torch_dtype=getattr(torch, dtype), attn_implementation=attention_backend,
    )
    expected = lock["config"]
    if (type(model).__name__ != "LlamaForCausalLM"
            or len(model.model.layers) != expected["num_hidden_layers"]
            or model.model.embed_tokens.weight.shape[1] != expected["hidden_size"]):
        raise ValueError("actual loaded architecture/module shape differs from audited config")
    measured_count = sum(p.numel() for p in model.parameters())
    if measured_count != lock["stored_tensor_element_count"]:
        raise ValueError("loaded parameter count differs from audited stored tensors; review ties/buffers")
    hidden_size = expected["hidden_size"]
    heads = expected["num_attention_heads"]
    kv_heads = expected.get("num_key_value_heads", heads)
    head_dim = expected.get("head_dim", hidden_size // heads)
    actual_shapes = {}
    for index, block in enumerate(model.model.layers):
        expected_shapes = {
            "self_attn.q_proj": (heads * head_dim, hidden_size),
            "self_attn.k_proj": (kv_heads * head_dim, hidden_size),
            "self_attn.v_proj": (kv_heads * head_dim, hidden_size),
            "self_attn.o_proj": (hidden_size, heads * head_dim),
            "mlp.gate_proj": (expected["intermediate_size"], hidden_size),
            "mlp.up_proj": (expected["intermediate_size"], hidden_size),
            "mlp.down_proj": (hidden_size, expected["intermediate_size"]),
        }
        for name, shape in expected_shapes.items():
            actual = tuple(block.get_submodule(name).weight.shape)
            if actual != shape:
                raise ValueError(f"actual layer {index} {name} shape differs from the locked config")
            actual_shapes[f"model.layers.{index}.{name}.weight"] = list(actual)
    model._minicpm_research_architecture_audit = {
        "actual_class": type(model).__name__, "parameter_count": measured_count,
        "actual_module_weight_shapes": actual_shapes,
        "parameter_dtypes": sorted({str(p.dtype) for p in model.parameters()}),
    }
    model.eval()
    model.requires_grad_(False)
    model.to(device)
    return model, tokenizer
