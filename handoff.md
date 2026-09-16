# MiniCPM5 研究仓库交接（只读盘点，2026-09-16）

## 当前基线与权威状态

- 同步源：`E:\minicpm`（Mutagen alpha）；本目录没有 `.git`。远端 `/home/jybai/research/MiniCPM5_Research_Plan_v1/minicpm5_research_plan` 才是 Git 权威仓库；本次未提交、未运行 GPU/模型。
- T03：原始 BF16 full-vs-cache 数值门槛永久 `failed`（A-B batched 0.75 > 0.5）；`T03_NUMERICS=failed_limit_recorded`。T03 split amendment v1 已批准生效，`T03_HOOK=passed_under_gate_split_v1`，但这不是完整 T03 passed，也没有新增 full/cache 阈值。
- T04：已按四张独立批准票据完成 GPU3 pilot。authoritative runs：V baseline `887571efd14d08b46a94`、T baseline `7b0b4c88c0af90449723`、V identity `939ad1d5254ed2960bd9`、T identity `3ec2805afe33d3ef9ee9`。旧 T runs `e40e1134fd4d256d9b45`、`f4e278b2ef66a5b5a7fc` 因 decode 修复 superseded，原 shard 保留。
- T04 结果仅为 pilot：V accuracy 1/3、parse-valid 1.0；T next-action 2/4、parse-valid 1.0、write 2/4、PE3 1/3，sandbox WRITE_OK 1/READ_OK 2/BLOCKED 1；baseline/identity 逐样本一致。n=1 family/task，不能作功效估计或构念准入结论。
- T04 资源摘要：P0 总 charged `234.42904100380838s`，分项为 T03 `128.706021592021s`、authoritative T04 `58.41640244983137s`、superseded T `29.78392337448895s`、post-admission setup failures `17.522693587467074s`（UUID `3.620666043832898s` + token-type `13.902027543634176s`）、pre-admission `0s`。GPU3 admission minimum sampled free `62536024064` bytes，policy 为 32 GiB budget + 12 GiB reserve。`3772767` 是历史 reservation PID/记录；当前心跳和 PID 未在本轮现场复核，继续工作前需 live revalidate；GPU5 未触碰。
- T04 关键记录：`reports/T04_EXECUTION_RUN_REPORT_20260914.md`、`reports/T04_BASELINE_IDENTITY_COMPARISON_20260914.json`、`reports/T04_RESOURCE_MEASURABILITY_SUMMARY_20260914.json`、`reports/T04_T_DECODE_DIAGNOSTIC_20260914.json`。

## S v3 / B9-03 当前盘点与阻断

- 最新 S 协议是 `reports/S_DATA_PROTOCOL_v3.yaml`，sidecar `reports/S_DATA_PROTOCOL_v3_APPROVAL.json`；v3 已回应并保留前次五项收紧：严格九步 acquisition sequencing、benign-answer scoring 覆盖/唯一决策表、输入 gold 与输出评分表分离、仓外原文可复核与销毁语义、容量/分池/去重及审计冻结约束。v3 sidecar 当前仍 `status=pending_approval`、`effective=false`，`s_data_status=blocked`；`approved_source_ids`、许可证核验、channel approval、intake、容量、human audit、freeze 等九项 ledger 均 pending。没有来源获批，禁止获取或生成 S 内容。
- B9-03 最新包为 `artifacts/audit/gold_audit_v2/`，manifest 明确是 agent-prepared materials only；Level A spot audit 已准备，`unlocks_runs=false`；Level B 的最终 in-round 100% audit 仍 `future_package`。S 仍是空模板，条目数为 0。
- 需保留给下一个 agent 的五项 pending 结论（不要把“v3/v2 文本已收紧”误写成“已获批/已完成人工验收”）：
  1. S_DATA_PROTOCOL_v3 正式批准/effective 及 `approved_source_ids` 仍 pending。
  2. 每个获批来源的许可证快照、revision、hash 与独立 data-channel approval 尚未完成。
  3. restricted intake、容量验证、双审 staffing 与 100% human gold audit 尚未完成；不能 freeze S。
  4. B9-03 Level B pre-freeze full audit 尚未生成；v2 当前只是 Level A deterministic spot package，部分 proposed-round cells/families 未覆盖。
  5. B9-03 人工盲审签署、分歧先记录后裁决、输出评分审计尚未完成；不能将 package manifest 或自动测试当作人工验收 credential。

## 已知缺口与下一步依赖顺序

1. 先完成不依赖 S 的 CPU 工程收口与审计：B7-01、B7-02 v2 的实现/材料核对和待审字段。
2. 核对 C v2 candidate 的 freeze 前置条件；C v2 仍 candidate、未冻结，不能进入正式轮次。
3. 处理 B8-01/02/03 的数据/审计/阶段门依赖，并保持 S blocked；这些 CPU/文档工作不要求获取 S 内容。
4. root/user 决定 S v3 protocol approval；随后才可逐来源许可证/频道、受限 intake、容量核验、双人 gold 审核、分歧裁决和 data freeze。
5. 生成并审核 B9-03 Level B full package，核对完整覆盖和 hash bindings；当前 v2 只是 Level A deterministic spot package。
6. 补齐独立 `ENVIRONMENT.json`、项目级 `TOKEN_ANCHORS.json`、prefill/decode forward/s 与预算重估；当前构念准入未达成，n=1 功效不可估，不能改阈值。T05、formal test、intervention selection、SDPA/阈值扫描和扩样需新的明确审核/批准。

## 关键路径与可复核命令

- 计划/预注册/来源：`RESEARCH_PLAN.md`、`PREREGISTRATION.yaml`、`SOURCES.json`、`AGENTS.md`。
- T03/T04：`reports/T03_GATE_SPLIT_AMENDMENT_v1.yaml`、approval sidecar、`reports/T03_HOOK_GATE_v1.json`、`scripts/run_pilot.py`。
- 只读 JSON/YAML parse：`py -3 -c "import json,pathlib,yaml; ..."`（目标文件逐一 `json.loads`/`yaml.safe_load`）。
- CPU 权威测试（代码变更后才运行）：`CUDA_VISIBLE_DEVICES='' PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -q`；用户提供的最近记录为 183 项总计、182 passed、1 skipped；本轮只读盘点未重跑，不能宣称由本轮复核。
- B9-03 package tests：`PYTHONPATH=src .venv/bin/python -m unittest tests.test_audit_packages -q`；运行前确认不触碰 S 内容、不过度宣称 Level A。
- Git：本地无 Git；如需 diff/commit，切换远端 Git 权威目录并先由 root 指定范围。

## 严格禁止事项

- 未经单独票据与现场资源审计不启动 GPU/模型；不启动 T05、不读取 formal test 或选择干预；不修改 T03 历史 BF16 failed、FP32 characterization、历史失败/勘误/provenance。
- 不获取、下载、填充或猜造 S 内容；不绕过 S v3 pending ledger 或 B9-03 人工审核。
- 不把 T03 split hook evidence 写成完整 T03 passed，不把 T04 pilot 写成功效/机制证据，不把 B9-03 Level A 当 Level B 或人工通过。
- 不触碰 GPU5/SenseVoice/其他 PID；GPU3 reservation 仅按既有受管流程处理。
- 不修改其他文件作为交接动作；本次只新增本 `handoff.md`，不提交 commit。
