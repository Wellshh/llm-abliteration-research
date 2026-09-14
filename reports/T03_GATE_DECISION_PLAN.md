# T03 门槛处理方案（供审核；不执行）

日期：2026-09-14  
状态：决策草案，未批准任何方案；本轮未运行 GPU、未启动 T04、未修改 `PREREGISTRATION.yaml` 权威字段。

## 1. 决策边界与当前结论

原始 BF16 主配置的 T03 判定永久保留为 **failed**：GPU3、官方锁定 checkpoint、BF16、eager、批量 A/B 对照的最大绝对 logit 差为 0.75，超过已执行实现中的 0.5（`64·eps_bf16`）门槛。不得用 CPU 结果、single-row 结果、argmax、B≡C、FP32 结果或任何通过的子对照追溯改写这一判定。

FP32 运行是 characterization，不是 formal credential：GPU A−B 约 `3.77e-5`，与 CPU FP32 同量级，支持“计算精度是 BF16 大差异的主要因素”，但没有 kernel trace，不能声称已证明具体舍入或 kernel 根因；也不能替代 BF16 hook gate。历史失败、原始产物、勘误和 provenance 均保持不变。

当前推荐：**采用方案 C 的拆分 gate 设计，但暂不解锁 T04**。先由 root/用户审核并批准协议 amendment，再按批准范围完成 CPU/静态可审计的 gate 交付；只有 T03-HOOK 通过且 T04 的明确批准到位，才可运行受限 baseline/identity pilot。若不批准 amendment，则执行方案 A，T04 保持 blocked。

## 2. 计划要求与门槛来源审计

计划原文要求：

| 计划位置 | 原文含义 | 对 T03 的界限 |
|---|---|---|
| `RESEARCH_PLAN.md:181` | padding/batch 不改变位置解释；多轮与 KV-cache 单独测试；干预须覆盖 prefill/decode 且不误处理 padding | 这是路径/位置控制要求，没有定义 full-vs-cache 的绝对 logit 数值门槛 |
| `RESEARCH_PLAN.md:185` | 无 hook、identity、self-patch、零强度应在同一后端重复噪声范围内等价；权重前后不变；异常退出清理 hooks；简单任务验证 hook 可改变输出 | 这是 hook 正确性/完整性控制，不能由 argmax、KL 或 PPL 单独替代 |
| `RESEARCH_PLAN.md:187` | 若比较 SDPA/eager，先比较各自重复 baseline；主实验只用一个通过测试的后端 | SDPA 只能作为后续单变量诊断，不能自动作为 eager 的替代 credential |
| `RESEARCH_PLAN.md:189–195` | S/V/T 行为 pilot 的初始准入阈值可在测试前最多修订两轮并保留日志；失败则标记该构念在当前协议下不适合机制确认 | 这不是 T03 full-vs-cache 数值门槛的授权。T03 拆分是基于已观察数据另行提出的 protocol amendment，须明确批准，不能由本段自动授权 |
| `RESEARCH_PLAN.md:385` | 建议 identity/self-patch、padding/batch/KV-cache 等独立测试 | 支持将控制拆成可审计子 gate，但未授权自动放宽完整 gate |
| `RESEARCH_PLAN.md:394–395` | T03 是 hooks 与基础运行对照；T04 是 pilot 与功效/资源重估 | T03 通过是 T04 的前置工程条件；T04 不能反向证明 T03 |

代码/产物中的 `64·eps_bf16=0.5` 是本次 T03 实现所采用的数值检查，并在 `reports/T03_FP32_CONTROL_PLAN.md` §9、`reports/ALIGNMENT_T00-T04.md` §2.2–§2.3 及 GPU 诊断 JSON 中记录。现有证据不能把它追溯描述为 `RESEARCH_PLAN.md` 已预注册的 full-vs-cache 绝对门槛。任何 amendment 必须说明它是数据后提出、从已观察数据出发、只适用于声明的 backend/dtype/shape/协议范围。

## 3. 证据矩阵

