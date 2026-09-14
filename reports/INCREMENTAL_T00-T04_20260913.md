# T00-T04 incremental merge evidence (2026-09-13)

Remote host: `sh-aiserver01`; target root: `/home/jybai/research/MiniCPM5_Research_Plan_v1/minicpm5_research_plan`.

The remote tree was not a Git worktree (`git status --short` exit 128), so the pre-merge state was preserved at `artifacts/setup/merge-backups/20260913T143729Z`. Updated files were `src/minicpm_research/resources.py`, `runs.py`, `model.py`, `scripts/check_hooks.py`, and tests `test_resources.py`, `test_runs.py`, `test_model.py`, `test_hooks.py`. Remote T-enabled `scripts/run_pilot.py --task V/T/both`, `tool_parser.py`, and `evaluation.py` were retained.

Key retained gates: `resources.py:56-60, 75-164, 412-474, 477-509` fixed host-local flock, <=30s RuntimeResourceGuard, fresh 60s admission, UUID/index/MIG/free-memory checks, and reservation takeover refusal. `runs.py:65-146` fsyncs durable event rows and recovers checksummed raw results; `runs.py:150-230` persists PhaseBudget and conservatively charges orphaned attempts. `model.py:305-334` preserves pinned revision/hash and mirror provenance checks. `check_hooks.py:108-115,147-159` enforces one visible UUID and explicit dtype/lock constraints.

Validation (remote, no GPU/model inference): `.venv/bin/python -m unittest discover -s tests -q` exit 0, 83 tests, 1 skipped; `scripts/run_pilot.py --dry-run --task both --max-families 1` exit 0, 600 examples validated, 7 selected, V/T each one family, `T_model_evaluation=code_ready_not_run`; `.venv/bin/python -m compileall -q src scripts tests` exit 0. Pytest was unavailable (exit 1, `No module named pytest`).

No GPU, checkpoint loading, test split access, process termination, or production service changes occurred. Full real-checkpoint hook validation remains pending.
