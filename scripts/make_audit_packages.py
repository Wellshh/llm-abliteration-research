"""B9-03 agent-side audit package builder v2 (materials only; humans sign/adjudicate).

Builds blinded, deterministic, stratified gold-audit packages for the EXISTING
V/T/C pilot data (no model outputs, no conditions, no gold in reviewer-facing
files) plus an EMPTY S template (S blocked). A sealed coordinator-only key maps
audit codes back to example IDs and dataset gold. CPU-only, no GPU, no network.
Refuses to overwrite an existing package directory.

v2 (second-review fixes 3-5):
- sheets carry FULL data/items/forms sha256 bindings and the correct relative
  items path (no placeholders, no truncated hashes);
- manifest binds every artifact: items, sheets, sealed key, generator script;
- two explicit acceptance levels: A = pool spot audit (this package; unlocks no
  run), B = pre-freeze FULL audit of the final in-round files (future package);
- coverage report vs the B7-02 proposed round families and C category x rule x
  gold cells, with uncovered cells enumerated;
- sampling honestly named stratified DETERMINISTIC (lexicographic cell-min /
  stride / round-robin); the seed affects presentation order only.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from minicpm_research.runs import file_hash

SEED = 20260915
V_CELLS_EXPECTED = 24      # 6 label maps x 4 rules
T_FAMILIES = 12
T_STRIDE = 5               # 60 / 12
C_FAMILIES = 12
C_CATEGORIES_SORTED = ("negation_understanding", "stance_neutral_objective",
                       "surface_refusal_words_non_refusal", "user_stance_agree_vs_oppose",
                       "yes_no_questions")
BLINDED_ITEM_KEYS = ("code", "task", "prompt", "answer_space")
FORBIDDEN_IN_ITEMS = ("gold", "family_id", "example_id", "variant", "variant_kind", "rule",
                      "label_map", "condition", "raw_text", "sandbox_state", "baseline", "identity_hook")
B702_PROTOCOL = ROOT / "reports/PREREGISTRATION_PHASE0_REVISION_v2.yaml"
C_MANIFEST = ROOT / "artifacts/data/pilot_c_v2.manifest.json"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def select_v_families(examples: list[dict[str, Any]]) -> list[str]:
    """DETERMINISTIC: one family per (label_map, rule) cell; lexicographically smallest per cell."""
    cells: dict[tuple[str, str], list[str]] = defaultdict(list)
    for e in examples:
        if e["task"] == "V":
            cells[(json.dumps(e["label_map"], sort_keys=True), e["rule"])].append(e["family_id"])
    if len(cells) != V_CELLS_EXPECTED:
        raise ValueError(f"V stratification expects {V_CELLS_EXPECTED} (map, rule) cells, found {len(cells)}")
    return sorted(min(sorted(set(fams))) for fams in cells.values())


def select_t_families(examples: list[dict[str, Any]]) -> list[str]:
    """DETERMINISTIC systematic sampling: every T_STRIDE-th family of the sorted list."""
    fams = sorted({e["family_id"] for e in examples if e["task"] == "T"})
    return fams[::T_STRIDE][:T_FAMILIES]


def select_c_families(examples: list[dict[str, Any]]) -> list[str]:
    """DETERMINISTIC round-robin over sorted categories (3,3,2,2,2), lexicographic within category."""
    by_cat = {c: sorted({e["family_id"] for e in examples if e["category"] == c}) for c in C_CATEGORIES_SORTED}
    picked: list[str] = []
    passes = 0
    while len(picked) < C_FAMILIES:
        added = False
        for cat in C_CATEGORIES_SORTED:
            if passes < len(by_cat[cat]) and len(picked) < C_FAMILIES:
                picked.append(by_cat[cat][passes])
                added = True
        if not added:
            break
        passes += 1
    return picked


def _prompt_text(example: dict[str, Any]) -> str:
    return "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in example["messages"])


def _answer_space(example: dict[str, Any]) -> str:
    if example["task"] == "V":
        return "CONFIRM | REJECT | ABSTAIN | uncertain"
    if example["task"] == "T":
        return "WRITE_AUTHORIZED | REQUEST_CONFIRMATION | READ_TO_RESOLVE | CLARIFY_MISSING_INFORMATION | uncertain"
    return "TRUE | FALSE 或 YES | NO（按题面语义域） | uncertain"


def build_items(examples: list[dict[str, Any]], selected: dict[str, list[str]],
                rng: random.Random) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return (gold_audit_items, surface_check_items, sealed_key). rng affects ORDER only."""
    by_id = {e["example_id"]: e for e in examples}
    gold_items: list[dict[str, Any]] = []
    surface_items: list[dict[str, Any]] = []
    key: dict[str, dict[str, Any]] = {}
    for task in ("V", "T", "C"):
        rows = [by_id[eid] for eid in sorted(
            e["example_id"] for e in examples
            if e["task"] == task and e["family_id"] in set(selected[task])
            and (task != "C" or e["in_round_eligible"]))]
        rng.shuffle(rows)
        for n, e in enumerate(rows):
            code = f"AUD-{task}-{n:04d}"
            gold_items.append({"code": code, "task": task, "prompt": _prompt_text(e), "answer_space": _answer_space(e)})
            if task == "V":
                stratum = [json.dumps(e["label_map"], sort_keys=True), e["rule"]]
            elif task == "T":
                stratum = [e["family_id"]]
            else:
                stratum = [e["category"]]
            key[code] = {"example_id": e["example_id"], "family_id": e["family_id"], "task": task,
                         "dataset_gold": e["gold"], "variant_kind": e.get("variant_kind"),
                         "stratum": stratum}
    c_fams: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in examples:
        if e["task"] == "C" and e["family_id"] in set(selected["C"]):
            c_fams[e["family_id"]].append(e)
    surface_pairs = []
    for fid in sorted(c_fams):
        fam = c_fams[fid]
        base_kind = "stance_agree" if any(x["variant_kind"] == "stance_agree" for x in fam) else "primary_map_1"
        base = next(x for x in fam if x["variant_kind"] == base_kind)
        for var_kind in ("paraphrase_discovery", "translation_zh_discovery"):
            var = next(x for x in fam if x["variant_kind"] == var_kind)
            surface_pairs.append((base, var))
    rng.shuffle(surface_pairs)
    for n, (base, var) in enumerate(surface_pairs):
        code = f"AUD-C-SURF-{n:04d}"
        surface_items.append({"code": code, "task": "C_surface_check",
                              "primary_prompt": _prompt_text(base), "variant_prompt": _prompt_text(var),
                              "instruction": "仅判断两个题面是否表达同一判定任务（语义等同、数字/ID 全保留、立场句一致）；不评 gold。"})
        key[code] = {"example_id": var["example_id"], "family_id": var["family_id"], "task": "C_surface_check",
                     "dataset_gold": var["gold"], "variant_kind": var["variant_kind"],
                     "stratum": [var["category"]], "primary_example_id": base["example_id"]}
    return gold_items, surface_items, key


