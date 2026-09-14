"""Read-only resource evidence and fail-closed admission for one research worker.

No function in this module allocates CUDA memory, kills a process, changes a
scheduler, or releases a reservation. PyTorch allocator limits are NOT hard
whole-process isolation. The two 32 GiB reservations are separate from the
single allowed formal experiment worker.
"""

from __future__ import annotations

import csv
import importlib.metadata
import io
import json
import math
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

GIB = 1024**3
MIB = 1024**2
PRIMARY_GPU_UUID = "GPU-e5c246b7-afc2-cccd-e66d-fa1ca4eb089e"
BACKUP_GPU_UUID = "GPU-500c112e-cdd9-4e0d-d709-63de81493d96"
AUTHORIZED_GPUS = {PRIMARY_GPU_UUID: 3, BACKUP_GPU_UUID: 5}
MAX_BUDGET_GIB = 32
MIN_RESERVE_GIB = 12
MIN_AUDIT_SECONDS = 60
MAX_AUDIT_AGE_SECONDS = 30
GPU_FIELDS = (
    "index,uuid,name,driver_version,memory.total,memory.free,memory.used,"
    "utilization.gpu,temperature.gpu,power.draw,power.limit,mig.mode.current"
)
PROCESS_FIELDS = "gpu_uuid,pid,process_name,used_gpu_memory"
SCHEDULER_KEYS = (
    "SLURM_JOB_ID", "SLURM_JOBID", "SLURM_JOB_GPUS", "SLURM_STEP_GPUS",
    "PBS_JOBID", "PBS_GPUFILE", "LSB_JOBID", "LSB_GPU_ID", "SGE_JOB_ID",
)
ENVIRONMENT_KEYS = SCHEDULER_KEYS + (
    "CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER", "NVIDIA_VISIBLE_DEVICES",
)


class ResourceError(RuntimeError):
    """Resource evidence is incomplete or an admission constraint failed."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _number(value: str, *, required: bool = False) -> float | None:
    try:
        result = float(value.strip())
    except ValueError:
        if required:
            raise ResourceError(f"Required nvidia-smi numeric value unavailable: {value!r}")
        return None
    if not math.isfinite(result) or result < 0:
        raise ResourceError("Invalid negative or non-finite nvidia-smi value")
    return result


def parse_gpu_csv(raw: str) -> list[dict[str, Any]]:
    """Parse an exact noheader,nounits query; required memory cannot be unknown."""
    rows: list[dict[str, Any]] = []
    for fields in csv.reader(io.StringIO(raw), skipinitialspace=True):
        if not fields:
            continue
        if len(fields) != 12:
            raise ResourceError(f"GPU query expected 12 fields, received {len(fields)}")
        values = [field.strip() for field in fields]
        try:
            index = int(values[0])
        except ValueError as exc:
            raise ResourceError("Invalid physical GPU index") from exc
        total, free, used = (_number(item, required=True) for item in values[4:7])
        assert total is not None and free is not None and used is not None
        if index < 0 or total <= 0 or free > total or used > total:
            raise ResourceError("Invalid GPU memory or physical index")
        rows.append({
            "index": index, "uuid": values[1], "name": values[2],
            "driver_version": values[3], "memory_total_bytes": int(total * MIB),
            "memory_free_bytes": int(free * MIB), "memory_used_bytes": int(used * MIB),
            "utilization_gpu_percent": _number(values[7]),
            "temperature_gpu_c": _number(values[8]), "power_draw_w": _number(values[9]),
            "power_limit_w": _number(values[10]), "mig_mode_current": values[11],
        })
    if not rows:
        raise ResourceError("No GPUs returned by nvidia-smi")
    if len({row["uuid"] for row in rows}) != len(rows) or len({row["index"] for row in rows}) != len(rows):
        raise ResourceError("Duplicate GPU UUID or physical index")
    return rows


def parse_process_csv(raw: str) -> list[dict[str, Any]]:
    """Record compute processes, including unrelated users' existing workloads."""
    if raw.strip() in ("", "No running processes found"):
        return []
    rows = []
    for fields in csv.reader(io.StringIO(raw), skipinitialspace=True):
        if not fields:
            continue
        if len(fields) != 4:
            raise ResourceError("Compute-process query expected four fields")
        try:
            pid = int(fields[1].strip())
        except ValueError as exc:
            raise ResourceError("Invalid compute-process PID") from exc
        if pid <= 0:
            raise ResourceError("Invalid compute-process PID")
        memory = _number(fields[3])
        rows.append({"gpu_uuid": fields[0].strip(), "pid": pid,
                     "process_name": fields[2].strip(),
                     "used_gpu_memory_bytes": None if memory is None else int(memory * MIB)})
    return rows


