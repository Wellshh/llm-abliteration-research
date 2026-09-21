# MATERIAL_VERIFICATION — Level-A 盲审材料核验（智能体备料，2026-09-21）

**性质**：这是智能体对 `artifacts/audit/gold_audit_v2/`（B9-03 Level-A 抽检包，generated 2026-09-15）的**材料完整性核验记录**，不是人工验收，不解锁任何运行。方法：对每个文件重算 sha256 并与包 manifest（`gold_audit_v2/manifest.json`）内嵌绑定逐项比对；对 sheets 做空白/未签/无 gold 字样检查；`SEALED_KEY.json` **只取哈希与大小，内容未读**。

## 1. 哈希绑定核验（18/18 全配）

| 绑定项 | manifest 期望 | 实算 | 结果 |
|---|---|---|---|
| packages/items_V.json | `1e5298d94ff7b50e…` | 同 | ✅ |
| packages/items_T.json | `bf5f8570d16a0bca…` | 同 | ✅ |
| packages/items_C.json | `1c0f64f258cd871c…` | 同 | ✅ |
| packages/items_C_surface.json | `da691db552ca6239…` | 同 | ✅ |
| sheets/sheet_{V,T,C,C_surface}_R1.md（4 张） | manifest `sheets_sha256` 各值 | 同 | ✅×4 |
| sheets/sheet_{V,T,C,C_surface}_R2.md（4 张） | manifest `sheets_sha256` 各值 | 同 | ✅×4 |
| SEALED_KEY.json | `4981fc92ea8e2c9d…` | 同（内容未读，size 46217B） | ✅ |
| artifacts/data/pilot.jsonl | `ecbcc6bf91822dd4…` | 同 | ✅ |
| artifacts/data/pilot_c_v2.jsonl | `e66fbd2659ef745a…` | 同 | ✅ |
| forms/DATA_GOLD_AUDIT_FORM_v1.md | `4eb178b0b86e7bbe…` | 同 | ✅ |
| forms/DISAGREEMENT_AND_ADJUDICATION_FORM_v1.md | `e04c131da9e35435…` | 同 | ✅ |
| forms/OUTPUT_SCORING_FORM_v1.md + v2.md | manifest `forms_sha256` 各值 | 同 | ✅×2 |

包 manifest 自身的 sha256（供表头绑定引用）：`dc71425fa8ed1562a1f823085e12e27925c6bdeb6de50f4773d1e244fd78be36`。

## 2. 空白/盲态检查

- 8 张 sheets（R1×4 + R2×4）：**全部未签**（签署栏为空）、正文无 `"gold"`/`gold:`/`正确答案` 字样。
- counts 与 §G 记录一致：gold_items V=72 / T=48 / C=24，surface_items=24，sealed_key_entries=168，`s_template_item_count=0`。
- `s_template_EMPTY/` 保持空模板（S blocked，批准 + intake 前不得填充）。

## 3. 覆盖限制（原样转述包 manifest / §G，不得放宽）

- C：families **12/40**，category_rule_gold cells **12/20**（8 个未覆盖格在 `coverage_report` 列名）；V/T 的抽检与拟议入轮 family 的重叠见 `coverage_report.proposed_round_overlap`。
- **Level A 结论只限"池质量"；不证明最终入轮文件已审核，不解锁任何运行**（包 README 原文）。全量入轮审核 = Level B，冻结后生成。

## 4. 结论

材料完整、绑定闭合、盲态未破、可以派发 R1/R2。人工签署与裁决**未开始**；本核验不构成 §G 满足。

*核验者：lead agent（备料角色）。方法可复现：对每个文件 `sha256sum` 并与 manifest 对应字段比对。*
