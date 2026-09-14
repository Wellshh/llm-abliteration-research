"""Pinned, read-only official checkpoint inspection and a minimal Llama loader.

The audit reads safetensors headers without importing torch or loading weights.
No remote model code, quantization, device sharding, or training is enabled.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
import re
import struct
from collections import Counter
from pathlib import Path
from typing import Any

OFFICIAL_MODEL = "openbmb/MiniCPM5-2B"
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
    if not _SHA.fullmatch(revision):
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


def resolve_revision(ref: str = "main", endpoint: str | None = None) -> str:
    """Resolve a moving name once; the returned SHA must be persisted before runs."""
    from huggingface_hub import HfApi
    return _revision(HfApi(endpoint=endpoint).model_info(OFFICIAL_MODEL, revision=ref).sha)


def download_model(revision: str, cache_dir: str | Path | None = None, endpoint: str | None = None) -> Path:
    """Download the official unquantized snapshot, always at a complete SHA."""
    from huggingface_hub import HfApi, snapshot_download
    revision = _revision(revision)
    if HfApi(endpoint=endpoint).model_info(OFFICIAL_MODEL, revision=revision).sha != revision:
        raise ValueError("the official Hub repository did not resolve to the requested SHA")
    return Path(snapshot_download(
        OFFICIAL_MODEL, revision=revision, cache_dir=str(cache_dir) if cache_dir else None,
        endpoint=endpoint,
        allow_patterns=["*.json", "*.jinja", "*.safetensors", "*.model", "*.txt", "*.tiktoken"],
    ))


def verify_official_file_hashes(manifest: dict[str, Any], endpoint: str | None = None) -> None:
    """Bind local file contents to the pinned Hub tree at the exact revision.

    Uses the tree endpoint (``list_repo_tree``), which returns a git blob oid for
    every file and an LFS sha256 for LFS files on both the official Hub and a
    mirror. ``endpoint=None`` resolves to the official Hub; a mirror endpoint
    yields ``mirror_file_hashes_verified`` provenance, which binds local content
    to the mirror's tree at the SHA, NOT to the official Hub. Official-Hub
    re-verification stays pending until huggingface.co is reachable.
    """
    from huggingface_hub import HfApi
    from huggingface_hub.hf_api import RepoFile
    revision = _revision(manifest["revision_sha"])
    api = HfApi(endpoint=endpoint)
    tree = {f.path: f
            for f in api.list_repo_tree(OFFICIAL_MODEL, revision=revision, recursive=False)
            if isinstance(f, RepoFile)}
    root = Path(manifest["local_dir"])
    verified = {}
    for name, metadata in manifest["files"].items():
        remote = tree.get(name)
        if remote is None:
            raise ValueError(f"local file is absent from the pinned tree: {name}")
        if remote.lfs:
            expected, actual, algorithm = remote.lfs.sha256, metadata["sha256"], "sha256"
        else:
            digest = hashlib.sha1(f"blob {metadata['bytes']}\0".encode())
            with (root / name).open("rb") as handle:
                for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                    digest.update(chunk)
            actual, expected, algorithm = digest.hexdigest(), remote.blob_id, "git_blob_sha1"
        if actual != expected:
            raise ValueError(f"local contents differ from the pinned tree file: {name}")
        verified[name] = {"algorithm": algorithm, "digest": actual}
    official = api.endpoint.rstrip("/") == "https://huggingface.co"
    manifest["hash_verification_endpoint"] = api.endpoint
    manifest["official_file_hashes"] = verified
    manifest["provenance"] = "official_file_hashes_verified" if official else "mirror_file_hashes_verified"


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
        "schema_version": 1, "repo_id": OFFICIAL_MODEL, "revision_sha": revision,
        "local_dir": str(root), "snapshot_provenance": "snapshot_path_matches_revision" if
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
                  labels: tuple[str, ...] = ("A", "B", "C")) -> dict[str, Any]:
    messages = messages or [{"role": "user", "content": "Reply with exactly one label: A, B, or C."}]
    prompt = render_prompt(tokenizer, messages)
    with_thinking = tokenizer.apply_chat_template(messages, tokenize=False,
                                                   add_generation_prompt=True, enable_thinking=True)
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
    if lock.get("provenance") not in {"official_file_hashes_verified", "mirror_file_hashes_verified"}:
        raise ValueError("model provenance is unverified; compare local files with the pinned Hub tree hashes")
    if not lock.get("token_anchors", {}).get("thinking_false_verified"):
        raise ValueError("native thinking=False/tokenization audit is missing")
    root = Path(local_dir or lock["local_dir"]).resolve()
    current_files = {p.name for p in root.iterdir() if p.is_file() and
                     p.suffix in {".json", ".jinja", ".safetensors", ".model", ".txt", ".tiktoken"}}
    if current_files != set(lock["files"]):
        raise ValueError("model file inventory changed since the lock was created")
    for name, info in lock["files"].items():
        if Path(name).name != name or not (root / name).is_file():
            raise ValueError(f"invalid or missing locked model file: {name}")
        if sha256_file(root / name) != info["sha256"]:
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
    model.eval()
    model.requires_grad_(False)
    model.to(device)
    return model, tokenizer
