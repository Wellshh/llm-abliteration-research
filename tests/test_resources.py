"""No real NVIDIA commands or CUDA allocations are made by these tests."""

from __future__ import annotations

import copy
import json
import os
import socket
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minicpm_research.resources import (
    BACKUP_GPU_UUID, GIB, GPU_FIELDS, PRIMARY_GPU_UUID, ResourceError,
    canonical_gpu_uuid,
    audit_resources, parse_gpu_csv, parse_process_csv, prepare_cuda_environment,
    require_admission, single_worker_lock,
)

class GPUUuidCanonicalizationTests(unittest.TestCase):
    def test_accepts_full_uuid_with_optional_prefix_and_case(self):
        body = PRIMARY_GPU_UUID[4:]
        self.assertEqual(canonical_gpu_uuid(body.upper()), PRIMARY_GPU_UUID)
        self.assertEqual(canonical_gpu_uuid(PRIMARY_GPU_UUID), PRIMARY_GPU_UUID)

    def test_rejects_non_full_or_non_uuid_values(self):
        body = PRIMARY_GPU_UUID[4:]
        for value in (body[:8], "3", "MIG-GPU-" + body + "/1/0", None, ""):
            with self.subTest(value=value):
                with self.assertRaises(ResourceError):
                    canonical_gpu_uuid(value)


def gpu_csv(uuid: str = PRIMARY_GPU_UUID, index: int = 3, free_mib: int = 45056) -> str:
    return f"{index}, {uuid}, NVIDIA H100, 580.65.06, 97272, {free_mib}, 10000, 54, 43, 150.3, 700.0, Disabled\n"


def evidence() -> dict:
    sample = {"timestamp": datetime.now(timezone.utc).isoformat(),
              "gpus": parse_gpu_csv(gpu_csv() + gpu_csv(BACKUP_GPU_UUID, 5)),
              "processes": [], "errors": [], "host": {"disk_free_bytes": 15 * GIB}}
    return {"hostname": socket.gethostname(), "status": "complete", "requested_seconds": 60,
            "sampling_duration_seconds": 60, "initial_commands": [{"exit_code": 0}, {"exit_code": 0}],
            "samples": [copy.deepcopy(sample), sample]}


class ParsingTests(unittest.TestCase):
    def test_gpu_units_and_optional_telemetry(self) -> None:
        row = parse_gpu_csv(gpu_csv().replace("150.3", "[N/A]"))[0]
        self.assertEqual(row["memory_free_bytes"], 44 * GIB)
        self.assertEqual(row["index"], 3)
        self.assertIsNone(row["power_draw_w"])
        self.assertEqual(row["utilization_gpu_percent"], 54)

    def test_malformed_unknown_memory_duplicates_rejected(self) -> None:
        for raw in ("", "3,bad", gpu_csv().replace("45056", "[N/A]"), gpu_csv() * 2,
                    gpu_csv().replace("45056", "nan"), gpu_csv().replace("45056", "999999")):
            with self.subTest(raw=raw), self.assertRaises(ResourceError):
                parse_gpu_csv(raw)

    def test_processes_allow_empty_and_record_unknown_memory(self) -> None:
        self.assertEqual(parse_process_csv(""), [])
        result = parse_process_csv(f"{PRIMARY_GPU_UUID}, 433133, /research/build/autoplacer-RL, [N/A]\n")
        self.assertEqual(result[0]["pid"], 433133)
        self.assertIsNone(result[0]["used_gpu_memory_bytes"])
        with self.assertRaises(ResourceError):
            parse_process_csv(f"{PRIMARY_GPU_UUID}, nope, x, 5\n")


