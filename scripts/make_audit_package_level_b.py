"""B9-03 Level-B pre-freeze FULL in-round gold-audit package builder.

Level B = 100% audit of the FINAL in-round prompt/gold files AFTER a round data
freeze — versus Level A's stratified pool spot sample (scripts/make_audit_packages.py,
which is left UNCHANGED so the committed gold_audit_v2 manifest's generator-script
hash stays valid).

This is TOOLING-PREP (audit AUD-03). It is fail-closed: it REFUSES to build unless
given an in-round manifest with freeze_status=="frozen" + a complete freeze_record,
so it CANNOT emit Level-B content before the C freeze + round-allocation +
the effective approved PREREG v2.1 protocol and sidecar land.
It reuses the EXACT blinding contract from the Level-A
builder (FORBIDDEN_IN_ITEMS / BLINDED_ITEM_KEYS / ident-leak check) so Level B
blinds identically. Human signing and adjudication remain human tasks
(mode=agent_prepared_materials_only); this prepares materials and proves 100%
structural coverage only — it never marks human sign-off complete and never
unlocks a run.

CPU-only, no GPU, no network, no model outputs, no S content (S blocked).
Refuses to overwrite an existing package directory.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))            # to import the Level-A builder as a module
sys.path.insert(0, str(ROOT / "src"))

# Single-source the blinding contract from Level A so Level B blinds IDENTICALLY.
import make_audit_packages as levelA  # noqa: E402
from minicpm_research.runs import file_hash  # noqa: E402
from validate_prereg_approval import validate_prereg_approval  # noqa: E402

_write = levelA._write
_read_jsonl = levelA._read_jsonl
_prompt_text = levelA._prompt_text
_answer_space = levelA._answer_space
FORBIDDEN_IN_ITEMS = levelA.FORBIDDEN_IN_ITEMS
BLINDED_ITEM_KEYS = levelA.BLINDED_ITEM_KEYS

SEED = 20260917
_REQUIRED_EXAMPLE_FIELDS = ("example_id", "family_id", "task", "messages", "gold")


def validate_frozen_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed gate: Level B may only be built from a FROZEN in-round manifest."""
    if not isinstance(manifest, dict):
        raise SystemExit("in-round manifest must be a JSON object")
    if manifest.get("schema") != "round_in_manifest_frozen_v1":
        raise SystemExit(f"unexpected in-round manifest schema {manifest.get('schema')!r}; expected round_in_manifest_frozen_v1")
    if manifest.get("prereg_revision") != "PREREGISTRATION_PHASE0_REVISION_v2_1":
        raise SystemExit("REFUSING to build Level B: prereg_revision must be the approved PREREGISTRATION_PHASE0_REVISION_v2_1")
    if manifest.get("freeze_status") != "frozen":
        raise SystemExit(
            f"REFUSING to build Level B: freeze_status={manifest.get('freeze_status')!r} != 'frozen'. "
            "Level B is a PRE-FREEZE FULL audit of FINAL in-round files; it cannot be built from "
            "candidate/unfrozen data; C freeze, round allocation, and the effective approved PREREG v2.1 protocol and sidecar are required.")
    fr = manifest.get("freeze_record")
    if not isinstance(fr, dict) or not fr.get("frozen_at") or not fr.get("data_sha256"):
        raise SystemExit("REFUSING to build Level B: freeze_record must carry frozen_at + data_sha256 bindings")
    # Audit D3: truth-based, not presence-based. A self-declared 'frozen' manifest with
    # fabricated hashes or an unapproved prereg revision must NOT pass.
    # RC-C3: the consumer reads and validates the approved v2.1 sidecar directly;
    # the manifest boolean below is retained only as a second, explicit declaration.
    prereg_approval_verified = validate_prereg_approval(ROOT)
    if manifest.get("prereg_revision_approval_effective") is not True:
        raise SystemExit("REFUSING to build Level B: prereg_revision_approval_effective must be true (the effective approved PREREG v2.1 protocol and sidecar are freeze prerequisites)")
    data_sha = fr.get("data_sha256")
    if not isinstance(data_sha, dict) or not data_sha:
        raise SystemExit("REFUSING to build Level B: freeze_record.data_sha256 must be a non-empty mapping of repo-relative path -> sha256")
    # §12 round-2 audit (2026-09-17): truth-of-listed-paths is not enough. Bound paths must stay
    # INSIDE the repo (no absolute or '..' entries, which pathlib happily resolves elsewhere), and
    # the binding must actually cover dataset files — a manifest that hash-verifies only unrelated
    # files (e.g. GOAL.md) used to pass while binding zero data.
    bounded = 0
    for rel, expected in data_sha.items():
        if not isinstance(rel, str) or not rel or PurePath(rel).is_absolute() or ".." in PurePath(rel).parts:
            raise SystemExit(f"REFUSING to build Level B: freeze_record.data_sha256 key {rel!r} must be a repo-relative path with no '..' segments")
        path = ROOT / rel
        try:
            path.resolve().relative_to(ROOT.resolve())
        except ValueError:
            raise SystemExit(f"REFUSING to build Level B: freeze_record path {rel!r} resolves outside the repository root")
        if not path.exists():
            raise SystemExit(f"REFUSING to build Level B: freeze_record references missing in-repo file {rel}")
        actual = file_hash(path)
        if actual != expected:
            raise SystemExit(f"REFUSING to build Level B: data_sha256 mismatch for {rel} (manifest {str(expected)[:16]}… != on-disk {actual[:16]}…)")
        if PurePath(rel).as_posix().startswith("artifacts/data/"):
            bounded += 1
    if bounded == 0:
        raise SystemExit("REFUSING to build Level B: freeze_record.data_sha256 binds no file under artifacts/data/; "
                         "a freeze record must bind the in-round DATA, not arbitrary repo files")
    examples = manifest.get("in_round_examples")
    if not isinstance(examples, list) or not examples:
        raise SystemExit("REFUSING to build Level B: in_round_examples must be a non-empty list")
    for e in examples:
        missing = [f for f in _REQUIRED_EXAMPLE_FIELDS if f not in e]
        if missing:
            raise SystemExit(f"in-round example missing required fields {missing}: {e.get('example_id', '<no id>')}")
        if e.get("in_round_eligible") is False:
            raise SystemExit(f"in-round example {e['example_id']} is marked in_round_eligible=false; cannot be in a frozen in-round set")
    return prereg_approval_verified