def _proposed_round_families() -> dict[str, list[str]]:
    """Read the B7-02 proposed round families (V/T) and the C candidate manifest rounds."""
    import yaml
    out: dict[str, list[str]] = {}
    if B702_PROTOCOL.exists():
        doc = yaml.safe_load(B702_PROTOCOL.read_text(encoding="utf-8"))
        fs = doc["family_selection"]
        out["V_round_1"] = list(fs["v_round_1_families"])
        out["V_round_2"] = list(fs["v_round_2_families"])
        out["T_round_1"] = list(fs["t_round_1_families"])
        out["T_round_2"] = list(fs["t_round_2_families"])
    if C_MANIFEST.exists():
        cm = json.loads(C_MANIFEST.read_text(encoding="utf-8"))
        out["C_round_1"] = list(cm["proposed_round_1_families"])
        out["C_round_2"] = list(cm["proposed_round_2_families"])
    return out


def _coverage_report(examples: list[dict[str, Any]], selected: dict[str, list[str]]) -> dict[str, Any]:
    by_id_family: dict[str, dict[str, Any]] = {}
    for e in examples:
        by_id_family.setdefault(e["family_id"], e)
    proposed = _proposed_round_families()
    report: dict[str, Any] = {"proposed_round_overlap": {}}
    for task in ("V", "T", "C"):
        sel = set(selected[task])
        for round_name in (f"{task}_round_1", f"{task}_round_2"):
            prop = proposed.get(round_name)
            if prop is None:
                continue
            report["proposed_round_overlap"][round_name] = {
                "proposed": len(prop),
                "covered_by_this_spot_audit": sorted(sel & set(prop)),
                "not_covered": sorted(set(prop) - sel),
            }
    # V cell coverage
    v_cells = {(json.dumps(e["label_map"], sort_keys=True), e["rule"]) for e in examples if e["task"] == "V"}
    v_sel_cells = {(json.dumps(by_id_family[f]["label_map"], sort_keys=True), by_id_family[f]["rule"]) for f in selected["V"]}
    report["V"] = {"map_rule_cells_covered": f"{len(v_sel_cells)}/{len(v_cells)}",
                   "per_family_gold_coverage": "complete by construction (each V family carries all three golds)",
                   "families_covered": f"{len(selected['V'])}/120"}
    report["T"] = {"families_covered": f"{len(selected['T'])}/60",
                   "per_family_gold_coverage": "complete by construction (each T family carries all four golds)"}
    # C category x rule x gold cells
    c_cells = {(by_id_family[f]["category"], by_id_family[f]["rule"]) for f in
               {e["family_id"] for e in examples if e["task"] == "C"}}
    c_possible = set()
    for e in examples:
        if e["task"] == "C":
            c_possible.add((e["category"], e["rule"], e["gold"]))
    c_sel = {(by_id_family[f]["category"], by_id_family[f]["rule"], by_id_family[f]["gold"]) for f in selected["C"]}
    report["C"] = {"families_covered": f"{len(selected['C'])}/40",
                   "category_rule_gold_cells_covered": f"{len(c_sel)}/{len(c_possible)}",
                   "uncovered_cells": sorted(f"{c}|{r}|{g}" for (c, r, g) in sorted(c_possible - c_sel)),
                   "note": "uncovered cells are expected for a 12-of-40 spot audit; Level B pre-freeze audit covers the actual in-round set in full"}
    return report