class EnvironmentTests(unittest.TestCase):
    def test_only_selected_full_uuid_is_bound(self) -> None:
        self.assertEqual(prepare_cuda_environment(PRIMARY_GPU_UUID, {}),
                         {"CUDA_VISIBLE_DEVICES": PRIMARY_GPU_UUID})
        source = {"CUDA_VISIBLE_DEVICES": PRIMARY_GPU_UUID, "SLURM_JOB_ID": "123"}
        original = dict(source)
        self.assertEqual(prepare_cuda_environment(PRIMARY_GPU_UUID, source)["CUDA_VISIBLE_DEVICES"], PRIMARY_GPU_UUID)
        self.assertEqual(source, original)

    def test_conflicting_scheduler_and_visibility_fail_closed(self) -> None:
        for env in ({"CUDA_VISIBLE_DEVICES": "3"}, {"CUDA_VISIBLE_DEVICES": ""},
                    {"CUDA_VISIBLE_DEVICES": BACKUP_GPU_UUID},
                    {"CUDA_VISIBLE_DEVICES": PRIMARY_GPU_UUID + "," + BACKUP_GPU_UUID},
                    {"SLURM_JOB_ID": "123"}, {"PBS_JOBID": "123"},
                    {"SLURM_JOB_GPUS": "5", "CUDA_VISIBLE_DEVICES": PRIMARY_GPU_UUID},
                    {"NVIDIA_VISIBLE_DEVICES": "none"}, {"CUDA_VISIBLE_DEVICES": "MIG-123"}):
            original = dict(env)
            with self.subTest(env=env), self.assertRaises(ResourceError):
                prepare_cuda_environment(PRIMARY_GPU_UUID, env)
            self.assertEqual(env, original)
        with self.assertRaises(ResourceError):
            prepare_cuda_environment("GPU-unauthorized", {})