| 控制/证据 | 现状 | 可支持的结论 | 不能支持的结论 | gate 归属 |
|---|---|---|---|---|
| CPU 官方 BF16 A/B/C | A=B=C=0.0 | CPU 路径在该样例/后端数值一致 | GPU BF16 等价；完整机制保留 | T03-HOOK 辅助通过 |
| GPU BF16 批量 full-vs-cache A−B | 0.75 > 0.5 | 原始 BF16 数值门槛 failed | 可挑选子对照后称 passed；阈值根因 | T03-NUMERICS 限制 |
| GPU BF16 B−C | 批量逐位相同；真 C cache 逐步增长 | 本次 B/C cache 实现内部自洽，覆盖的 mask/position/cache 使用错误被削弱 | 所有 hook/模型实现错误均排除；A/full 等价 | T03-HOOK 辅助 |
| GPU BF16 single-row | B−C 有差异 | shape sensitivity 存在 | 证明机制保留或证明 kernel 根因 | T03-NUMERICS |
| GPU BF16 argmax | 各路径保持 | 离散选择在样例上保持 | 完整 logits、KL、PPL 或机制保留 | 观察性，仅报告 |
| GPU FP32 eager、TF32 关 | A−B 约 3.77e−5 | 支持计算精度主因 | 证明舍入/kernel 具体根因；重判 BF16 | characterization |
| identity/zero/self-patch、权重 hash、finite、padding/decode 记录 | CPU/代码测试与诊断覆盖；正式 GPU full credential 尚无 `status=passed` | hook 完整性可拆分审计 | full-vs-cache BF16 绝对一致 | T03-HOOK |
| baseline full-vs-cache 数值形状一致性 | BF16 GPU 未达到原实现门槛；FP32 仍非逐位相同 | 记录后端/dtype/shape 限制 | 用单一 argmax/KL/PPL 宣称完整机制保留 | T03-NUMERICS |

“通过”在本方案中不等于“完整机制保留”。probe、cosine、PPL、KL、工具语法、argmax 均只能作为各自控制或描述性结果；它们不能单独满足完整机制 gate。

## 4. 拆分 gate 的拟议定义

### T03-HOOK：hook 正确性与路径完整性

必要条件（全部满足）：

1. 同一锁定 checkpoint、dtype/backend 和同一 cache 路径下，无 hook、identity hook、zero-strength、自 patch 的输出/状态差异在**预先冻结的重复噪声范围**内；不能只比较 argmax。
2. KV identity 与真逐 token cache 的调用序列、`cache_position`、cache 长度、`position_ids`、attention mask 前缀和 padding 计数符合 manifest；B 与 C 是否相同须按记录报告，不预设结论。
3. prefill 与逐 token decode 都触发指定 hook；padding 不被误处理；异常退出清理 hook。
4. 权重/模型 manifest 前后 hash 不变；所有路径 finite；输出格式/截断/循环按结果保留。
5. 至少一个受控简单任务证明信息替换会改变可预测输出，证明 hook 并非静默失效。
6. 生成如获 T04 批准，必须走同一 cache 路径；baseline 与 identity 的行为结果需完整记录，不能只报成功样本。

判定：逐项 `passed`/`failed`/`blocked`，任一完整性不变量 failed 则 T03-HOOK failed；在 amendment 获批前统一标为 `candidate_passed_pending_amendment_approval`，该候选状态不是生效状态；仅数值 shape 差异归入 T03-NUMERICS，不得把它抹去。`tests/test_hooks.py:84–89` 的 ToyModel 单测满足计划第 185 行所需的受控简单任务：固定 `PatchSpec` 值 `[100,-100,0]`、固定 layer/position，并预期 argmax 从 2 变为 0。它证明 hook 工程实现可按预期改变可预测输出，范围不外推到官方模型机制。官方 CPU 产物的 `projection_logit_max_abs` 仍不能替代该 ToyModel 控制，也不能单独证明完整机制保留。候选状态不自动解锁 T04。

