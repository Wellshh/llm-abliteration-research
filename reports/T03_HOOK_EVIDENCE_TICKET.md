# T03-HOOK 证据矩阵与执行票据

日期：2026-09-14；状态：静态审计完成，未运行 GPU/T04，未执行本票据的缺失项。

当前候选判定：`historical_T03_bf16_gate=failed`；`T03_NUMERICS=failed_limit_recorded`；`T03_HOOK=candidate_passed_pending_amendment_approval`。该候选状态不是生效的 `passed` credential，也不是完整 T03 passed。

| 条件 | 当前证据 | 状态 | 最小补齐步骤 |
|---|---|---|---|
| no-hook / identity / zero / self-patch 等价 | `artifacts/hooks/HOOK_VALIDATION_CPU_ABC_OFFICIAL_BF16_20260914.json`：对应 max abs 均 0；GPU BF16 诊断也记录这些控制 | present（CPU）；GPU完整credential仍受数值限制 | 保持分路径记录；不以 argmax 替代 logit/噪声比较 |
| KV identity | 同一官方 CPU 产物 `kv_identity_max_abs=0`；GPU BF16 产物有 `kv_identity` 与真 C 调用记录 | present（已覆盖路径） | 静态复核字段与 cache 长度；不重写历史 GPU failed |
| padding/position/decode 计数 | GPU 产物记录 mask、position/cache_position、C cache 增长；`tests/test_check_hooks_kv.py` 覆盖计数 | present（记录/CPU测试） | 若需新 credential，仅按批准范围复核 manifest |
| prefill/decode hook coverage | `HOOK_VALIDATION_GPU_ABC_REAL_C_20260914.json` 与真 C 记录；脚本 `check_hooks.py` 覆盖两路径 | present（路径证据） | 归档字段/调用序列，保持单一 cache 路径 |
| 权重前后不变 | 官方 CPU/GPU 产物包含 `weights_before_sha256` 与 `weights_after_sha256` | present | 静态比较字段；异常仍停止 |
| finite values | GPU BF16/FP32 产物和第四轮防御性测试记录 finite；不能推断所有未来运行 | present（既有运行） | 新运行时沿用 finite guard |
| controlled information replacement | `tests/test_hooks.py:84–89` ToyModel 固定 `PatchSpec` 值 `[100,-100,0]`、layer/position，验证 argmax 从 2 变 0 | present（ToyModel 工程控制） | 只证明 hook 实现按预期改变可预测输出；不外推官方模型机制；官方产物的 `projection_logit_max_abs>0` 不能替代 | 保留测试路径与限制说明；不需升级为官方模型要求 |

`projection_logit_max_abs > 0` 只证明输出发生数值变化，不能证明受控信息替换产生了可预测目标，也不能满足完整机制保留。该条件不得由 argmax、KL、PPL、probe 或工具语法单独替代。

## 最小后续顺序

1. 保留现有 ToyModel 单测作为计划要求的工程控制证据；不读取 V/T formal test 效应。
2. 由 root 审核 amendment 后决定是否把候选状态更新为正式 `passed`；该状态更新不改变历史 BF16 gate 和 T03-NUMERICS。
3. 若后续需要官方模型或 GPU 证据，另行提交资源审计与人工批准；不自动执行。

## 条件 T04（本轮不执行）

仅允许 baseline/identity、pilot split、同一锁定 cache 路径、完整保留格式错误/截断/循环/失败分布；禁止干预选择，结果不得用于改阈值。即使 T03-HOOK 后续通过，T04 仍需 root/用户单独明确批准。
