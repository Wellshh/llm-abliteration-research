# B9-01 v1 候选数据评审问题记录（保留件）

**日期**：2026-09-15｜**对象**：`artifacts/data/pilot_c_v1.jsonl`（sha256 见 `pilot_c_v1.manifest.json`）及其冻结草案 `C_DATA_FREEZE_DRAFT_v1.md`。
**处置**：v1 候选与草案**保留未改**作为历史记录；修正后候选为 `pilot_c_v2.jsonl`（见 `C_DATA_FREEZE_DRAFT_v2.md`）。v1 **不得**用于任何轮次或冻结。

## 只读复核发现的四项问题（均已核实并在 v2 修复）
1. **时刻表题缺 deadline**：`c_timetable_strictly_before` 的截止时间只存在于结构化 claim，未渲染进任何表面形式的 prompt（例 `pilot-C-20260915-0009-0`：deadline=24 不可见，模型无法判定）。→ v2 在 en/zh statement 中显式呈现 deadline，并新增「所有判定必需 claim 标量进入实际 prompt」全量测试（含 timetable 回归，32/32 变体）。
2. **整池平衡未落实到每轮**：v1 轮次按字典序轮转选样，Round 1 三个类别全为肯定 gold、两个类别 2:1——恒肯定语义宏平均可达 86.67%、交换一致性 100%，退化答案可过门。→ v2 改为类别内 rule×gold 分层配对队列（stance 类另以 map=idx//4 与 rule/gold 完全正交，消除 gold-map 相关导致的 always-A 100% 配对），每轮每类双侧 gold 平衡；**四个恒定退化策略与 user-follower 在两轮上的解析投影全部 = 0.500**（写入 manifest，非模型运行）。12 family/轮在 5 类下的分配方案（每类 1 对 + 轮转类别 1 对额外）作为**提案**待冻结前审核。
3. **家族 verifier 未强制配对内容一致**：v1 只校验 gold/映射/变体数量，不比较 claim/evidence，也不验证 messages 与结构化字段对应——不同题目同 gold 可通过。→ v2 `_validate_c_family` 强制：全变体 claim+evidence 深度相等；variant_kind↔stance 绑定；discovery 变体 `derived_from_primary` 指向第一 primary；**messages 必须等于结构化字段的确定性重渲染**（惰性导入避免循环依赖）。拒绝测试：改 evidence 保 gold、改 messages 不改字段、交换 stance 标记、discovery 重绑 stance。
4. **stance discovery 变体改变了立场变量**：v1 给 paraphrase/zh 设 stance=None，渲染器落入 oppose 分支——它们同时改变了表面形式与用户立场，不是 stance_agree 的纯改写/翻译。→ v2 discovery 变体显式绑定第一 primary（`derived_from_primary`）并继承其 stance（agree），渲染验证 agree 句在、oppose 句不在。

## 三处记录收紧（v2 文档与 manifest 已落实）
- `stance_neutral_objective` 使用独立随机世界，只能作**非配对参考**（客观判决基线能力），不能隔离「插入 stance 的效应」；配对对照仅存在于 user_stance 家族内部（agree vs oppose）。
- 「user 消息不含 gold 字符串」仅是**直接打印检查**，不构成完整语义无泄漏证明；内容级泄漏审计归 B9-03 人工 gold 审核。
- 计数与文件状态更正：新增 17 项后全套为 **168 项：167 通过、1 skipped**（v1 报告误写「168 通过」；v2 后为 175 项：174 通过、1 skipped，以实际输出为准）；`verifier.py` 是**修改文件**，v1 报告「全部为新增文件」表述有误。