### T03-NUMERICS：full-vs-cache 的数值形状限制

这不是 hook 正确性 pass/fail 的替代，而是限制记录。至少报告 dtype（BF16 primary、FP32 characterization）、backend、batch/shape、A/B/C、single-row、重复噪声、max/mean、finite、argmax 和完整原始 logits 摘要。BF16 原始 A−B failed 永久保留。FP32 结果只能标为 characterization；没有 kernel trace 就标明具体根因未证实。

若 amendment 最终批准新的数值判据，必须在任何后续 T04 运行前冻结：适用 shape/backend/dtype、统计量、容差来源、重复次数、失败处理和独立验证范围。不得把 observed `0.75` 倒推成刚好通过的阈值，也不得只保留通过的子对照。

## 5. 三个方案

### A：保持原门槛并停止 T04

保留 BF16 `failed` 和现有 `0.5` 代码门槛；不把 FP32 characterization 当 credential；不做 T04。优点是解释最简单、零数据后修订风险。代价是无法区分“hook 已正确但 GPU BF16 shape numerics 受限”与“全部 T03 未通过”，工程信息利用不足。停止条件是原始 failed 已足够支持报告；任何继续必须另行批准。

### B：单变量 SDPA 对照

只改变 eager→SDPA，固定 checkpoint、BF16、输入、A/B/C 真 cache、batch/shape、资源和解析，独立记录 baseline repeat 与所有失败模式。SDPA 是诊断计算后端差异的可选后续，不是替代 eager 主配置，不自动改变 T03 判定，不自动解锁 T04。若后端结果仍有差异，报告不确定；若差异下降，也只能支持后端相关性。需先有人工批准；本轮不运行。

### C：前瞻修订并拆分 gate（推荐设计，待批准）

把 T03-HOOK 与 T03-NUMERICS 分开：前者验证 hook/cache/padding/decode/权重完整性，后者把 BF16 full-vs-cache shape sensitivity 作为已知限制。原始 BF16 gate 仍 `failed`，不改写历史。若 root/用户批准，可在严格限制下让 T04 baseline pilot 有条件前进：仅 `baseline` 和 `identity_hook`，不做干预方向选择；生成始终同一 cache 路径；保留 BF16 primary、所有格式错误/截断/循环和失败分布；pilot 结果不得用于改阈值或选择干预；T04 每次正式启动仍需 root/用户明确批准。

推荐 C 的理由是它忠实区分了计划要求的 hook 工程控制与已观察到的 dtype/shape 数值限制，并保留阴性证据。C 不提出新的 full/cache 通过阈值，也不把完整 T03 改称 passed；建议状态字段为 `historical_T03_bf16_gate=failed`、`T03_HOOK=passed|failed|blocked`、`T03_NUMERICS=failed_limit_recorded`。主要风险是 amendment 可能被误读为“把失败改成通过”、受限 pilot 可能被误读为机制实验，且 T04 baseline 仍不能证明完整机制保留。若人工不批准或 T03-HOOK 任一完整性条件未通过，保持 blocked，回到 A。

## 6. 最小执行步骤与停止条件（仅供批准后执行）

1. root 审核本草案、确认是否采用 C；记录批准人、时间和版本 hash。
2. 在不改写原始预注册状态的前提下，新增 amendment 文件/条目，冻结字段见 §7；更新 run manifest 说明 amendment 适用范围。
3. 只做静态/CPU 验证和必要的已有 hook 单测；若需 SDPA 或真模型 credential，另行提交单变量运行申请。
4. 生成 T03-HOOK gate report，逐项列出证据路径、hash、失败/未运行项；T03-NUMERICS 单独附上历史 BF16 failed 与 FP32 characterization。
5. 只有人工明确批准 T04 后，才允许受限 baseline/identity pilot；先做 dry-run/资源审计，仍按 GPU UUID、32 GiB 预算、12 GiB 余量和单 worker 规则。

