"""Content-addressed manifests and immutable, resumable result shards."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        handle.write(canonical(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def source_state(root: Path) -> dict[str, Any]:
    files = {}
    for pattern in ("src/**/*.py", "scripts/*.py", "configs/*.json", "pyproject.toml", "AGENTS.md", "PREREGISTRATION.yaml", "RESEARCH_PLAN.md", "SOURCES.json"):
        for path in sorted(root.glob(pattern)):
            files[path.relative_to(root).as_posix()] = file_hash(path)
    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    try:
        head = git("rev-parse", "HEAD")
        if head.returncode:
            return {"git_available": False, "git_commit": None, "git_diff": None,
                    "reason": "directory has no Git commit; source hashes are the reproducibility fallback", "source_sha256": files}
        return {"git_available": True, "git_commit": head.stdout.strip(), "git_diff": git("diff", "HEAD", "--no-ext-diff").stdout,
                "git_status": git("status", "--porcelain").stdout, "source_sha256": files}
    except FileNotFoundError:
        return {"git_available": False, "git_commit": None, "git_diff": None, "source_sha256": files}


class RunStore:
    """One writer (the entry point must hold a lock); never overwrite results."""
    def __init__(self, base: Path, manifest: dict[str, Any]) -> None:
        self.run_id = digest(manifest)[:20]
        self.path = base / self.run_id
        self.path.mkdir(parents=True, exist_ok=True)
        target = self.path / "manifest.json"
        if target.exists():
            if json.loads(target.read_text(encoding="utf-8")) != manifest:
                raise ValueError("run manifest mismatch")
        else:
            atomic_json(target, manifest)
        self.manifest = manifest
        self.rows: dict[str, dict[str, Any]] = {}
        for shard in sorted(self.path.glob("shard-*.json")):
            payload = json.loads(shard.read_text(encoding="utf-8"))
            if digest(payload["rows"]) != payload["rows_sha256"]:
                raise ValueError(f"corrupt completed shard: {shard.name}")
            for row in payload["rows"]:
                key = row["example_id"]
                if key in self.rows:
                    raise ValueError(f"duplicate completed example: {key}")
                self.rows[key] = row

    def event(self, event: str, **fields: Any) -> None:
        with (self.path / "events.jsonl").open("ab") as handle:
            handle.write(canonical({"at": now(), "event": event, **fields}) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())

    def commit(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        identifiers = [row["example_id"] for row in rows]
        if len(set(identifiers)) != len(identifiers) or set(identifiers) & self.rows.keys():
            raise ValueError("refusing duplicate result commit")
        target = self.path / f"shard-{len(list(self.path.glob('shard-*.json'))):06d}.json"
        if target.exists():
            raise ValueError("refusing to replace a committed shard")
        atomic_json(target, {"rows": rows, "rows_sha256": digest(rows)})
        self.rows.update({row["example_id"]: row for row in rows})


def environment() -> dict[str, Any]:
    from importlib.metadata import PackageNotFoundError, version
    packages = {}
    for name in ("torch", "transformers", "tokenizers", "huggingface-hub", "safetensors", "numpy", "accelerate"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "platform": platform.platform(), "packages": packages}
