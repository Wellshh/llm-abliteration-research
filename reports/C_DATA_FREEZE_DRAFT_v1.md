# C 控制家族数据冻结草案 v1（B9-01 交付）

**日期**：2026-09-15｜**状态**：`candidate_draft_not_frozen` —— 候选数据 + 冻结草案，等待主会话审核；**C 门槛在 `PREREGISTRATION_PHASE0_REVISION_v2` 批准且本数据正式冻结前保持惰性**（依审核指示）。
**模式**：纯 CPU 合成生成 + 独立验证；**未运行任何模型/GPU**；`pilot.jsonl`（历史 600 行，sha `ecbcc6bf…`）**未修改**；formal test 不存在、未生成、保持封存。

## 1. 交付物
| 文件 | 内容 |
|---|---|
| `artifacts/data/pilot_c_v1.jsonl` | 160 行 = 40 family × 4 变体；**data_sha256 `36fe47a87f44363b8c5dc94b2bf7865f4b9f18b1beb341d5b712bb7796f85371`** |
| `artifacts/data/pilot_c_v1.manifest.json` | 计数/平衡/生成器与 verifier 模块 sha/轮次提案/状态字段 |
| `src/minicpm_research/data_c.py` | 生成器（确定性，seed 20260915） |
| `src/minicpm_research/verifier.py`（扩展） | **独立** C 验证：从 (rule, claim, evidence) 用与生成器分离的逻辑重算 gold；二值 `parse_c_verdict`（单标签、不强制、不吸收失败）；家族结构校验；V/T 路径零改动（`reproduce_review.py` exit 0 复核） |
| `scripts/make_c_pilot_data.py` | 构建 + 组合验证 + manifest（原子写、拒绝覆盖） |
| `tests/test_data_c.py` | 17 测试（见 §5） |

## 2. 分类学与结构（钉死于 v2 协议 `c_round_gate.taxonomy_pinning`）
- **5 个独立类别**（宏平均口径），每类 8 family：`negation_understanding`、`yes_no_questions`、`user_stance_agree_vs_oppose`、`stance_neutral_objective`、`surface_refusal_words_non_refusal`。
- **label_swap = 家族内配对变体属性**：4 个 swap 类别的两 primary = 同内容同 gold、字母映射**精确互换**（结构测试强制）；stance 类别的两 primary = 同命题同 gold 同映射、仅用户立场句（赞同/反对）不同——迎合检测走语义正确率（跟随用户在 4T/4F 平衡下只得 50%）。
- **paraphrase/zh-translation = 家族内 discovery 变体**：`in_round_eligible=false`，永不入轮、永不跨 split（同 family/world 绑定由 `validate_dataset` 强制）；数字/ID token 在所有表面形式中保留（测试强制）。
- 每规则×gold 平衡：每类 2 规则 × {gold 正/反} × 2 重复 = 8 family；语义域：yes_no→{YES,NO}，其余→{TRUE,FALSE}；stance 类家族级字母映射 4/4 平衡。
- 内容全部为良性合成记录判定（传感器/箱计数/时刻表/字段值），**无任何安全相关内容**（S 数据仍按 B9-02 blocked）；surface_refusal 类的拒绝词只出现在 metadata 噪声注记中且 verifier 强制其存在、gold 与其无关。
- 迎合不被简化为单一 flattery：stance 类别覆盖多领域字段/时刻表规则、赞同与反对双侧、gold 双侧平衡；另有立场中立的客观判决类别作为 stance 插入效应的对照。

## 3. 轮次提案（B7-02 规则：类别排序轮转、类内字典序；正式冻结在数据冻结时）
- **Round 1（12 family，覆盖全部 5 类）**：`pilot-C-20260915-` **0000, 0008, 0016, 0024, 0032, 0001, 0009, 0017, 0025, 0033, 0002, 0010**（→ 24 个 round-eligible primary 样本）。
- **Round 2（12 family，与 R1 不重叠，覆盖全部 5 类）**：**0018, 0026, 0034, 0003, 0011, 0019, 0027, 0035, 0004, 0012, 0020, 0028**。
- **Reserve（16 family）**：其余，仅作 discovery/补充，不入两轮判定。
- 与历史 pilot（V/T 180 family）命名空间（example/family/world ID）经测试验证**完全不相交**；组合 760 行 `validate_dataset` 通过。

## 4. 冻结程序（批准后才执行）
1. 主会话批准 `PREREGISTRATION_PHASE0_REVISION_v2`（当前 pending）+ 本草案。
2. B9-03 两位独立人工 gold 审核完成并记录（分层抽样、盲态、分歧先记录后裁决）——**人工审核通过是冻结前置**。
3. 冻结时：记录 data_sha256、生成器/verifier 模块 sha、轮次 family 清单入轮 manifest；`status → frozen`；此后任何数据变更须新版本文件，不改写已冻结数据。
4. C 门槛（宏平均语义正确率 ≥0.75、交换一致性 ≥0.85、整数规则 ceil）仅在冻结后对轮次输出生效；在此之前所有 C 门槛为惰性文本。

## 5. 验证（双重确认）
- **生成器↔verifier 双重确认**：`build_c_pilot` 返回前对全部 160 行跑 `validate_dataset`（每行 gold 由独立逻辑重算比对；world/family/split 隔离；swap/stance/discovery 结构规则）。
- **17 项测试**：构建确定性（两次构建逐字节相同）；计数/类别/gold/规则/映射平衡；轮次提案不重叠且覆盖 5 类；swap 精确互换、stance 同映射异立场句；discovery 变体不入轮 + 数字/ID token 保留 + zh 含 CJK；surface_refusal 噪声注记强制；user 消息**无 gold 泄漏**；**腐蚀检验**（每规则改 claim/evidence → 独立重算翻转、validate 拒绝；null 注入拒绝——C 世界全观测）；结构违规拒绝（缺变体/discovery 入轮/家族内 gold 不一致/stance 映射不一致/swap 非精确互换）；`parse_c_verdict` 语义（单标签、字母限定、TRUNCATED/INVALID 不吸收、3 标签/错域拒绝）；命名空间不相交 + 组合验证。
- **兼容性**：全套 **168 通过**（151+17），1 skipped；`reproduce_review.py` exit 0（V/T 历史证据链在扩展后 verifier 下仍可复核）。

## 6. 纪律声明
- 仅 pilot/discovery；formal test 未生成、保持封存；未运行模型/GPU；未选择干预方向；未改任何阈值。
- `pilot.jsonl`、历史 run、评审/勘误产物零修改；本票据全部为新增文件。
- C 数据不含可执行危险细节或安全敏感内容（与 S 严格分离；S 按 B9-02 协议 blocked 直至来源与审计规则获批）。
