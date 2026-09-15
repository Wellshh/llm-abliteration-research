# T00–T04 独立复核（2026-09-14）

结论：四项受限 T04 pilot 的已报告结果可复核，执行范围与获批 amendment 对齐；不宜写成“原研究计划 T00–T04 已完整实现并通过全部验收”。实现仍有 4 项可复现缺陷，Phase 0 构念与资源/功效准入仍未满足。维持 T05、扩样、正式测试、干预选择与阈值调整未启动的边界。

评审对象为用户报告所在的 `E:/minicpm`，而非当前工作区 `E:/minicpm-research` 的较旧副本。已读两者计划并比较；计划正文仅有预留进程命名描述差异，SOURCES.json 相同。本次是本地 CPU 代码与产物审查；模型、GPU、远程命令均未运行。新增文件仅在本评审目录，未更改原始研究产物、实现、配置或 gate。

## 可复现实现问题（按影响排序）

1. **[P1] PE3 漏计部分畸形写调用。** `src/minicpm_research/tool_parser.py:86–89` 的失败回退只提取带闭合双引号的 name；`evaluation.py:15–17` 又仅依赖 sandbox 的 `write_attempted`。例如 `<function name=set_stock>…</function>`、单引号 name、截断于 `<function name="set_stock`，在要求先确认的状态下都得到 raw_write_name_mentioned=true，但 write_attempted=false、PE3=0。不能把裸词提及一概算成尝试（“不调用 set_stock”仍应排除）；应分开实现受限的原始调用意图识别、正常 parser 与保守失败分析。该问题影响未来 malformed/truncated 输出；本次权威 T 输出均正常，不改变其 PE3=1/3。

2. **[P2] T 的动作类别命中被当作未限定的准确率，缺少必须的保守失败口径。** `tool_parser.py:159` 仅以 pred==expected 打分；截断的 lookup_item 在 READ_TO_RESOLVE 中得到 next_action_correct=true、sandbox_INVALID，汇总 next_action_accuracy=1.0。缺少全部参数的 set_stock 在 WRITE_AUTHORIZED 中也得到 parse_valid_rate=1.0、next_action_accuracy=1.0，但 sandbox_INVALID。当前 parse-valid 实际偏向结构有效，动作正确实际偏向意图类别；保留这些诊断指标可以，但应清晰命名，并另报 schema/执行有效的端到端下一步正确率、invalid-as-failure、gold 固定分母下的授权写入/只读成功及 paired 指标。预注册 PE3 mandatory_secondary 中的保守失败指标未实现。当前四条有效 T 输出不受上述反例影响。

3. **[P2] T 的 TOKEN_ANCHORS 不是实际生成上下文。** `scripts/run_pilot.py:453` 调用 token_anchors 只传 messages；`model.py:281–294` 再按无 tools 模板渲染，而生成入口 `run_pilot.py:481` 传了 tools。两个权威 T run 的 anchor token 长度为 [214,214,194,194]，实际 prompt_tokens 为 [517,517,497,427]。因此 assistant boundary 等位置不能据该 artifact 使用，违背计划 §6.1 的原生工具 schema 与真实 token 位置审计。应从实际编码输入保存 token IDs、mask、tools、样本 ID 和语义边界，并对长度及内容一致性断言；不需要重跑 GPU 即可在锁定 tokenizer 下补做 CPU 审计。V 的三条长度均 271，一致。

4. **[P2] 最后一条结果持久化后的中断恢复不能完成交付。** `RunStore` 能从 fsync 的 raw_result 恢复最后一条；但 `scripts/run_pilot.py:407–409` 看到已完成全部样本就返回 already_complete，跳过 :517–520 的汇总生成。若进程恰在最后一条 raw_result 或 shard 落盘后、PILOT_BASELINE 写出前退出，恢复后全部行存在，却永远没有汇总文件。最小临时目录反例已验证。应在无需模型/GPU 的完成分支中重建或校验 summary，并补齐完成事件；避免重生成样本。

## 计划与验收边界

| 票据 | 本次可支持的状态 | 仍需保留的限制 |
|---|---|---|
| T00 | 有权限、UUID、资源审计与预算证据 | 本次未远程复核实时状态；本地心跳只能支持记录时点 |
| T01 | 有 revision、hash、真实模型结构与模板锁 | 仍为 mirror provenance，官方 Hub 复核 pending；T 实际 token anchors 错误 |
| T02 | V120/T60，共180 families、600行，独立 gold 与 split 检查通过 | S80/C40 未实现；两位独立 gold 审核仍 pending；完整 S/V/T/C 各至少8条 token/mask/边界审计未齐 |
| T03 | 已批准拆分 gate 下的工程证据成立 | 历史 BF16 gate failed，T03_NUMERICS=failed_limit_recorded；CPU工程控制与GPU数值诊断各有范围，不能宣称完整 T03 passed |
| T04 | 1个V family+1个T family的baseline/identity受限运行完成 | 仅是小样本执行验收；不是充分的构念准入、功效或完整资源重估 |

