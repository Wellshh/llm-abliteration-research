# Level-A 盲审派发包 — B9-03 R1/R2（2026-09-21）

**授权**：批准人指令（2026-09-21）："将现有 gold_audit_v2 盲态包交给两位独立人类 R1/R2。他们分别填写并签署 Level A 表格，先记录分歧再裁决；智能体只能备料和核对，不能代签。"
**包状态**：材料已由智能体核验（见 `MATERIAL_VERIFICATION_20260921.md`，18 项哈希全配、8 张表全部空白未签）。**等待两位人工审查者填写并签署。**

## 0. 这个审核能证明什么、不能证明什么（先读）

- **Level A 是数据池的分层抽样审核**（`gold_audit_v2`，B9-03，seed 20260915）：V 72 项、T 48 项、C 24 项 gold + 24 项 C 表面一致性检查；密封钥匙 168 条。
- **C 覆盖是部分的**：40 个 family 中抽到 **12**，20 个 category×rule×gold 格中覆盖 **12**（8 个未覆盖格已在包 manifest 的 `coverage_report` 中逐一列名）。
- 因此签署结论**只能**表述为"数据池抽样质量"，**不得**表述为"全部入轮条目已审核"。全量入轮审核是 **Level B**，在 C 冻结**之后**由 `scripts/make_audit_package_level_b.py` 生成（该入口现已由 RC-C3 验证器把守）。
- 盲态是**诚信约束**：sheets/items 不含 gold、原始 ID、模型输出、condition；但拥有仓库访问权的人技术上可查源数据——这是包 README 已记录的既有限制，签署即确认遵守。

## 1. 材料分发

| 角色 | 得到 | 绝不给 |
|---|---|---|
| R1（人类） | `gold_audit_v2/sheets/sheet_{V,T,C,C_surface}_R1.md` + `gold_audit_v2/packages/items_{V,T,C,C_surface}.json` + 表格模板 `forms/DATA_GOLD_AUDIT_FORM_v1.md` | `SEALED_KEY.json`、`manifest.json`、R2 的表、`artifacts/data/*.jsonl`、`artifacts/runs/` |
| R2（人类） | 同上（`_R2` sheets） | 同上（R1 的表） |
| 协调人 | `SEALED_KEY.json` + `manifest.json`（仅用于双方提交后的比对与分歧登记） | — |

**表头绑定（协调人预填，数值来自 `MATERIAL_VERIFICATION_20260921.md` 的实算）：**
- `package_manifest_sha256`: `dc71425fa8ed1562a1f823085e12e27925c6bdeb6de50f4773d1e244fd78be36`
- `data_sha256`（被审数据）: V/T = `ecbcc6bf91822dd44547289dca429dc4b381f2c5549b452201fc29789e5f2782`（pilot.jsonl）；C = `e66fbd2659ef745a13280decf610f84aa4375630a66981b79c077a643f8cf302`（pilot_c_v2.jsonl）
- `rubric_version_sha256`: `4eb178b0b86e7bbe87f2cb7d710548679372bc1c78cef79d06f35c71ca962a02`（DATA_GOLD_AUDIT_FORM_v1.md）
- 注：表格模板"数据来源声明"一栏提到的 S_DATA_PROTOCOL **v2** 已被 **v3** 取代（errata E-1）；S 部分本来就是**空模板，不得填充**（S blocked），此差异不影响本次 V/T/C 审核。

## 2. 流程（顺序不可变）

1. **独立填写**：R1、R2 各自对每个 item 一行：自己的独立 gold 判断 + 理由（≤3 句）+ prompt 内证据引用 + 存疑标记。**不确定就标 uncertain，勿猜。** 期间互不查看对方表格，不查看数据集 gold / 模型输出 / condition / run 信息。
2. **签署**：各自在表格"签署"栏签名 + 日期，并确认独立性声明。
3. **双方都提交后**，协调人才可比对；**分歧先原样登记**进 `forms/DISAGREEMENT_AND_ADJUDICATION_FORM_v1.md`（登记先于裁决，不得边裁边改记录）。
4. **裁决由人类完成**；智能体只备料、核对哈希与完整性，**不填写、不代签、不裁决**。
5. 签署表 + 分歧登记 + 裁决记录归档后，进入执行包（任务 #19）供批准人批准 C freeze。

## 3. 完成判据（供协调人核对）

- [ ] R1 四张表全部行填写完毕并签署（含日期）
- [ ] R2 四张表全部行填写完毕并签署（含日期）
- [ ] 所有分歧已登记且已裁决，裁决人署名
- [ ] `s_template_EMPTY/` 未被填充（S blocked）
- [ ] 签署后的文件哈希与空白表哈希的差异已记录（证明改动来自人工填写）

**智能体边界重申**：本包由智能体备料与核验；`mode=agent_prepared_materials_only`；`unlocks_runs=false`；`proves_in_round_files_audited=false`。人工签署完成前，C freeze 的前置 §G 视为未满足。
