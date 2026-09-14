"""Content-addressed manifests and immutable, resumable result shards."""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import subprocess
import threading
import time
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
        self._event_lock = threading.Lock()
        self._event_path = self.path / f"events-{time.time_ns()}-{os.getpid()}.jsonl"
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
        self._recover_durable_results()

    def _recover_durable_results(self) -> None:
        """Promote complete fsynced raw outputs, preserving interrupted tails.

        Each store opening writes a new event segment. A partial final line is
        retained in its original file and is never concatenated with new data.
        Legacy unchecksummed results are not promoted or silently trusted.
        """
        recovered: dict[str, dict[str, Any]] = {}
        paths = sorted(self.path.glob("events*.jsonl"))
        for path in paths:
            with path.open("rb") as handle:
                lines = handle.readlines()
            for line_number, line in enumerate(lines, 1):
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeDecodeError) as exc:
                    if line_number == len(lines) and not line.endswith(b"\n"):
                        self.event("interrupted_event_tail_preserved", file=path.name,
                                   line=line_number, tail_sha256=hashlib.sha256(line).hexdigest())
                        continue
                    raise ValueError(f"Corrupt event log {path.name}:{line_number}") from exc
                if event.get("event") != "raw_result" or "row_sha256" not in event:
                    continue
                row = event["row"]
                if digest(row) != event["row_sha256"]:
                    raise ValueError(f"Corrupt raw output in {path.name}:{line_number}")
                key = row["example_id"]
                existing = self.rows.get(key, recovered.get(key))
                if existing is not None and existing != row:
                    raise ValueError(f"Conflicting durable outputs for {key}")
                if key not in self.rows:
                    recovered[key] = row
        if recovered:
            self.commit(list(recovered.values()))
            self.event("durable_results_recovered", examples=len(recovered))

    def event(self, event: str, **fields: Any) -> None:
        if event == "raw_result":
            fields["row_sha256"] = digest(fields["row"])
        with self._event_lock:
            with self._event_path.open("ab") as handle:
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


class PhaseBudget:
    """Persistent Phase 0 GPU-time charging across conditions and resumes.

    Call only while holding the global research worker lock. An orphaned
    attempt is conservatively charged until reconciliation, explicitly marked
    uncertain; that charge is not reported as measured GPU computation.
    """

    def __init__(self, path: Path, limit_seconds: float) -> None:
        if isinstance(limit_seconds, bool) or not isinstance(limit_seconds, (int, float)) or not math.isfinite(limit_seconds) or not 0 < limit_seconds <= 5 * 3600:
            raise ValueError("Phase 0 GPU budget must be finite, positive and at most five hours")
        self.path = path
        self.limit_seconds = limit_seconds
        self._lock = threading.Lock()
        self._started_monotonic: float | None = None
        self._attempt_id: str | None = None
        self.state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
            "schema_version": 1, "stage": "P0", "attempts": []}
        if self.state.get("schema_version") != 1 or self.state.get("stage") != "P0":
            raise ValueError("Unknown phase-budget ledger schema")
        identifiers: set[str] = set()
        for attempt in self.state["attempts"]:
            amount = attempt.get("charged_seconds")
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount < 0:
                raise ValueError("Invalid charged seconds in the phase-budget ledger")
            if attempt.get("status") not in {"running", "finished", "orphaned_conservative_charge"}:
                raise ValueError("Invalid attempt status in the phase-budget ledger")
            if not isinstance(attempt.get("attempt_id"), str) or not attempt["attempt_id"] or attempt["attempt_id"] in identifiers:
                raise ValueError("Missing or duplicate budget attempt ID")
            identifiers.add(attempt["attempt_id"])
            if attempt["status"] == "running":
                wall = (datetime.now(timezone.utc) - datetime.fromisoformat(attempt["started_at"])).total_seconds()
                if wall < 0:
                    raise ValueError("Budget ledger is dated in the future")
                attempt["charged_seconds"] = max(attempt["charged_seconds"], wall)
                attempt["status"] = "orphaned_conservative_charge"
                attempt["charge_is_measured_gpu_runtime"] = False
                attempt["reconciled_at"] = now()
        atomic_json(self.path, self.state)

    @property
    def charged_seconds(self) -> float:
        return sum(attempt["charged_seconds"] for attempt in self.state["attempts"])

    def start(self, attempt_id: str, run_id: str) -> None:
        if self._attempt_id is not None:
            raise ValueError("A budget attempt is already active")
        if self.charged_seconds >= self.limit_seconds:
            raise RuntimeError("Cumulative Phase 0 GPU time budget is exhausted")
        if any(attempt["attempt_id"] == attempt_id for attempt in self.state["attempts"]):
            raise ValueError("Duplicate budget attempt ID")
        self._attempt_id = attempt_id
        self._started_monotonic = time.monotonic()
        self.state["attempts"].append({"attempt_id": attempt_id, "run_id": run_id,
            "started_at": now(), "status": "running", "charged_seconds": 0.0,
            "charge_is_measured_gpu_runtime": True,
            "measurement_scope": "admitted_single_gpu_worker_wall_time_including_loading_and_idle"})
        atomic_json(self.path, self.state)

    def checkpoint(self, *, finish: bool = False) -> float:
        with self._lock:
            if self._started_monotonic is None:
                return self.charged_seconds
            elapsed = time.monotonic() - self._started_monotonic
            attempt = next(item for item in self.state["attempts"] if item["attempt_id"] == self._attempt_id)
            attempt["charged_seconds"] = max(attempt["charged_seconds"], elapsed)
            attempt["last_checkpoint_at"] = now()
            if finish:
                attempt["status"] = "finished"
                attempt["finished_at"] = now()
            atomic_json(self.path, self.state)
            if finish:
                self._started_monotonic = None
                self._attempt_id = None
            return self.charged_seconds

    def remaining_seconds(self) -> float:
        total = self.charged_seconds
        if self._started_monotonic is not None:
            recorded = next(item["charged_seconds"] for item in self.state["attempts"] if item["attempt_id"] == self._attempt_id)
            total += max(0.0, time.monotonic() - self._started_monotonic - recorded)
        return self.limit_seconds - total


def environment() -> dict[str, Any]:
    from importlib.metadata import PackageNotFoundError, version
    packages = {}
    for name in ("torch", "transformers", "tokenizers", "huggingface-hub", "safetensors", "numpy", "accelerate"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "platform": platform.platform(), "packages": packages}