class AdmissionTests(unittest.TestCase):
    def test_exact_budget_plus_reserve_boundary_and_explicit_backup(self) -> None:
        result = require_admission(evidence(), env={})
        self.assertEqual(result["budget_bytes"], 32 * GIB)
        self.assertFalse(result["allocator_fraction_is_hard_isolation"])
        self.assertEqual(result["logical_device"], "cuda:0")
        self.assertEqual(require_admission(evidence(), BACKUP_GPU_UUID, env={})["physical_index"], 5)

    def test_transient_pressure_is_not_hidden_by_final_sample(self) -> None:
        report = evidence()
        report["samples"][0]["gpus"][0]["memory_free_bytes"] -= 1
        with self.assertRaisesRegex(ResourceError, "budget plus"):
            require_admission(report, env={})

    def test_zero_or_expanded_budgets_rejected(self) -> None:
        for value in (0, -1, 32.01, float("inf"), float("nan")):
            with self.subTest(value=value), self.assertRaises(ResourceError):
                require_admission(evidence(), budget_gib=value, env={})

    def test_short_stale_incomplete_wrong_host_wrong_index_mig_disk_rejected(self) -> None:
        mutations = (
            lambda r: r.update(sampling_duration_seconds=59.9),
            lambda r: r.update(requested_seconds=0),
            lambda r: r.update(status="interrupted"),
            lambda r: r.update(hostname="another-host"),
            lambda r: r.update(initial_commands=[]),
            lambda r: r["samples"][-1].update(timestamp=(datetime.now(timezone.utc) - timedelta(seconds=31)).isoformat()),
            lambda r: r["samples"][-1]["gpus"][0].update(index=0),
            lambda r: r["samples"][-1]["gpus"][0].update(mig_mode_current="Enabled"),
            lambda r: r["samples"][-1]["host"].update(disk_free_bytes=15 * GIB - 1),
            lambda r: r["samples"][-1].update(errors=["process query failed"]),
        )
        for mutate in mutations:
            report = evidence()
            mutate(report)
            with self.subTest(report=report), self.assertRaises(ResourceError):
                require_admission(report, env={})

    def test_reservation_detection_by_name_pid_and_lifecycle(self) -> None:
        for name in ("gpu_reservation", "/research/build/autoplacer-RL"):
            report = evidence()
            report["samples"][-1]["processes"] = [{"gpu_uuid": PRIMARY_GPU_UUID, "pid": 433133, "process_name": name}]
            with self.assertRaisesRegex(ResourceError, "reservation"):
                require_admission(report, env={})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report["samples"][-1]["processes"][0]["process_name"] = "renamed-helper"
            (root / "gpu3.pid").write_text("433133\n", encoding="utf-8")
            with self.assertRaisesRegex(ResourceError, "reservation"):
                require_admission(report, reservation_dir=root, env={})
            (root / "gpu3.pid").unlink()
            (root / "gpu3.jsonl").write_text(json.dumps({"pid": 433133, "event": "heartbeat"}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ResourceError, "reservation"):
                require_admission(report, reservation_dir=root, env={})

    def test_backup_reservation_does_not_trigger_primary_or_kill_anything(self) -> None:
        report = evidence()
        report["samples"][-1]["processes"] = [{"gpu_uuid": BACKUP_GPU_UUID, "pid": 123, "process_name": "gpu_reservation"},
                                                {"gpu_uuid": PRIMARY_GPU_UUID, "pid": 456, "process_name": "SenseVoice"}]
        with patch("os.kill") as kill:
            require_admission(report, env={})
            kill.assert_not_called()


class AuditTests(unittest.TestCase):
    def test_sampling_duration_spans_observations_and_excludes_initial_query_delay(self) -> None:
        sample = evidence()["samples"][0]
        with tempfile.TemporaryDirectory() as temporary, \
                patch("minicpm_research.resources._command", return_value={"exit_code": 0}), \
                patch("minicpm_research.resources.capture_snapshot", side_effect=lambda _: copy.deepcopy(sample)), \
                patch("minicpm_research.resources.time.monotonic", side_effect=[0, 2, 64]), \
                patch("minicpm_research.resources.time.sleep") as sleep:
            report = audit_resources(temporary, seconds=60)
            self.assertEqual(report["sampling_duration_seconds"], 62)
            self.assertTrue(report["formal_sampling_complete"])
            sleep.assert_called_once_with(5)

    def test_quick_snapshot_persists_raw_commands_without_admission(self) -> None:
        def command(argv):
            if any(argument == f"--query-gpu={GPU_FIELDS}" for argument in argv):
                raw = gpu_csv()
            else:
                raw = "" if any("query-compute-apps" in argument for argument in argv) else "read-only inventory"
            return {"argv": list(argv), "exit_code": 0, "stdout": raw, "stderr": ""}
        with tempfile.TemporaryDirectory() as temporary, patch("minicpm_research.resources._command", side_effect=command):
            report = audit_resources(temporary, seconds=0)
            saved = json.loads((Path(temporary) / "RESOURCE_AUDIT.json").read_text(encoding="utf-8"))
            self.assertFalse(report["formal_sampling_complete"])
            self.assertFalse(saved["gpu_experiment_run"])
            self.assertEqual(len(saved["samples"]), 1)
            self.assertIn(PRIMARY_GPU_UUID, saved["samples"][0]["commands"][0]["stdout"])
            with self.assertRaises(ResourceError):
                require_admission(report, env={})
            with self.assertRaisesRegex(ResourceError, "already exists"):
                audit_resources(temporary, seconds=0)

    @unittest.skipUnless(sys.platform == "linux", "Actual flock requires Linux; tested again on remote CPU")
    def test_global_lock_contender_cannot_truncate_or_steal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "formal.lock"
            with single_worker_lock(path):
                original = path.read_bytes()
                with self.assertRaisesRegex(ResourceError, "Another formal"):
                    with single_worker_lock(path):
                        self.fail("contender acquired lock")
                self.assertEqual(path.read_bytes(), original)
            with single_worker_lock(path) as metadata:
                self.assertEqual(metadata["pid"], os.getpid())
            self.assertTrue(path.exists())

    @unittest.skipIf(sys.platform == "linux", "Non-Linux rejection only")
    def test_non_linux_worker_lock_fails_closed(self) -> None:
        with self.assertRaisesRegex(ResourceError, "Linux flock"):
            with single_worker_lock("unused.lock"):
                self.fail("Windows formal worker should not be admitted")


if __name__ == "__main__":
    unittest.main()
