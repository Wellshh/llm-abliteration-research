# T04 最终权威摘要（2026-09-14）

最终 authoritative runs：V baseline `887571efd14d08b46a94`、V identity `939ad1d5254ed2960bd9`、T baseline `7b0b4c88c0af90449723`、T identity `3ec2805afe33d3ef9ee9`。V：accuracy 1/3、parse-valid 1.0；T：next-action 2/4、parse-valid 1.0、write 2/4、PE3 1/3，sandbox 为 WRITE_OK 1、READ_OK 2、BLOCKED 1；两条件逐样本一致。GPU3 reservation 当前 PID `3772767`，32 GiB，UUID 正确且心跳新鲜；GPU5/其他进程未触碰。

# T04 GPU3 pilot execution record (2026-09-14)

四份逐票据批准 artifact 已生成并通过本地 `validate_t04_execution_approval`：baseline-V、baseline-T、identity-V、identity-T。批准来源是本线程本轮用户指令，范围仅限这四项票据；未扩大到正式 test、干预选择、SDPA 或阈值修改。

按顺序尝试 baseline-V。第一次命令误加 `CUDA_VISIBLE_DEVICES=3`，runner 在资源审计前拒绝并记录失败 artifact，原因是环境不是已验证单 UUID。保留该失败记录。

去除额外环境变量后，baseline-V 完成独立 60 秒资源审计并释放 reservation 后通过显存准入，但 worker 启动时报告 `CUDA runtime UUID differs from admitted UUID`，exit 1，completed_examples=0；模型未产生样本或 metrics。该 content-addressed run 未重试。

随后恢复 GPU3 reservation。首次恢复尝试因 CUDA 初始化 OOM 失败；仅 reservation helper 使用 `CUDA_VISIBLE_DEVICES=3` 重启后成功恢复，PID 3422046，UUID 为 GPU-e5c246b7-afc2-cccd-e66d-fa1ca4eb089e，分配 32 GiB。GPU5 和其他进程未触碰。baseline-T、identity-V、identity-T 未启动。

(中间时间点记录，已由后续执行更新) 原始输出位置：远程 `artifacts/runs/t04-baseline-V/51f6ad0cb3c6792c0104/`，包含 manifest、events 和四次 failure JSON；失败分别为环境冲突、显存准入不足、runtime UUID mismatch，以及 canonical UUID 修复后首个生成调用的 `token_type_ids` model-input 兼容性错误。失败 attempts 均保留，未删除。

（中间时间点记录，后续已审核修复）只读 property probe 证实 PyTorch `str(properties.uuid)` 返回不带 `GPU-` 前缀的完整 UUID；runner 已改为严格 canonicalization。随后 baseline/identity pilot 已完成。

第四次失败已修复：编码显式传入 `return_token_type_ids=False`，并严格只接受 `input_ids` 与可选同形状 `attention_mask`；未知 key、缺失 input_ids 或 shape 错误均 fail closed。第四次 admitted worker wall time 约 13.902 秒，包含模型加载但无样本计算。远程仅 tokenizer smoke 已验证 V/T 首条 prompt keys 为 `input_ids, attention_mask`，shape 分别为 `[1,271]`、`[1,517]`；未重跑 GPU/T04。

修复审核后按原批准顺序完成四项 pilot：baseline-V run_id `887571efd14d08b46a94`（3 examples）、baseline-T `e40e1134fd4d256d9b45`（4）、identity-V `939ad1d5254ed2960bd9`（3）、identity-T `f4e278b2ef66a5b5a7fc`（4）。四项均 exit 0，独立 output/manifest，未读取 formal test、未选择干预、未修改阈值。GPU3 reservation 已恢复为 PID `3630412`、32 GiB、UUID 正确并有新鲜心跳；GPU5/其他进程未触碰。

汇总：V 两个条件均 `VALID=3`、accuracy `1/3`、decisive accuracy `1/2`、parse-valid `1.0`；T 两个条件均 `4` 行 `sandbox_INVALID`、parse-valid `0.0`、write attempts `0`。baseline/identity 的 pilot 输出保持原始文本、token IDs、解析失败与 sandbox 结果；这些结果不构成正式机制或门槛证据。

后处理 CPU 诊断见 `reports/T04_T_DECODE_DIAGNOSTIC_20260914.json`：T shard 的 raw token IDs 在 `skip_special_tokens=True` 下丢失 native function/param 标记；保留 special tokens 并按 token ID 去除末尾 EOS 后，baseline/identity 各 4 行均可被 parser 识别为 `VALID`。既有 shard/PILOT_BASELINE 未修改；此前 T INVALID 结果已标记为 decode pipeline artifact，后续纠正重跑已完成。

CPU replay 已逐行完成：baseline/identity 各 4 行 old `INVALID/NO_ACTION` 均修正为 `VALID`，并得到正确 sandbox/action 字段；四个 example 在两条件间 corrected parser/action 结果一致。随后仅重跑两张 T：baseline-T 新 run_id `7b0b4c88c0af90449723`、identity-T 新 run_id `3ec2805afe33d3ef9ee9`，均 exit 0、各 4 examples。旧 T runs `e40e1134fd4d256d9b45`、`f4e278b2ef66a5b5a7fc` 标记为 superseded_by_decode_fix，原 shard 保留。
