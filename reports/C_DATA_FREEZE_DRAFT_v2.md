# C 控制家族数据冻结草案 v2（B9-01 修正版交付）

**日期**：2026-09-15｜**状态**：`candidate_draft_not_frozen` —— 等待主会话复核；**C 门槛在 `PREREGISTRATION_PHASE0_REVISION_v2` 批准且本数据正式冻结前保持惰性**。
**取代**：v1 候选（`pilot_c_v1.jsonl`，sha `36fe47a8…`）因四项评审问题**不得使用**；v1 文件与本目录 `B9_01_C_DATA_V1_REVIEW_FINDINGS.md` 问题记录**保留未改**。
**模式**：纯 CPU；**未运行任何模型/GPU**；`pilot.jsonl`（历史 600 行，sha `ecbcc6bf…`）未修改；formal test 不存在、保持封存。

## 1. 交付物
| 文件 | 内容 |
|---|---|
| `artifacts/data/pilot_c_v2.jsonl` | 160 行 = 40 family × 4 变体；**data_sha256 `e66fbd2659ef745a13280decf610f84aa4375630a66981b79c077a643f8cf302`** |
| `artifacts/data/pilot_c_v2.manifest.json` | 计数/平衡/**逐轮平衡证明**/**退化得分解析投影**/supersede 记录/限制声明 |
| `src/minicpm_research/data_c.py`（新增，v2 修正） | 生成器：deadline 进 statement；discovery 绑定第一 primary 并继承 stance；stance map=idx//4 使 rule×gold×map 完全正交；分层配对轮次选择；`round_balance_attestation` + `project_degenerate_scores`（解析计算，无模型） |
| `src/minicpm_research/verifier.py`（**修改文件**） | C 独立验证 + v2 强化：变体间 claim/evidence 深度相等、kind↔stance 绑定、`derived_from_primary`、**messages 与结构化字段确定性重渲染逐字相等**；V/T 路径零改动（`reproduce_review.py` exit 0） |
| `scripts/make_c_pilot_data.py` | v2 构建（原子写、拒绝覆盖、supersede 记录） |
| `tests/test_data_c.py` | 24 测试（v1 的 17 + 四项修正的 7 项回归） |
| `reports/B9_01_C_DATA_V1_REVIEW_FINDINGS.md` | v1 问题记录（保留件） |

## 2. 四项评审修正的落实证据
1. **deadline 可见**：en/zh statement 显式含截止时间；全量测试断言**每个判定必需的 claim 标量出现在每种表面形式的实际 prompt 中**（timetable 回归 32/32 变体）。
2. **每轮平衡 + 退化得分显式计算**：类别内 rule×gold 分层配对（stance 类同 map 配对，rule×gold×map 全正交）；每轮每类 family gold 1T+1F（轮转额外类别 2T+2F）、规则混合。**两轮解析投影：always_affirmative / always_negate / always_letter_A / always_letter_B 宏平均全部 = 0.500，user_follower = 0.5（2/4）**——恒定答案在 ≥0.75 门下不可能通过。**12 family 在 5 类的分配方案（每类 1 对 + 轮转类别额外 1 对）为提案，待冻结前审核**（每类等量与双侧平衡在 12/5 下不可兼得，故以「每类双侧平衡 + 额外对轮转」替代等量）。
3. **配对内容一致 + prompt 对应**：verifier 强制全变体 claim/evidence 相同、messages == 结构化字段的确定性重渲染；拒绝测试覆盖「改 evidence 保 gold」「改 messages 不改字段」「交换 stance 标记」「discovery 重绑 stance」。
4. **discovery = 纯表面变体**：`derived_from_primary` 指向第一 primary（stance 家族 = stance_agree）并继承其 stance；渲染断言 agree 句在/oppose 句不在（en+zh）。

## 3. 轮次提案（确定性；正式冻结在批准后）
- **Round 1（12 family）**：`pilot-C-20260915-` **0000, 0003, 0008, 0011, 0016, 0019, 0024, 0027, 0032, 0035, 0001, 0002**（额外对类别：negation_understanding）。
- **Round 2（12 family，不重叠）**：**0004, 0007, 0009, 0010, 0017, 0018, 0025, 0026, 0033, 0034, 0012, 0015**（额外对类别：stance_neutral_objective）。
- **Reserve（16 family）**：其余，仅 discovery/补充。
- 选择规则：每轮从每个类别（排序）取一个分层对（rule 混合、gold 双侧、stance 同 map），再加轮转类别（round index mod 5）的下一对；Round 2 继续消费队列。
- 与历史 pilot 命名空间不相交；组合 760 行 `validate_dataset` 通过。

## 4. 记录限制（收紧后表述）
- **中立类别为非配对参考**：`stance_neutral_objective` 用独立随机世界，只能作客观判决基线参考，**不能隔离「插入 stance 的效应」**；配对 stance 对照仅存在于 user_stance 家族内（agree vs oppose 同命题）。
- **泄漏检查范围**：自动检查仅证明 gold 标签串未直接打印进 user 消息，**非完整语义无泄漏证明**；内容级审计归 B9-03 人工审核。
- **文件状态**：`verifier.py` 为修改文件（V/T 行为不变，历史兼容性由 `reproduce_review.py` exit 0 证明）；其余为本票据新增。
- **测试计数**（以实际输出为准）：全套 **175 项：174 通过、1 skipped**（C 测试 24 项）。

## 5. 冻结程序（不变，批准后执行）
1. 主会话批准 `PREREGISTRATION_PHASE0_REVISION_v2` + 本草案（含 §3 分配方案）。
2. B9-03 两位独立人工 gold 审核完成（盲态、分歧先记录后裁决）。
3. 冻结时记录 data_sha256、生成器/verifier 模块 sha、轮次清单、**退化得分投影**入轮 manifest；`status → frozen`；此后数据变更须新版本文件。
4. C 门槛（宏平均 ≥0.75、交换一致性 ≥0.85、ceil 整数规则）仅在冻结后对轮次输出生效。

## 6. 纪律声明
仅 pilot/discovery；formal test 封存未生成；零模型/GPU 运行；无干预方向选择；无阈值改动；历史产物（含 v1 候选）零修改；S 数据仍按 B9-02 blocked。