def build_items_full(examples: list[dict[str, Any]], rng: random.Random) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Blinded items for 100% of in-round examples (NO sampling). rng affects ORDER only."""
    items: list[dict[str, Any]] = []
    key: dict[str, dict[str, Any]] = {}
    # group by task, sort by example_id for determinism, then shuffle presentation order
    by_task: dict[str, list[dict[str, Any]]] = {}
    for e in examples:
        by_task.setdefault(e["task"], []).append(e)
    for task in sorted(by_task):
        rows = sorted(by_task[task], key=lambda e: e["example_id"])
        rng.shuffle(rows)
        for n, e in enumerate(rows):
            code = f"LB-{task}-{n:05d}"
            items.append({"code": code, "task": task, "prompt": _prompt_text(e), "answer_space": _answer_space(e)})
            if task == "V":
                stratum = [json.dumps(e.get("label_map"), sort_keys=True), e.get("rule")]
            elif task == "T":
                stratum = [e["family_id"]]
            else:
                stratum = [e.get("category")]
            key[code] = {"example_id": e["example_id"], "family_id": e["family_id"], "task": task,
                         "dataset_gold": e["gold"], "variant_kind": e.get("variant_kind"), "stratum": stratum}
    return items, key


def verify_blinding(items: list[dict[str, Any]], key: dict[str, dict[str, Any]]) -> None:
    """Identical blinding contract to Level A: no forbidden field, no sealed-identifier leak."""
    ident_fields = ("example_id", "family_id", "variant_kind", "primary_example_id")
    for item in items:
        for forbidden in FORBIDDEN_IN_ITEMS:
            if forbidden in item:
                raise ValueError(f"blinding violation: {forbidden} in item {item.get('code')}")
        blob = json.dumps(item, ensure_ascii=False)
        for field in ident_fields:
            value = key[item["code"]].get(field)
            if isinstance(value, str) and value and value in blob:
                raise ValueError(f"blinding violation: sealed identifier {field} appears in item {item['code']}")


def _sheet_md_b(task: str, codes: list[str], reviewer: str, bind: dict[str, str], items_rel: str) -> str:
    lines = [f"# GOLD AUDIT SHEET (LEVEL B) — {task} — reviewer {reviewer}",
             "",
             "- acceptance_level: **B_pre_freeze_full_audit**（入轮文件 100% 全量审核；冻结前必须完成；人工签署后方可解锁该轮运行）",
             f"- round_id: `{bind['round_id']}`  frozen_at: `{bind['frozen_at']}`",
             f"- in-round manifest sha256: `{bind['manifest_sha']}`",
             "- data bindings: " + "; ".join(f"{k}=`{v}`" for k, v in bind["data_sha256"].items()),
             f"- items_file: `{items_rel}`  sha256: `{bind['items_sha_' + task]}`",
             f"- forms_sha256: " + "; ".join(f"{name}=`{sha}`" for name, sha in bind["forms"].items()),
             "- coverage: **100% of in-round examples** (no sampling; selection_rule=full_in_round)",
             f"- reviewer_anonymous_id: {reviewer}",
             "- 题面见上方 items_file 路径（按 code 检索）；禁止查看数据集源文件、运行目录、SEALED_KEY、对方表格",
             "",
             "| item_code | 我的独立 gold（语义） | 理由（≤3 句） | 必需证据引用 | uncertain? | 备注 |",
             "|---|---|---|---|---|---|"]
    lines += [f"| {c} | | | | | |" for c in codes]
    lines += ["", "签署：本人独立完成。签名 ____ 日期 ____"]
    return "\n".join(lines) + "\n"


def build_level_b(manifest: dict[str, Any], out: Path, seed: int = SEED) -> dict[str, Any]:
    """Build the Level-B package from a FROZEN in-round manifest. Returns the manifest dict."""
    prereg_approval_verified = validate_frozen_manifest(manifest)
    if out.exists():
        raise SystemExit(f"REFUSING overwrite of existing package dir: {out}")
    examples = manifest["in_round_examples"]
    rng = random.Random(seed)  # presentation order ONLY; coverage is 100%, selection is full
    items, key = build_items_full(examples, rng)
    verify_blinding(items, key)

    out.mkdir(parents=True)
    tasks_present = sorted({i["task"] for i in items})
    items_files = {t: out / f"packages/items_{t}.json" for t in tasks_present}
    for t in tasks_present:
        _write(items_files[t], json.dumps([i for i in items if i["task"] == t], ensure_ascii=False, indent=1) + "\n")
    _write(out / "SEALED_KEY.json", json.dumps({"coordinator_only": True,
        "notice": "Maps Level-B audit codes to in-round example IDs and dataset gold. NOT for reviewer distribution; blinding is good-faith (repo access could reveal sources - documented limitation).",
        "key": key}, ensure_ascii=False, indent=1) + "\n")

    forms_dir = ROOT / "artifacts/audit/forms"
    forms = {p.name: file_hash(p) for p in sorted(forms_dir.glob("*.md"))}
    fr = manifest["freeze_record"]
    bind = {"round_id": str(manifest.get("round_id")), "frozen_at": str(fr.get("frozen_at")),
            "manifest_sha": file_hash_from_obj(manifest), "data_sha256": fr.get("data_sha256", {}),
            "forms": forms, "seed": str(seed)}
    for t in tasks_present:
        bind[f"items_sha_{t}"] = file_hash(items_files[t])

    sheets: dict[str, str] = {}
    for reviewer in ("R1", "R2"):
        for t in tasks_present:
            codes = [i["code"] for i in items if i["task"] == t]
            p = out / f"sheets/sheet_{t}_{reviewer}.md"
            _write(p, _sheet_md_b(t, codes, reviewer, bind, f"../packages/items_{t}.json"))
            sheets[p.name] = file_hash(p)

    in_round_total = len(examples)
    pkg_manifest = {
        "schema": "gold_audit_package_manifest_levelB_v1",
        "ticket": "B9-03",
        "acceptance_level": "B_pre_freeze_full_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "seed_role": "presentation order (item shuffle + code assignment) ONLY; coverage is 100% full in-round, seed-independent",
        "mode": "agent_prepared_materials_only; human signing and adjudication are human tasks",
        "round_id": manifest.get("round_id"),
        "prereg_approval_verified": prereg_approval_verified,
        "built_from_frozen_manifest": {"freeze_status": manifest["freeze_status"], "frozen_at": fr.get("frozen_at"),
                                       "data_sha256": fr.get("data_sha256"), "prereg_revision": manifest.get("prereg_revision"),
                                       "prereg_revision_approval_effective": manifest.get("prereg_revision_approval_effective")},
        "generator_script": {"path": "scripts/make_audit_package_level_b.py", "sha256": file_hash(Path(__file__).resolve())},
        "items_sha256": {t: file_hash(p) for t, p in items_files.items()},
        "sheets_sha256": sheets,
        "sealed_key_sha256": file_hash(out / "SEALED_KEY.json"),
        "selection_rule": "full_in_round_no_sampling (100% of frozen in-round examples)",
        "coverage": {"in_round_total": in_round_total, "in_round_audited": len(items),
                     "coverage_fraction": (len(items) / in_round_total) if in_round_total else None,
                     "per_task": dict(Counter(i["task"] for i in items))},
        "acceptance": {
            "level_B_structural_coverage_complete": len(items) == in_round_total,
            "human_signoff_complete": False,
            "unlocks_runs": False,
            "note": "100% structural coverage of the frozen in-round set is prepared, but runs are NOT unlocked until BOTH human reviewers sign and disagreements are adjudicated (human tasks).",
        },
        "blinding": {
            "reviewer_facing_fields": list(BLINDED_ITEM_KEYS),
            "forbidden_fields_verified_absent": list(FORBIDDEN_IN_ITEMS),
            "no_model_outputs_no_conditions": True,
            "good_faith_limitation": "reviewers with repository access could consult source data files; sheets themselves display no gold/output/condition",
        },
        "counts": {"gold_items": dict(Counter(i["task"] for i in items)), "sealed_key_entries": len(key)},
    }
    _write(out / "manifest.json", json.dumps(pkg_manifest, ensure_ascii=False, indent=1) + "\n")
    _write(out / "README.md",
           "# gold_audit Level B — 入轮前全量审核包\n\n"
           "- **Level B（本包）**：轮数据冻结后，对该轮**全部**入轮 prompt/gold 的 100% 全量审核。\n"
           "- 结构覆盖 100% 已由本工具保证；**运行解锁仍需两名独立人工审核员签署 + 分歧裁决**（人工任务）。\n"
           "- 分发：reviewer 得到 sheets/ + packages/；**SEALED_KEY.json 与 manifest.json 仅协调人**。\n"
           "- 盲态为诚信约束：sheets/items 不含 gold/ID/输出/condition；有仓库访问权者技术上可查源数据（已记录为限制）。\n")
    return pkg_manifest


def file_hash_from_obj(obj: Any) -> str:
    """Stable sha256 of a JSON object (canonical encoding) for manifest binding."""
    import hashlib
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--in-round-manifest", type=Path, required=True,
                   help="FROZEN in-round manifest (schema round_in_manifest_frozen_v1, freeze_status=frozen)")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--seed", type=int, default=SEED)
    args = p.parse_args(argv)
    manifest = json.loads(args.in_round_manifest.read_text(encoding="utf-8"))
    pkg = build_level_b(manifest, args.out, seed=args.seed)
    print(json.dumps({"status": "level_b_package_built", "out": str(args.out),
                      "acceptance_level": pkg["acceptance_level"],
                      "coverage": pkg["coverage"]["coverage_fraction"],
                      "in_round_audited": pkg["coverage"]["in_round_audited"],
                      "unlocks_runs": pkg["acceptance"]["unlocks_runs"],
                      "human_signoff_complete": pkg["acceptance"]["human_signoff_complete"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
