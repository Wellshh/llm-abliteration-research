#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p artifacts/setup
if [[ ! -x .venv/bin/python ]]; then
  if command -v uv >/dev/null; then
    uv venv --python 3.12 .venv
  else
    python3.12 -m venv .venv
  fi
fi
if command -v uv >/dev/null; then
  uv pip install --python .venv/bin/python -r requirements-server.txt
  uv pip install --python .venv/bin/python -e .
  uv pip freeze --python .venv/bin/python > artifacts/setup/requirements-resolved.txt
else
  .venv/bin/python -m ensurepip
  .venv/bin/python -m pip install -r requirements-server.txt -e .
  .venv/bin/python -m pip freeze > artifacts/setup/requirements-resolved.txt
fi
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
printf 'Environment ready. No GPU allocation was performed.\n'