def _command(argv: Sequence[str]) -> dict[str, Any]:
    started_at = _now()
    try:
        result = subprocess.run(list(argv), capture_output=True, text=True, timeout=20, check=False)
        return {"argv": list(argv), "started_at": started_at, "finished_at": _now(),
                "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"argv": list(argv), "started_at": started_at, "finished_at": _now(),
                "exit_code": None, "stdout": "", "stderr": str(exc)}


def _host_resources(path: Path) -> dict[str, Any]:
    disk = shutil.disk_usage(path)
    ram: dict[str, int] = {}
    memory_path = Path("/proc/meminfo")
    if memory_path.exists():
        for line in memory_path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition(":")
            if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                ram[key + "_bytes"] = int(value.split()[0]) * 1024
    return {"disk_path": str(path.resolve()), "disk_total_bytes": disk.total,
            "disk_free_bytes": disk.free, "ram": ram}


def capture_snapshot(disk_path: str | Path) -> dict[str, Any]:
    """One read-only snapshot, also suitable for pressure checks between chunks."""
    gpu = _command(["nvidia-smi", f"--query-gpu={GPU_FIELDS}", "--format=csv,noheader,nounits"])
    processes = _command(["nvidia-smi", f"--query-compute-apps={PROCESS_FIELDS}", "--format=csv,noheader,nounits"])
    errors: list[str] = []
    parsed_gpus: list[dict[str, Any]] = []
    parsed_processes: list[dict[str, Any]] = []
    for label, command, parser in (("gpus", gpu, parse_gpu_csv), ("processes", processes, parse_process_csv)):
        if command["exit_code"] != 0:
            errors.append(f"{label} query failed with exit code {command['exit_code']}")
            continue
        try:
            value = parser(command["stdout"])
            if label == "gpus":
                parsed_gpus = value
            else:
                parsed_processes = value
        except ResourceError as exc:
            errors.append(str(exc))
    return {"timestamp": _now(), "gpus": parsed_gpus, "processes": parsed_processes,
            "host": _host_resources(Path(disk_path)), "commands": [gpu, processes], "errors": errors}


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def audit_resources(output_dir: str | Path, *, seconds: float = 60,
                    interval_seconds: float = 5) -> dict[str, Any]:
    """Save actual commands and snapshots; a short snapshot never admits a run.

    Choose a new directory for every process start. Partial evidence is persisted
    after each sample, including on interruption; an old audit is never resumed.
    """
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("seconds must be finite and nonnegative")
    if not math.isfinite(interval_seconds) or not 0 < interval_seconds <= 60:
        raise ValueError("interval_seconds must be positive and at most 60")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / "RESOURCE_AUDIT.json"
    if report_path.exists():
        raise ResourceError("Audit already exists; choose a new output directory")
    versions: dict[str, str | None] = {}
    for package in ("torch", "transformers", "numpy", "safetensors", "huggingface-hub"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    report: dict[str, Any] = {
        "schema_version": 1, "kind": "read_only_resource_audit", "status": "running",
        "started_at": _now(), "requested_seconds": seconds, "interval_seconds": interval_seconds,
        "hostname": socket.gethostname(), "pid": os.getpid(),
        "platform": platform.platform(), "python": sys.version,
        "package_versions": versions,
        "device_environment": {key: os.environ[key] for key in ENVIRONMENT_KEYS if key in os.environ},
        "authorization": {"gpu_uuids_and_expected_indices": AUTHORIZED_GPUS,
                          "budget_gib_per_gpu": MAX_BUDGET_GIB, "reserve_gib": MIN_RESERVE_GIB,
                          "max_formal_workers": 1, "automatic_failover": False,
                          "allocator_fraction_is_hard_isolation": False},
        "initial_commands": [_command(["nvidia-smi", "-L"]), _command(["nvidia-smi", "-q"])],
        "samples": [], "gpu_experiment_run": False,
    }
    started = time.monotonic()
    try:
        while True:
            sample = capture_snapshot(destination)
            sample["elapsed_seconds"] = time.monotonic() - started
            report["samples"].append(sample)
            report["sampling_duration_seconds"] = sample["elapsed_seconds"] - report["samples"][0]["elapsed_seconds"]
            _atomic_json(report_path, report)
            remaining = seconds - report["sampling_duration_seconds"]
            if remaining <= 0:
                break
            time.sleep(min(interval_seconds, remaining))
        report["status"] = "complete"
    except BaseException:
        report["status"] = "interrupted"
        report["finished_at"] = _now()
        _atomic_json(report_path, report)
        raise
    report["finished_at"] = _now()
    report["formal_sampling_complete"] = seconds >= MIN_AUDIT_SECONDS and len(report["samples"]) >= 2
    _atomic_json(report_path, report)
    return report


def prepare_cuda_environment(gpu_uuid: str, env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return visibility-only settings without mutating the actual environment.

    An existing numeric/multiple/MIG binding is left untouched and rejected:
    this module cannot prove the scheduler's device-index mapping. A scheduler
    job must already expose precisely the selected full UUID.
    """
    if gpu_uuid not in AUTHORIZED_GPUS:
        raise ResourceError("GPU UUID is not one of the two explicitly authorized devices")
    current = os.environ if env is None else env
    visible = current.get("CUDA_VISIBLE_DEVICES")
    scheduler_present = any(current.get(key) for key in SCHEDULER_KEYS)
    if visible is not None and visible.strip() != gpu_uuid:
        raise ResourceError("Existing CUDA_VISIBLE_DEVICES conflicts or is not a verified single UUID; it will not be overridden")
    if scheduler_present and visible is None:
        raise ResourceError("Scheduler environment has no verified single-UUID CUDA binding; refusing to override it")
    for key in ("SLURM_JOB_GPUS", "SLURM_STEP_GPUS", "LSB_GPU_ID"):
        if current.get(key) and current[key].strip() != gpu_uuid:
            raise ResourceError(f"{key} is not a verified matching UUID; scheduler allocation requires independent verification")
    container_visible = current.get("NVIDIA_VISIBLE_DEVICES")
    if container_visible is not None and container_visible not in ("all", gpu_uuid):
        raise ResourceError("NVIDIA_VISIBLE_DEVICES does not prove the selected UUID is available")
    return {"CUDA_VISIBLE_DEVICES": visible if visible is not None else gpu_uuid}


def _reservation_pids(directory: str | Path | None) -> set[int]:
    if directory is None:
        return set()
    pids: set[int] = set()
    for path in Path(directory).glob("*.pid"):
        try:
            pid = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError) as exc:
            raise ResourceError(f"Unreadable reservation PID evidence: {path.name}") from exc
        if pid <= 0:
            raise ResourceError("Invalid reservation PID evidence")
        pids.add(pid)
    for path in Path(directory).glob("*.jsonl"):
        # Existing resident helpers may have different binary names. Their
        # newest lifecycle record is additional PID evidence, but historical
        # PID files alone never establish that a process is still running.
        try:
            with path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - 65536))
                lines = handle.read().splitlines()
            latest = json.loads(lines[-1]) if lines else {}
        except (OSError, ValueError) as exc:
            raise ResourceError(f"Unreadable reservation lifecycle evidence: {path.name}") from exc
        if latest.get("event") not in {"stopped", "admission_failed"} and "pid" in latest:
            pid = latest["pid"]
            if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
                raise ResourceError("Invalid reservation lifecycle PID")
            pids.add(pid)
    return pids


def require_admission(report: Mapping[str, Any], gpu_uuid: str = PRIMARY_GPU_UUID,
                      budget_gib: float = 32, reservation_dir: str | Path | None = None,
                      env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Require >=60 seconds of fresh evidence and the full budget plus reserve.

    The caller must hold ``single_worker_lock`` through audit, model loading,
    and execution. This gate never takes ownership of another process's memory.
    """
    cuda_environment = prepare_cuda_environment(gpu_uuid, env)
    if not math.isfinite(budget_gib) or not 0 < budget_gib <= MAX_BUDGET_GIB:
        raise ResourceError("Per-card budget must be positive and at most 32 GiB")
    if report.get("hostname") != socket.gethostname():
        raise ResourceError("Resource audit was collected on another host")
    if report.get("status") != "complete" or report.get("sampling_duration_seconds", 0) < MIN_AUDIT_SECONDS:
        raise ResourceError("Formal starts require a completed audit sampling at least 60 seconds")
    if report.get("requested_seconds", 0) < MIN_AUDIT_SECONDS:
        raise ResourceError("A quick snapshot cannot authorize a formal start")
    samples = report.get("samples", [])
    if len(samples) < 2:
        raise ResourceError("Formal admission requires multiple resource samples")
    try:
        timestamp = datetime.fromisoformat(samples[-1]["timestamp"])
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()
    except (KeyError, TypeError, ValueError) as exc:
        raise ResourceError("Audit timestamp is invalid") from exc
    if age < -1 or age > MAX_AUDIT_AGE_SECONDS:
        raise ResourceError("Audit is stale or dated in the future; collect a fresh audit")
    if any(command.get("exit_code") != 0 for command in report.get("initial_commands", [])) or len(report.get("initial_commands", [])) != 2:
        raise ResourceError("GPU list or full driver/MIG audit failed")
    budget_bytes = int(budget_gib * GIB)
    reserve_bytes = MIN_RESERVE_GIB * GIB
    reservation_pids = _reservation_pids(reservation_dir)
    minimum_free = None
    selected = None
    for sample in samples:
        if sample.get("errors"):
            raise ResourceError("One or more resource samples failed")
        matches = [gpu for gpu in sample.get("gpus", []) if gpu.get("uuid") == gpu_uuid]
        if len(matches) != 1 or matches[0].get("index") != AUTHORIZED_GPUS[gpu_uuid]:
            raise ResourceError("Authorized UUID/physical-index mapping was not verified")
        selected = matches[0]
        if selected.get("mig_mode_current", "").lower() != "disabled":
            raise ResourceError("MIG must be explicitly disabled for this whole-GPU protocol")
        free = selected.get("memory_free_bytes", -1)
        minimum_free = free if minimum_free is None else min(minimum_free, free)
        if free < budget_bytes + reserve_bytes:
            raise ResourceError("GPU free memory is below requested budget plus 12 GiB reserve")
        if sample.get("host", {}).get("disk_free_bytes", 0) < 15 * GIB:
            raise ResourceError("Disk free space is below the 15 GiB stop threshold")
        for process in sample.get("processes", []):
            if process.get("gpu_uuid") == gpu_uuid and (
                any(name in process.get("process_name", "").lower()
                    for name in ("gpu_reservation", "autoplacer-rl"))
                or process.get("pid") in reservation_pids
            ):
                raise ResourceError("A managed reservation is present on this UUID; separate-worker takeover is blocked and no process will be stopped")
    assert selected is not None
    return {"gpu_uuid": gpu_uuid, "physical_index": AUTHORIZED_GPUS[gpu_uuid],
            "logical_device": "cuda:0", "budget_bytes": budget_bytes,
            "reserve_bytes": reserve_bytes, "minimum_sampled_free_bytes": minimum_free,
            "memory_total_bytes": selected["memory_total_bytes"],
            "cuda_environment": cuda_environment, "admitted_at": _now(),
            "allocator_fraction_is_hard_isolation": False}


@contextmanager
def single_worker_lock(lock_path: str | Path) -> Iterator[dict[str, Any]]:
    """Linux advisory flock covering both authorized GPUs; never kill/reclaim.

    Every formal entry point must use the same repository lock path. The lock
    file remains after exit to avoid inode replacement races; its PID is only
    historical metadata and never grounds a kill or forced lock break.
    """
    if sys.platform != "linux":
        raise ResourceError("Formal GPU workers require Linux flock")
    import fcntl

    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ResourceError("Another formal research worker holds the global lock") from exc
        acquired = True
        metadata = {"pid": os.getpid(), "hostname": socket.gethostname(),
                    "started_at": _now(), "lock_path": str(path.resolve())}
        payload = (json.dumps(metadata, ensure_ascii=False) + "\n").encode("utf-8")
        os.ftruncate(descriptor, 0)
        os.write(descriptor, payload)
        os.fsync(descriptor)
        yield metadata
    finally:
        if acquired:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