立即停止条件：任一完整性不变量失败或 non-finite；manifest/template/backend/dtype 不匹配；出现非 baseline/identity 条件；尝试读取 V/T 正式 test 选择干预；资源审计不满足；输出被覆盖；或发现结果将用于追改阈值。任何停止都保留原始日志，不删除、不改写 failed。

## 7. 拟议 PREREGISTRATION amendment 字段草案（不写入权威文件）

```yaml
amendment:
  id: t03_gate_split_v1
  status: proposed_data_after_amendment
  proposed_at: 2026-09-14
  approval_required: root_and_user_explicit
  basis:
    observed_data:
      bf16_gpu_batched_full_vs_cache_max_abs: 0.75
      historical_implementation_threshold: 0.5
      fp32_gpu_eager_characterization_max_abs: 3.77e-5
    evidence_paths:
      - artifacts/hooks/HOOK_VALIDATION_GPU_ABC_REAL_C_20260914.json
      - artifacts/hooks/KV_FULL_GPU_FP32_CONTROL_20260914.json
      - reports/T03_FP32_CONTROL_PLAN.md
  historical_status:
    bf16_original_gate: failed_permanent
    threshold_retroactive_change: false
    fp32_is_formal_credential: false
  gates:
      T03_HOOK:
      purpose: hook/cache/padding/decode/weight_integrity
      required_conditions: [no_hook_identity_zero_self_patch, kv_identity, padding, decode, weight_hash, finite, controlled_information_replacement]
      status: candidate_passed_pending_amendment_approval
      unlocks_T04_automatically: false
    T03_NUMERICS:
      purpose: record_dtype_backend_shape_sensitivity
      bf16_primary_report: required_and_failed_history_preserved
      fp32_role: characterization_only
      argmax_kl_ppl_alone_sufficient: false
  conditional_T04_scope:
    allowed_conditions: [baseline, identity_hook]
    intervention_selection: forbidden
    generation_cache_path: one_locked_path_only
    preserve_invalid_truncated_loop_and_format_failures: true
    results_may_change_threshold: false
    requires_separate_explicit_approval: true
  exclusions:
    - no_claim_of_kernel_root_cause_without_trace
    - no_generalization_beyond_locked_checkpoint_dtype_backend_shapes
    - no_SDPA_substitution_for_eager_primary
  freeze:
    freeze_before_any_conditional_T04_run: true
    freeze_artifact_hash: null
    approver: null
    approval_timestamp: null
```

## 8. 本轮执行记录

- 读取：`E:\minicpm\AGENTS.md`、`RESEARCH_PLAN.md`、`PREREGISTRATION.yaml`、`SOURCES.json`、`reports/T03_FP32_CONTROL_PLAN.md`、`reports/ALIGNMENT_T00-T04.md`、`scripts/check_hooks.py`、`scripts/run_pilot.py`。
- 静态检查重点：计划行 181、185–195、385、389–395、420–424；runner 行 24–37、53–66、106–113；脚本/报告中的 characterization 拒绝 T04 逻辑。
- GPU：未运行。本轮未启动 T04，未创建 reservation/worker，未接触 GPU3/GPU5。
- 权威状态：未改 `PREREGISTRATION.yaml`；未改历史产物、勘误或 provenance。
- 测试：本轮未重跑已有 115 passed/1 skipped；该数字仅作为现有报告事实引用，不宣称本轮重跑。
- controlled information replacement：`tests/test_hooks.py:84–89` 的 ToyModel 单测固定 patch 值/位置并验证预期 argmax 从 2 变为 0，满足“受控简单任务上信息替换改变可预测输出”的工程控制；范围仅限 hook 实现，不证明官方模型机制。官方 CPU BF16 产物的 `projection_logit_max_abs=0.796875` 不能替代该控制；当前候选状态为 `T03_HOOK=candidate_passed_pending_amendment_approval`，不是生效的 `passed` credential。
- Git：`E:\minicpm` 当前未发现 `.git`，无法提供 commit/diff；本文件是同步工作树中的新增草案。需要 root 在其实际版本控制端确认 diff/提交。
