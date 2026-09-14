"""Resolve/download/audit the official model without allocating a GPU."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from minicpm_research.model import (audit_model, download_model, resolve_revision, token_anchors,
                                    verify_official_file_hashes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    revisions = parser.add_mutually_exclusive_group(required=True)
    revisions.add_argument("--revision", help="full official 40-character commit SHA")
    revisions.add_argument("--resolve-revision", metavar="REF", help="resolve an official ref once and persist its SHA")
    parser.add_argument("--local-dir", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--endpoint", default=None,
                        help="HF endpoint for revision/download/hash verification (e.g. https://hf-mirror.com); default = official Hub")
    parser.add_argument("--output", type=Path, default=Path("artifacts/model/MODEL_MANIFEST.json"))
    parser.add_argument("--metadata-only", action="store_true", help="audit local metadata; produces an incomplete non-runnable lock")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; use a new output path to preserve the prior audit")
    if args.metadata_only and args.local_dir is None:
        parser.error("--metadata-only requires --local-dir")
    revision = args.revision or resolve_revision(args.resolve_revision, endpoint=args.endpoint)
    print(json.dumps({"resolved_official_revision": revision}), flush=True)
    root = args.local_dir or download_model(revision, args.cache_dir, endpoint=args.endpoint)
    manifest = audit_model(root, revision, require_weights=not args.metadata_only)
    if not args.metadata_only:
        verify_official_file_hashes(manifest, endpoint=args.endpoint)
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(root, local_files_only=True, trust_remote_code=False)
        manifest["token_anchors"] = token_anchors(tokenizer)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    with tmp.open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, args.output)
    print(json.dumps({"manifest": str(args.output.resolve()), "revision": revision,
                      "endpoint": args.endpoint, "provenance": manifest.get("provenance"),
                      "weights_verified": manifest["weights_verified"],
                      "tensor_elements": manifest["stored_tensor_element_count"]}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, ImportError, RuntimeError) as exc:
        print(f"model lock failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
