# DOCUMENTATION DRIFT ERRATA — 2026-09-16 session

**Type:** Append-only errata sidecar (GOAL §10/§14). **No original document was modified.** Each entry preserves the original statement, gives the correction with provenance/chronology, and states downstream impact. These are **present-tense documentation drift** corrections, not alterations of historical thresholds, artifacts, failures, or provenance.
**Authority:** `reports/CURRENT_STATE_20260916.{md,json}` is the authoritative present-tense record; these errata annotate the lower-tier point-in-time documents listed in its §0 hierarchy.

---

## E-1 — `reports/ALIGNMENT_T00-T04.md` §6 cites S_DATA_PROTOCOL **v2**; current is **v3** (audit F-ALIGN-06)

- **Original (preserved, line ~156):** "数据准入协议 **v2** 待批：`reports/S_DATA_PROTOCOL_v2.yaml`（+ pending sidecar …）".
- **Correction:** The current S protocol is **`reports/S_DATA_PROTOCOL_v3.yaml`** (sidecar `S_DATA_PROTOCOL_v3_APPROVAL.json`), which **supersedes v2** (`status_at_supersede=proposed_not_approved`, reason: second read-only review two tightenings — nine-step acquisition sequencing + benign-answer scoring decision table). v2 and v1 are preserved unmodified.
- **Provenance/chronology:** ALIGNMENT batch-6 text predates the v3 revision (v3 sidecar issued 2026-09-15T07:43:31Z). The one-line ALIGNMENT change in commit `5e8f769` did not update this reference.
- **Downstream impact:** **No gate impact** — S is `blocked` under v2 and v3 alike (`s_data_status=blocked`, `approved_source_ids=null`, all 9 ledger steps pending). The drift only misdirects on *which* protocol is current and omits v3's two tightenings. Any future S approval must act on **v3**, not v2.

## E-2 — `handoff.md` test count **183/182/1** is stale; verified current count is **187/186/1** (audit F-HANDOFF-05, F-TEST-04, TEST-01)