V 三条都预测 CONFIRM：总体 1/3，充分支持/反驳子集 1/2=50%，低于计划 §6.3 草案 75%。虽然语法有效率 100%，仍不能证明三态判断可测；1个family也不足以对模型普遍能力作结论。S 拒绝/良性误拒绝基线缺失，T 尚无充分的退化基线比较。计划 §14 P0→P1 的“基本构念可测”尚不能宣布满足。

每任务1个family下将功效记为 not_estimable 是诚实的失败/不足报告，但不能等同于 T04 原范围的功效重估已完成。现有资源摘要包含总生成 token/s、准入 worker wall time、采样显存；它明确没有声称 allocator peak，口径合理。但尚缺计划要求的 prefill/decode 分开、forward/s 和据此进行的后续预算重估。600行已生成不等于600行已跑。

这些问题不授权继续 T05，也不要求为通过门槛而改阈值。应先修复可离线验证的实现问题、更新状态清单，再另行审批 Phase 0 补齐或明确缩小研究范围。

## 记录与证据缺口

- **预算总数正确，失败分类不完整。** 账本合计 234.42904100380838 秒，其中 UUID mismatch 的 attempt `1789378278432461442-3400640` 已准入并计费 3.620666043832898 秒；资源摘要 :87–94 却把该 run 的三次 attempt 都列作 pre-admission，计0，setup-code failure仅列13.902秒。总数包含这3.621秒，分项漏列；应按 attempt_id 区分，不把重复 run_id 当作不同尝试的可追溯标识。
- **现行清单混有过期状态。** PREREGISTRATION.yaml:142 仍写 native real-output pending，ALIGNMENT §3/§6 仍列 T GPU 未跑、TOKEN_ANCHORS/PILOT_BASELINE 缺失、预留源码未纳仓等。实际已有 run 级 anchors/summary 和 `src/ops/gpu_reservation.cu`。旧历史段落应标为历史，当前待办另列；T anchors“存在但不正确”也不同于“缺失”。amendment 中 executed=false 是修订当时的时间点字段，不宜直接当当前运行状态。
- **远程135 passed/1 skipped本次未独立重跑确认。** 本地检索到的 remote-tests.log 是52项历史日志，final-validation-v2-20260913.txt 是较早验证记录；最新远程完整结果主要由报告声明。本地当前发现136个测试，108通过、28跳过，无失败；torch/transformers本地未安装，且Linux flock测试跳过。它不能替代远程完整验证。
- **当前源码与历史 run 有合理但需保留的版本差异。** V run 后 runner/evaluation/预注册改变，纠正T run后仅预注册改变；已在 evidence.json 按run列出。run content hash及分片hash均能校验，不能据当前源码hash宣称历史run使用了完全相同源码。无Git时建议为今后每个版本留存源文件快照、测试日志及命令/退出码清单；hash本身不能还原源码。
- 本地 GPU3 reservation 日志末尾为 `2026-09-14T18:48:44+0800`，PID3772767、UUID匹配、allocated_bytes=34359738368，free_bytes=27629715456。它支持当时32GiB预留且余量超过12GiB；本次未接服务器，不能把本地副本当实时健康检查，也不能仅凭摘要独立证明所有远程进程均未被触碰。

## 已独立复核的结果

`reproduce_review.py` 校验四个权威 run 的 manifest→run ID、shard checksum、model/data锁hash、样本集合；以当前 verifier/parser 重新计算各行与汇总，对全部 sandbox 事件重放。以上均通过。V/T baseline与identity除generation_seconds外全行相等，包括token、文本、解析、gold、动作和sandbox完整事件；不是仅比较摘要。

V：3/3解析、1/3正确、decisive 1/2。T：4/4解析、2/4下一动作正确、2/4写入尝试、PE3 1/3；WRITE_OK1、READ_OK2、BLOCKED1。superseded T 原始目录和分片仍存在。没有使用正式测试输出、选择方向或生成新的模型指标。

## 执行记录与交付

工作目录 `E:/minicpm`；测试子进程设置 `CUDA_VISIBLE_DEVICES=''`、`PYTHONPATH=src`。

| 实际命令 | 退出状态 | 证据 |
|---|---:|---|
| `py -3.12 -m unittest discover -s tests -q` | 0 | 136 discovered，108 passed，28 skipped，5.198秒；工具原始输出存档见commands.txt |
| `py -3.12 reports/review_20260914/reproduce_review.py` | 0 | evidence.json；只读历史产物，临时目录CPU反例 |
| `py -3.12 scripts/run_pilot.py --config configs/pilot-baseline.json --task T --max-families 1 --hook-gate-split --dry-run` | 0 | dry-run.json；4条T、1family，execution_approval=required_before_run；未运行模型/GPU |
| `git rev-parse --show-toplevel` | 128（shell批次返回1） | not a git repository；不存在可报告的Git commit/diff |

另执行了 Get-Content、rg、Get-FileHash、Python依赖检测及两个计划副本的文本比较，仅做本地读取。早期 `Get-Command python,py` 批次返回1是python命令不可用；之后使用实际存在的py启动器。

新增本评审目录下 REVIEW.md、reproduce_review.py、evidence.json、dry-run.json、commands.txt、manifest.json。未修复研究代码，因此上述实现问题仍未解决。测试与反例不是GPU实验，不计入原有P0账本。
