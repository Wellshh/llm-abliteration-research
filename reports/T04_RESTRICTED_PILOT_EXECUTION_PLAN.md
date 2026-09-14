# T04 受限 pilot 执行方案（已批准并完成；仅 pilot 范围）

状态：T03 gate split amendment 已生效；用户已逐项批准四张 T04 GPU3 pilot 票据并完成 baseline/identity × V/T。结果仅限 pilot，不改写 T03 历史失败、不进入 formal test 或干预选择。

## 范围与条件

- 仅使用 `split=pilot`，首批 `max-families=1`，按任务分别运行 V 或 T；不读取 V/T formal test，不选择干预方向。
- 条件必须拆成两个独立 run manifest：一个 `condition=baseline`，一个 `condition=identity_hook`。不得把两种条件合并为一个 run 或覆盖同一 run 输出。
- checkpoint/revision、tokenizer/template、BF16、eager、prompt/decode 配置和数据 hash 固定；生成始终使用同一锁定 cache 路径。identity 只验证 hook，不改变权重。
- 保留所有原始文本、raw token IDs、invalid、truncated、loop、解析失败和 fake sandbox 事件；不把格式错误强制改成成功或弃权。
- 结果只用于受限 pilot 的失败分布、资源与可测量性评估，不用于阈值修订、干预选择、V/T collateral maximization 或机制确认。

## T03 gate 依赖与 runner 兼容点

正式拆分证据为 `reports/T03_HOOK_GATE_v1.json`，并由 `reports/T03_GATE_SPLIT_AMENDMENT_v1.yaml` 与其 approval sidecar 支撑。它是 `evidence_aggregation_not_runtime_credential`，不是 `HOOK_VALIDATION` 运行产物，也不包含官方模型运行 credential。hook 触发计数只引用官方锁定模型 CPU artifact 的 `projection_hook_manifest.forward_count=2`、`decode_forward_count=1`；GPU `C_call_sequence` 仅表示真 C cache 1→5 与 finite 状态，不证明 hook trigger counts。

现有 `scripts/run_pilot.py:53–66,115` 的旧 `validate_hook_gate` 仍要求：报告 `status == passed`、`model_source == locked_official_checkpoint`、model manifest hash、device、dtype、backend 全匹配，并拒绝 characterization。拆分 gate 的 `status=passed_under_gate_split_v1` 与 aggregation 类型不能直接通过旧守卫；FP32 characterization 也明确不能作为凭据。

已实现并执行：`scripts/run_pilot.py` 增加显式 `--hook-gate-split`，仅当 amendment YAML `effective=true`、approval sidecar hash 匹配、正式聚合 JSON 类型/状态/历史 failed 字段一致、条件为 baseline/identity、且 `dtype=bfloat16`、`attention_backend=eager` 与配置匹配时，记录 split gate 元数据并通过 gate 校验。默认旧 `--hook-validation` 行为保持不变，两个输入互斥；adapter 不接受 FP32、任意新数值阈值、selected edit 或 formal test split。

非 dry-run 的 split 执行使用 `--t04-execution-approval PATH`。批准文件绑定 amendment/aggregation/sidecar SHA、独立 config/data/output、condition、task、`max_families=1`、GPU UUID、批准语义和时间。template 与 pending proposal 保留为历史材料；本次实际执行使用四份独立 approved artifact。

四项 proposal 票据保留在 `reports/T04_EXECUTION_TICKETS_PROPOSED.json`，作为批准前的 point-in-time 历史材料；实际执行使用四份独立 approved artifact，复制并校验所有内容 hash、批准时间/语义与 `approval_id`，并保留 `single_content_addressed_run_allow_resume` 约束。proposal 文件本身不是执行批准。

adapter 已通过针对性 CPU 测试与 dry-run 验证；本文件不绕过资源/执行批准，也不把 dry-run 当模型执行。

## 已批准票据执行结果（2026-09-14）

四项独立 GPU3 pilot 均已完成：baseline-V `887571efd14d08b46a94`（3 examples）、baseline-T `e40e1134fd4d256d9b45`（4）、identity-V `939ad1d5254ed2960bd9`（3）、identity-T `f4e278b2ef66a5b5a7fc`（4）。每项使用独立配置、output_dir、manifest 和批准 artifact；结果仅为 pilot-only 失败分布与资源/可测量性记录，不用于阈值、干预选择或正式 test。

T decode 修正后，旧 T runs 已标记 `superseded_by_decode_fix` 并保留；仅 T 票据按同一参数重跑：baseline-T `7b0b4c88c0af90449723`、identity-T `3ec2805afe33d3ef9ee9`，均 4 examples、exit 0。V runs 未重跑。

## 资源与启动前检查（仅获独立批准后）

单 worker、仅授权 GPU3 UUID `GPU-e5c246b7-afc2-cccd-e66d-fa1ca4eb089e`、32 GiB budget、12 GiB 全卡余量；先做 60 秒只读资源审计和 `require_admission`，使用 `PhaseBudget` 与全局 worker lock。释放 GPU3 受管预留后运行，结束时按原配置恢复并确认心跳；GPU5、SenseVoice 和其他进程不碰、不自动换卡、不多卡。

每个条件使用独立 output/run manifest，记录 amendment/evidence paths、model/data/template hash、GPU UUID、资源审计、起止时间、condition、split、失败行与原始输出。磁盘余量低于 15 GiB、全卡余量低于 12 GiB、超 32 GiB、非有限值、manifest 不匹配、worker/预留接管失败或出现非允许 condition 时，在安全分片边界停止并原子落盘。

## 已完成范围与后续边界

本批执行前已由 root/用户逐项明确批准并完成。后续仍需另行批准的边界为：T05、formal test 读取、intervention selection、SDPA/阈值修改、扩样或新增条件。

任何批准均不授权干预选择、正式 test、SDPA 扫描、阈值调整或跨条件合并。T04 运行失败、格式错误、截断、循环和 sandbox 失败均保留并报告。