- **Original (preserved):** "用户提供的最近记录为 183 项总计、182 passed、1 skipped；本轮只读盘点未重跑，不能宣称由本轮复核."
- **Correction:** Re-running the authoritative CPU suite this session — `CUDA_VISIBLE_DEVICES='' PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -q` — yields **187 total / 186 passed / 1 skipped / 0 failed (exit 0)**, stable across `-q` and `-v`. Decomposition: **151** (review_20260915 CLOSEOUT, pre-C) **+ 24** (`tests/test_data_c.py`) **+ 12** (`tests/test_audit_packages.py`) **= 187**.
- **Provenance/chronology:** `handoff.md` is honest that 183 was *user-provided and not re-run*. 183 is **not reachable** from the current tree and was already self-inconsistent within commit `5e8f769` (which shipped both new test files). The 151→175→183 lineage is superseded; **187 is the verified live count.** (Discovery collects 188 IDs; the runner's 187 includes 1 legitimate platform-skip — F-LOADER-12.)
- **Downstream impact:** Adopt **187/186/1** as authoritative; **retire 151/175/183** as historical/superseded. No scientific gate depends on the count; it is a reproducibility hygiene figure.

## E-3 — `handoff.md` git claims are false of the authoritative repo (audit/critic contradiction)

- **Original (preserved):** "本目录没有 `.git`" / "Git：本地无 Git" / "本次未提交、不提交 commit".
- **Correction:** The directory `handoff.md` resides in (`/home/jybai/research/MiniCPM5_Research_Plan_v1/minicpm5_research_plan`) **is** the authoritative Git repo and **has** `.git`. Live git shows commit **`5e8f7698fa55173c27f896857324037e1de06c14`** ("research architecture", author `wells`, **2026-09-16 22:17:32 +0800**) which **postdates `handoff.md`** (mtime 22:14:51) by ~3 minutes and **includes `handoff.md` itself** plus all previously-untracked files (S v1–v3, pilot_c v1/v2, gold_audit v1/v2, prereg revisions, new scripts/tests, `verifier.py` +182 lines, both heartbeat logs).
- **Provenance/chronology:** `handoff.md` was written from the Windows sync-copy perspective (`E:\minicpm`, "本目录没有 .git") yet committed inside the Linux authoritative repo. The commit's **provenance/authorization is unresolved** (created after a handoff that said "no commit").
- **Downstream impact:** A future agent obeying `handoff.md` literally would (a) skip needed git hygiene and (b) wrongly believe nothing is committed. **Do not** repeat "nothing committed / worktree has untracked S/C/prereg files". Equally, **do not** describe `5e8f769` as user-authorized until its provenance is confirmed. See `APPROVAL_PACKETS_20260916.md` §A for the commit-scope decision.

## E-4 — `reports/T03_FP32_CONTROL_PLAN.md` header is internally stale

- **Original (preserved, header):** states the GPU FP32 control run is **NOT APPROVED / NOT EXECUTED**.
- **Correction:** §7/§9 of the same file record the run as **executed** (`status=characterization_completed`, wall≈107s, GPU FP32 A−B `3.72e-5/3.77e-5`, TF32 explicitly off, `role=characterization_not_validation`, `does_not_unlock_t04=true`). The header was not updated after execution.
- **Provenance/chronology:** artifact `artifacts/hooks/KV_FULL_GPU_FP32_CONTROL_20260914.json` (+ `.PROVENANCE.json`) is the executed record.
- **Downstream impact:** The header could mislead a reader into thinking the characterization is still pending. The executed characterization **does not** re-judge T03, relax any threshold, or unlock T04. Per skeptic F-01/F-02, its supported claim is only "consistent with a precision-sensitive GPU computation effect within tested shapes; mechanism unresolved" — **not** "precision-dominant proven".

## E-5 — `README.md` is a convenience summary, known stale (source-of-truth tier 6)

- **Note (no specific line correction):** `README.md` is tier-6 in the §0 hierarchy. Its "最小 CUDA smoke test" wording was already corrected in ALIGNMENT batch-1 to "CPU hook 验证 + 只读 GPU 审计，无 CUDA/模型 smoke run". Future agents must **not** mistake README statements for current empirical status; read `CURRENT_STATE_20260916.md` instead.

## E-6 — 2026-09-17 addendum: this errata's own **187** figure is superseded (**241**), and `README.md` now carries a pointer banner

- **Original (preserved, E-2):** "Adopt **187/186/1** as authoritative". **Original (preserved, E-5):** "The originals (`ALIGNMENT_T00-T04.md`, `handoff.md`, `T03_FP32_CONTROL_PLAN.md`, `README.md`) remain byte-for-byte unchanged."
- **Correction:** The authoritative CPU suite is now **241 tests / OK / skipped=1 / 0 failed** (verified by re-run on 2026-09-17): 187 + 21 (B8-02 `test_resource_profile`) + 10 (`test_audit_package_level_b`) + 5 (D1/D3 hardening at `fbb363c`) + 18 (`test_phase0_anchors`, §12 D5 consumer gate). **187/186/1 is historical as of `fbb363c`.** Separately, per GOAL §14 ("ensure future agents cannot mistake stale README statements for current empirical status"), a **pointer banner was prepended to `README.md`** directing readers to `CURRENT_STATE_20260916.md §12`; the README body text itself is unchanged, so E-5's "byte-for-byte unchanged" statement is true of the 2026-09-16 session but no longer of the file on disk.
- **Provenance/chronology:** commits `bcfd237` → `8ac8c61` → `84f1952` → `fbb363c` postdate this errata (2026-09-16); the test-count growth is theirs, and the D5 consumer accessor plus its tests are this session's. No gate, threshold, failure record or artifact hash changed; `TOKEN_ANCHORS.json`/`ENVIRONMENT.json` remain `ecdac639…`/`5b8b5bf6…`.
- **Downstream impact:** present-tense figures come from `CURRENT_STATE_20260916.md §12` / `addendum_20260917`. `handoff.md`, `ALIGNMENT_T00-T04.md`, this errata's E-2/E-5 and the README body remain preserved historical text; the README banner is navigation, not a finding.

---

**Discipline statement:** These errata annotate; they do not overwrite. The originals (`ALIGNMENT_T00-T04.md`, `handoff.md`, `T03_FP32_CONTROL_PLAN.md`, `README.md`) remain byte-for-byte unchanged. No historical threshold, gate, failure record, artifact, or provenance was altered. Where a present-tense claim is corrected, the authoritative replacement lives in `CURRENT_STATE_20260916.{md,json}`.
