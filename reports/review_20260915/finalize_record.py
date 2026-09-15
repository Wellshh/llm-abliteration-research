"""Normalize test-count wording and record verification provenance before staging."""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent

for relative in ("PREREGISTRATION.yaml", "reports/ALIGNMENT_T00-T04.md"):
    path = ROOT / relative
    content = path.read_text(encoding="utf-8")
    content = content.replace("151 local tests pass", "151 tests total: 150 passed, 1 skipped")
    content = content.replace("**151 通过**，1 skipped", "**151 项：150 通过、1 skipped**")
    content = content.replace("**151 通过**（+16：13 评审修复测试＋3 审核修复测试），1 skipped", "**151 项：150 通过、1 skipped**（总数以本次unittest实际发现为准；目标修复覆盖见tests/test_review_fixes.py）")
    path.write_text(content, encoding="utf-8")

verification = json.loads((OUT / "verification.json").read_text(encoding="utf-8"))
paths = [".gitignore", "PREREGISTRATION.yaml", "reports/ALIGNMENT_T00-T04.md", "scripts/run_pilot.py", "src/minicpm_research/evaluation.py", "src/minicpm_research/model.py", "src/minicpm_research/runs.py", "src/minicpm_research/tool_parser.py", "tests/test_review_fixes.py"]
manifest = {"type": "batch6_commit_verification_manifest", "base_commit": verification["base_commit"],
    "gpu_execution": "not_run", "test_command": "CUDA_VISIBLE_DEVICES='' PYTHONPATH=src OMP_NUM_THREADS=4 .venv/bin/python -m unittest discover -s tests -q",
    "tests": {"total":151,"passed":150,"skipped":1,"failed":0,"exit_code":0},
    "verification_exit_code":0, "source_sha256":{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
    "evidence_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"},
    "excluded_from_commit":["artifacts/reservation/gpu3_reservation.jsonl","artifacts/reservation/gpu5_reservation.jsonl"]}
(OUT / "manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
check = subprocess.run(["git","-c","core.whitespace=cr-at-eol","diff","--check"],cwd=ROOT)
raise SystemExit(check.returncode)