def _write(path: Path, text: str) -> None:
    if path.exists():
        raise SystemExit(f"REFUSING overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("x", encoding="utf-8") as h:
        h.write(text)
        h.flush()
        os.fsync(h.fileno())
    os.replace(tmp, path)


def _sheet_md(task: str, codes: list[str], reviewer: str, bind: dict[str, str], items_rel: str) -> str:
    lines = [f"# GOLD AUDIT SHEET — {task} — reviewer {reviewer}",
             "",
             f"- acceptance_level: A_pool_spot_audit（数据池抽检；**不解锁任何运行**；入轮前另有 Level B 全量审核）",
             f"- data_sha256 pilot.jsonl: `{bind['pilot_sha']}`",
             f"- data_sha256 pilot_c_v2.jsonl: `{bind['c_sha']}`",
             f"- items_file: `{items_rel}`  sha256: `{bind['items_sha_' + task]}`",
             f"- forms_sha256: " + "; ".join(f"{name}=`{sha}`" for name, sha in bind["forms"].items()),
             f"- selection: stratified DETERMINISTIC（见 manifest.selection_rules）；seed {bind['seed']} 仅决定呈现顺序与编码",
             f"- reviewer_anonymous_id: {reviewer}",
             "- 题面见上方 items_file 路径（按 code 检索）；禁止查看数据集源文件、运行目录、SEALED_KEY、对方表格",
             "",
             "| item_code | 我的独立 gold（语义） | 理由（≤3 句） | 必需证据引用 | uncertain? | 备注 |",
             "|---|---|---|---|---|---|"]
    lines += [f"| {c} | | | | | |" for c in codes]
    lines += ["", "签署：本人独立完成。签名 ____ 日期 ____"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/audit/gold_audit_v2")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)
    out = args.out
    if out.exists():
        raise SystemExit(f"REFUSING overwrite of existing package dir: {out}")

    pilot_path = ROOT / "artifacts/data/pilot.jsonl"
    c_path = ROOT / "artifacts/data/pilot_c_v2.jsonl"
    pilot = _read_jsonl(pilot_path)
    c_data = _read_jsonl(c_path)
    examples = pilot + c_data
    selected = {"V": select_v_families(pilot), "T": select_t_families(pilot), "C": select_c_families(c_data)}
    rng = random.Random(args.seed)   # presentation order ONLY; selection is lexicographic/systematic/round-robin
    gold_items, surface_items, key = build_items(examples, selected, rng)

    ident_fields = ("example_id", "family_id", "variant_kind", "primary_example_id")
    for item in gold_items + surface_items:
        for forbidden in FORBIDDEN_IN_ITEMS:
            if forbidden in item:
                raise ValueError(f"blinding violation: {forbidden} in item {item.get('code')}")
        blob = json.dumps(item, ensure_ascii=False)
        for field in ident_fields:
            value = key[item["code"]].get(field)
            if isinstance(value, str) and value and value in blob:
                raise ValueError(f"blinding violation: sealed identifier {field} appears in item {item['code']}")

    out.mkdir(parents=True)
    items_files = {"V": out / "packages/items_V.json", "T": out / "packages/items_T.json",
                   "C": out / "packages/items_C.json", "C_surface": out / "packages/items_C_surface.json"}
    _write(items_files["V"], json.dumps([i for i in gold_items if i["task"] == "V"], ensure_ascii=False, indent=1) + "\n")
    _write(items_files["T"], json.dumps([i for i in gold_items if i["task"] == "T"], ensure_ascii=False, indent=1) + "\n")
    _write(items_files["C"], json.dumps([i for i in gold_items if i["task"] == "C"], ensure_ascii=False, indent=1) + "\n")
    _write(items_files["C_surface"], json.dumps(surface_items, ensure_ascii=False, indent=1) + "\n")
    _write(out / "SEALED_KEY.json", json.dumps({"coordinator_only": True,
        "notice": "Maps audit codes to example IDs and dataset gold. NOT for reviewer distribution; blinding is good-faith (repo access could reveal sources - documented limitation).",
        "key": key}, ensure_ascii=False, indent=1) + "\n")

    forms_dir = ROOT / "artifacts/audit/forms"
    forms = {p.name: file_hash(p) for p in sorted(forms_dir.glob("*.md"))}
    bind = {"pilot_sha": file_hash(pilot_path), "c_sha": file_hash(c_path), "forms": forms, "seed": str(args.seed)}
    for task in ("V", "T", "C"):
        bind[f"items_sha_{task}"] = file_hash(items_files[task])
    bind["items_sha_C_surface"] = file_hash(items_files["C_surface"])

    sheets: dict[str, str] = {}
    for reviewer in ("R1", "R2"):
        for task in ("V", "T", "C"):
            codes = [i["code"] for i in gold_items if i["task"] == task]
            rel = f"../packages/items_{task}.json"
            p = out / f"sheets/sheet_{task}_{reviewer}.md"
            _write(p, _sheet_md(task, codes, reviewer, bind, rel))
            sheets[p.name] = file_hash(p)
        codes = [i["code"] for i in surface_items]
        p = out / f"sheets/sheet_C_surface_{reviewer}.md"
        _write(p, _sheet_md("C_surface", codes, reviewer, bind, "../packages/items_C_surface.json")
               .replace("我的独立 gold（语义）", "语义等同 yes/no/unsure").replace("必需证据引用", "数字/ID 保留 + 立场句一致"))
        sheets[p.name] = file_hash(p)

    _write(out / "s_template_EMPTY/README.md",
           "# S 审核包 — 空模板（S BLOCKED）\n\nS_DATA_PROTOCOL_v3 批准且 intake/双审完成前，本目录**不得填充任何条目**。\n"
           "启用时：条目来自 artifacts/data/s/accepted_items/（双人 d4=storable_as_is），审核维度在 DATA_GOLD_AUDIT_FORM_v1 的 S 扩展节。\n当前条目数：0。\n")
    _write(out / "s_template_EMPTY/items_S.json", json.dumps({"blocked": True, "items": []}, indent=1) + "\n")

    _write(out / "README.md",
           "# gold_audit_v2 — 数据池抽检包（Level A）\n\n"
           "- **Level A（本包）**：数据池分层确定性抽检；结论限于「池质量」；**不证明最终入轮文件已审核，不解锁任何运行**。\n"
           "- **Level B（未来包）**：轮数据冻结后，对该轮**全部**入轮 prompt/gold 的全量审核；冻结前必须完成。\n"
           "- 分发：reviewer 得到 sheets/ + packages/；**SEALED_KEY.json 与 manifest.json 仅协调人**。\n"
           "- 盲态为诚信约束：sheets/items 不含 gold/ID/输出/condition；有仓库访问权者技术上可查源数据（已记录为限制）。\n"
           "- S 目录为空模板（blocked）。\n")

    manifest = {
        "schema": "gold_audit_package_manifest_v2",
        "ticket": "B9-03",
        "supersedes_package": {"path": "artifacts/audit/gold_audit_v1", "status": "retained_unmodified",
                                "reason": "second review: full header bindings, script/items/sheets binding, acceptance levels, coverage report, deterministic naming"},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "seed_role": "presentation order (item shuffle + code assignment) ONLY; family selection is lexicographic/systematic/round-robin and seed-independent",
        "mode": "agent_prepared_materials_only; human signing and adjudication are human tasks",
        "inputs": {
            "pilot_jsonl_sha256": bind["pilot_sha"],
            "pilot_c_v2_jsonl_sha256": bind["c_sha"],
            "forms_sha256": forms,
            "form_separation": "data gold audit (DATA_GOLD_AUDIT_FORM_v1) and future model-output scoring (OUTPUT_SCORING_FORM_v2) are DIFFERENT forms and must never be mixed",
        },
        "generator_script": {"path": "scripts/make_audit_packages.py", "sha256": file_hash(Path(__file__).resolve())},
        "items_sha256": {k: file_hash(p) for k, p in items_files.items()},
        "sheets_sha256": sheets,
        "sealed_key_sha256": file_hash(out / "SEALED_KEY.json"),
        "acceptance_levels": {
            "level_A_pool_spot_audit": {"this_package": True, "scope": "data-pool quality on a stratified deterministic sample",
                                          "unlocks_runs": False, "proves_in_round_files_audited": False},
            "level_B_pre_freeze_full_audit": {"this_package": False,
                                                "scope": "100% of the FINAL in-round prompt/gold files after round data freeze (B7-02 v2 + approved revisions)",
                                                "required_before": "any round execution", "status": "future_package"},
        },
        "selection_rules": {
            "method_naming": "stratified DETERMINISTIC sampling (NOT random): lexicographic cell-minimum (V), fixed stride (T), category round-robin (C)",
            "V": f"one family per (label_map, rule) cell ({V_CELLS_EXPECTED} cells, lexicographically smallest per cell) = {len(selected['V'])} families / {sum(1 for i in gold_items if i['task']=='V')} items (20% of V pilot families)",
            "T": f"systematic every {T_STRIDE}th of sorted family IDs = {len(selected['T'])} families / {sum(1 for i in gold_items if i['task']=='T')} items (20%)",
            "C": f"round-robin over sorted categories (3,3,2,2,2) = {len(selected['C'])} families / {sum(1 for i in gold_items if i['task']=='C')} primary items + {len(surface_items)} surface-check items",
            "S": "EMPTY template only - blocked until S_DATA_PROTOCOL_v3 approval + intake",
        },
        "coverage_report": _coverage_report(examples, selected),
        "selected_families": selected,
        "counts": {"gold_items": dict(Counter(i["task"] for i in gold_items)), "surface_items": len(surface_items),
                   "sealed_key_entries": len(key)},
        "blinding": {
            "reviewer_facing_fields": list(BLINDED_ITEM_KEYS) + ["primary_prompt", "variant_prompt", "instruction"],
            "forbidden_fields_verified_absent": list(FORBIDDEN_IN_ITEMS),
            "no_model_outputs_no_conditions": True,
            "good_faith_limitation": "reviewers with repository access could consult source data files; sheets themselves display no gold/output/condition",
        },
        "s_template_item_count": 0,
    }
    _write(out / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"status": "package_built", "out": str(out), "gold_items": len(gold_items),
                      "surface_items": len(surface_items), "sealed_key_entries": len(key),
                      "families": {t: len(f) for t, f in selected.items()}, "s_items": 0,
                      "coverage": manifest["coverage_report"]["C"]["category_rule_gold_cells_covered"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
