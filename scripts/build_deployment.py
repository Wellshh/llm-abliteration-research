"""Create a checked source-only payload for this task's authorized SSH deployment."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", action="store_true")
    args = parser.parse_args()
    files = {}
    for pattern in ("src/minicpm_research/*.py", "scripts/*.py", "scripts/*.sh", "tests/test_*.py", "configs/*.json", "pyproject.toml", "requirements-server.txt", "docs/RUNNING.md"):
        for path in sorted(ROOT.glob(pattern)):
            content = path.read_bytes()
            files[path.relative_to(ROOT).as_posix()] = {"sha256": hashlib.sha256(content).hexdigest(), "content": base64.b64encode(content).decode()}
    payload = {"schema_version": 1, "files": files}
    if args.payload:
        print(base64.b64encode(zlib.compress(json.dumps(payload, sort_keys=True).encode(), 9)).decode())
    else:
        print(json.dumps({"files": {name: value["sha256"] for name, value in files.items()}}, indent=2))


if __name__ == "__main__":
    main()
