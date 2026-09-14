# T03 后续：单次 GPU FP32·eager 精度对照方案（第②步已实现，GPU 运行**待批**）

**状态：第②步（实现探索性 FP32 模式 + 单测 + CPU 验证）已批准并完成；GPU FP32 运行仍 NOT APPROVED / NOT EXECUTED。本文件为预执行协议，先于任何 GPU 运行写下，避免事后合理化。**

## 0. 背景与边界
批3 的 GPU BF16·eager A/B/C 诊断（`artifacts/hooks/HOOK_VALIDATION_GPU_ABC_REAL_C_20260914.json`）得到：batched A−B=A−C=0.375/0.75、**B−C=0.0**；single-row B−C=0.367/0.391；CPU 同代码 A=B=C=0.0 精确。这**已排除本次对照覆盖的 mask/position/cache 使用错误**，并**支持**差异与 GPU 计算形状相关，但**具体来源（是否为 BF16 有限精度舍入）尚未验证**。本方案是一个**单变量**最小对照，用于区分来源，**不**重判 T03、**不**放宽阈值。

## 1. 目标与可区分的假设
只改变**计算精度**（BF16→FP32），其余全部固定，测量 GPU 上 A−B/A−C/B−C 的量级变化：

判读以**定性**为主。**量级预测仅供参考**：深层网络的 full-vs-cache 误差**不必**按 eps 线性缩放，`0.75/65536` 与 `64·eps_fp32=7.6e-6` **不是硬判据**，仅作为数量级参照。允许判为「不确定」：

- **支持精度主导（H_precision）**：GPU FP32 的 A−B 相比 BF16 的 0.75 **明显下降**（趋向 FP32 噪量级；参考已测 CPU FP32≈1.6e-5）。结论只表述为「**支持**」，非「证明」。
- **反驳精度主导（H_other）**：GPU FP32 的 A−B **未明显下降、仍与 BF16 同量级** → 指向与 dtype 无关的 GPU 形状相关差异，转逐层/逐组件定位，**而非改阈值**。
- **不确定（uncertain）**：GPU FP32 的 A−B 介于两者之间（部分下降但远未达 FP32 噪量级、或 batched/single-row 行为不一致、或与 CPU FP32 不一致）→ **如实判为「不确定」**，不强行归因，再提一个能进一步区分的最小后续步骤。

判读以 **2×2 矩阵**为准（已有三格，本方案补 GPU·FP32 一格）。CPU·FP32 格已用**真 C 探索性对照**复测（`KV_FULL_CPU_FP32_CONTROL_OFFICIAL_20260914.json`，与旧 `diagnose_kv_full` 的 1.6e-5 一致）：

| A−B 最大绝对差 | BF16 | FP32（TF32 关闭） |
|---|---|---|
| CPU（官方模型） | 0.0（已测，真 C） | **1.4e-5 / 1.6e-5**（已测，真 C 探索对照） |
| GPU3（官方模型） | 0.375 / 0.75（已测，真 C） | **本方案待测（GPU 未批准）** |

辅助判读（**仅参考，非硬判据**）：`eps_bf16/eps_fp32 ≈ 65536`；若差异大致随精度缩放（0.75/65536≈1.1e-5 仅作数量级参照）则与 H_precision 一致，但深层网络误差不必线性随 eps，故不以该比例作通过/否决定量门槛。同时比较 **GPU FP32 vs CPU FP32**：若两者接近，则 FP32 下设备差消失，进一步支持「BF16 GPU 形状相关舍入」；若 GPU FP32 仍 ≫ CPU FP32，则存在 FP32 下仍在的 GPU 形状相关差异（转 H_other / 不确定）。

## 2. 为什么先 FP32、不同时换 SDPA
SDPA 会同时改变**注意力后端**与数值路径，引入第二个变量，难以把结果归到精度还是后端。**先只动精度（保持 eager）**是单变量、最易解释的最小步骤。后端对照（SDPA）只在 FP32 结果仍不能解释差异时，再作为另一次单变量对照单独提交。

## 3. 固定项（除精度外全部不变）
- checkpoint：锁定 revision `62b9b3bd4308e72905c5bce38c1d6689549c525d`，`MODEL_MANIFEST.json`（sha256 `96985947…`）；权重 BF16 存储，加载时 `torch_dtype=float32` 上采样计算（权重数值不变，仅容器/计算精度变 FP32）。
- 输入：`input_ids=[[0,0,5,6],[7,8,9,10]]`、`attention_mask=[[0,0,1,1],[1,1,1,1]]`、固定 `next_token=[[49],[350]]`。
- 路径：同一份 A/B/C 代码（A=全 5-token 无 cache；B=4-token prefill+cache 解码；**C=真逐 token 持久 cache**），同一 `_pair` 对照与 single-row 变体。
- 后端：**eager**（不变）。设备：GPU3 `GPU-e5c246b7-…`（不变）。
- 资源协议：单 worker、32 GiB 预算、12 GiB 全卡余量、60s 只读审计 + `require_admission`、`RuntimeResourceGuard`、`PhaseBudget`、全局 flock；**释放 GPU3 受管预留→准入→运行→按原配置恢复预留并确认心跳**；GPU5/SenseVoice/其他用户进程不碰；不换卡、不多卡、本对照仅一次。

## 4. 最小代码改动（第②步**已实现**，含审核补充的三点）
`scripts/check_hooks.py` 的原 BF16 守卫 `if args.model_lock and args.dtype != "bfloat16"` **保持不变**；FP32 仅在显式探索开关下放行：
- **已实现** `--exploratory-precision-control` 开关：**仅**当该开关存在时允许 `--model-lock` 配 `--dtype float32`；无开关时 float32+model-lock 仍被原守卫拒绝（单测覆盖）。
- **已实现** 产物强制标注：`role=characterization_not_validation`、`exploratory_precision_control=true`、`authoritative_t03_status=failed_bf16_primary_unchanged`、`does_not_unlock_t04=true`；**不**写/替换任何 `HOOK_VALIDATION.json`；**不**改 `gpu_t03_kv_full_gate_status`（仍 failed）。
- **已实现** 输出名守卫：探索模式若 `--output` 以 `HOOK_VALIDATION` 开头则 `parser.error` 拒绝（防止被误当作正式凭据）。
- **已实现（审核点①：TF32 与矩阵乘法精度）**：新增 `_precision_backend_state()` 记录 `cuda.matmul.allow_tf32 / cudnn.allow_tf32 / float32_matmul_precision`；探索 FP32 模式在运行前**显式关闭 TF32**（`allow_tf32=False`×2 + `set_float32_matmul_precision('highest')`），避免名义 FP32 实为 TF32（~10-bit 尾数）；产物 `precision_backend` 同时记录 `active_during_run`（TF32 关）与 `default_at_entry`（**仅本进程进入时观测到的 PyTorch 默认**：matmul tf32=False、cudnn tf32=True、precision=highest；这**不**等同历史 BF16 运行的设置，详见 §4.1 文案修正），并注明 BF16 走 tensor-core、TF32 标志不影响 BF16 计算。
- **已实现（审核点③：探索报告不解锁 T04）**：`scripts/run_pilot.py` 的 `validate_hook_gate` 增加显式拒绝——任何 `role==characterization_not_validation` 或 `exploratory_precision_control` 为真的报告都**不能**作为正式 hook 验证凭据，即使 `status==passed` 且 device/dtype/backend/manifest 全匹配（单测覆盖：构造一个「看似通过」的 characterization 报告，gate 仍拒绝）。
- 复用现有真 C 与 `_pair` 逻辑，不改对照数学；沿用同一加载器/guard/日志，不新建第二套 GPU 入口。

> 备注：FP32 内部 `64·eps_fp32≈7.6e-6` 门限可能仍被 ~1e-5 触发——**预期**。审核修正后探索模式不再因数值门限提前中止：失败记入 `numerical_controls` 并继续采集 A/B/C，最终 `status=characterization_completed`（非 failed/passed）。本对照取其**量级**入 2×2 矩阵，**不**把 FP32 的 pass/fail 当作 T03 判定。

### 4.1 审核修正（第二轮，GPU 前；已实现+单测）
- **修正①（早期断言不再提前结束 FP32 对照）**：`run_checks` 增 `exploratory` 参数。探索模式下 identity/zero/self-patch/left-padding/kv_identity/kv_vs_full/projection 等**数值**门限失败一律**记入 `numerical_controls` 并继续**，确保 A/B/C 必被采集；**资源异常、非有限值（non-finite）仍立即停止**；权重被改等完整性不变量仍停止。**BF16 正式路径行为不变**（仍在原门限 fail-fast 抛出）。
- **修正②（失败报告不再丢重复噪声基线）**：所有数值检查的 `value/threshold/passed` 与 `baseline_repeat_max_abs`（含派生 tolerance）写入 `numerical_controls`，并嵌入可恢复的 `kv_full_diagnostics`——BF16 KV 门限失败时随 `structured_diagnostics=` 恢复，探索模式正常返回时直接在产物中。
- **文案修正**：`precision_backend.bf16_primary_note` → `entry_state_note`，明确 `default_at_entry` 只证明**本进程进入时**的设置，**不**等同历史 BF16 运行设置；历史状态须引用当时记录（BF16 主诊断产物早于该字段、未含 TF32 状态）。
- **针对性测试**：`test_early_numerical_failure_still_collects_abc_and_baseline`（早期 left-padding 失败后仍有 A/B/C+baseline，且 BF16 路径仍中止）、`test_exploratory_stops_on_non_finite_not_a_tolerance_failure`（非有限值仍停止）、失败诊断测试新增 `numerical_controls`/`baseline_repeat`/threshold 断言。全套 **110 通过**（+2）。

### 4.2 审核修正（第三轮，GPU 前；已实现+单测）
- **修正③（非有限值检查覆盖全路径，阻断项）**：原非有限守卫只查 batched A/B/C。现 `_gate` 对任何**非有限**控制值（NaN/Inf）在**两种模式都立即停止**（区别于「有限但超阈值」——后者探索模式仍记录并继续，保持不变）；并对未经 `_gate` 的路径补显式守卫：`baseline_repeat`、batched A/B/C、single-row A/B/C。由此 standalone(left-padding)、identity、kv_identity、kv_vs_full、projection 等路径的非有限值都会停止，探索模式不会带着 NaN/Inf 返回 `characterization_completed`。
- **文案修正（续）**：本计划 §4 与 §8 原仍把 `default_at_entry` 称为「此前 BF16 主诊断所处设置」，已统一为「仅本进程进入时观测到的默认，非历史 BF16 运行记录」。
- **针对性测试**：`test_exploratory_stops_on_non_finite_standalone_only`（仅 standalone 注 Inf→停止）、`test_exploratory_stops_on_non_finite_projection_only`（仅第 4 个 batched 解码调用=projected_decode 注 Inf→停止，并断言确到达该调用）、`test_finite_over_threshold_continues_but_non_finite_stops`（同一路径：有限超阈值→记录并 `characterization_completed`；非有限→停止）。全套 **113 通过**（+3），1 skipped。

### 4.3 审核修正（第四轮；已实现+单测）
- **修正④（逐 token C 中间步骤非有限值守卫，阻断项）**：原 batched C 循环只在 `c_steps` 记录 `logits_finite` 而**不在 false 时停止**；single-row C 循环的 `so.logits` 也**无检查**。现两个逐 token 循环每步直接 `torch.isfinite(logits).all()`，非有限**立即抛错（两模式）**——杜绝「中间步 NaN/Inf 但最终输出恢复有限」时仍返回 `characterization_completed`。
- **文案**：`execute()` 中 `precision_default` 注释由「state the BF16 primary diagnostic ran under」改为「**本进程入口状态（PyTorch 默认），非历史 BF16 运行记录**」，与 `entry_state_note` 一致。
- **针对性测试**：`test_exploratory_stops_on_non_finite_c_intermediate_step`（只污染 batched C 中间步 cache_position=1、最终解码仍有限 → 停止）、`test_exploratory_stops_on_non_finite_single_row_c_intermediate_step`（只污染 single-row C 中间步 → 停止）。全套 **115 通过**（+2），1 skipped。
- **对已执行 GPU FP32 运行的影响**：第④步已于上一轮经批准执行（`KV_FULL_GPU_FP32_CONTROL_20260914.json`），其 `C_call_sequence.logits_finite` 全为 True（5 步均有限）、single-row C 长度 [1,2,3,4]×2，**本缺口未在该次运行中触发**，A/B/C 量级结果有效；修正④为防御性加固，不改变该已完成运行的结论。

## 5. 记录的证据
GPU FP32 的 A−B/A−C/B−C（batched + single-row，每行 max/mean、最大差 vocab 索引+两侧 logits、argmax）；C 调用序列与每步 cache 长度；`baseline_repeat_max_abs`（FP32 重复噪声基线，用于把 A−B 与实测噪声比对）；dtype/backend/版本；权重前后摘要；峰值 allocated/reserved 显存（FP32 权重 ~9.4 GiB，预计峰值 ~10–11 GiB，仍在 32 GiB 预算内、保留 12 GiB 余量）；budget 结算；与 BF16/CPU 各格的 eps 缩放比。

## 6. 纪律护栏
- **T03 在 BF16 主配置下保持 failed**；本 FP32 对照是**来源刻画**，不是重判、不是放宽阈值、不是挑选通过子对照。
- 即便 FP32 结果干净，也只表述为「**支持**精度相关来源」，**不**宣称「证明无实现错误」或「根因确定」；逐层/逐组件定位（如需）另提最小方案。
- **（审核点②）允许判为「不确定」**：量级预测仅参考，深层网络误差不必按 eps 线性缩放；介于 H_precision 与 H_other 之间、或 batched/single-row/CPU-GPU 不一致时，如实记为 uncertain，不强行二选一归因。
- **（审核点③）探索性 characterization 报告绝不解锁 T04**：除产物 role 标记外，runner（`run_pilot.validate_hook_gate`）已硬性拒绝把 characterization 报告当作正式 hook 验证凭据；正常 BF16 守卫不变。
- 一次有界 GPU 运行；运行后恢复 GPU3 预留并确认心跳；失败/异常如实保留。
- 不自动展开后端/精度多维扫描；任何后续单变量对照再单独提交审核。

## 7. 执行前置条件与当前进度
1. ✅ 用户审核批准本方案 + §4 代码改动（含补充三点）；
2. ✅ 实现 §4 改动并补单测；CPU 上用 tiny + 官方模型验证 FP32 路径可跑、2×2 矩阵 CPU·FP32 格复现（见 §8）；
3. ✅ 提交实现摘要 + 针对性测试 + CPU A/B/C 结果；审核通过（含第二/三轮小修，见 §4.1/§4.2）；
4. ✅ 按 §3 资源协议执行**单次** GPU FP32 对照（结果见 §9）。

**当前：第④步已执行完成；GPU FP32 对照结果与判读见 §9。T03 BF16 主配置仍 failed、T04 未解锁。**

## 8. 第②步实现与 CPU 验证记录（已执行，无 GPU）
- **代码**：`scripts/check_hooks.py`（`--exploratory-precision-control`、`_precision_backend_state`、探索 FP32 关 TF32、产物 role 标记、HOOK_VALIDATION 名守卫）；`scripts/run_pilot.py`（`validate_hook_gate` 拒绝 characterization 报告）。
- **单测**：全套 **108 通过**（+7：5 个 FP32 模式 + 2 个 runner 拒绝），1 skipped。覆盖：探索 FP32 关 TF32 并记录 active/default 两态；BF16 主路径不声称关 TF32；产物含 4 个非凭据标记；探索输出名 `HOOK_VALIDATION*` 被拒；无开关时 float32+model-lock 仍被原 BF16 守卫拒；runner 拒绝「看似 passed」的 characterization 报告（role 标记 / 仅 exploratory 标志两种）。
- **CPU 验证（官方锁定模型，FP32，TF32 关，eager）**：`KV_FULL_CPU_FP32_CONTROL_OFFICIAL_20260914.json`，`status=failed`（A−B 1.6e-5 > `64·eps_fp32`=7.6e-6，预期）、`diagnostic_status=completed`、role/exploratory/authoritative/does_not_unlock_t04 标记齐全。真 C 正常执行（cache 1→5、全 finite、position 每步正确）。
  - **注**：该产物在 §4.1 修正①**之前**生成，故 `status=failed`（旧 KV 门限抛出路径）、且不含 `numerical_controls`；其 **A/B/C 量级（1.4e-5/1.6e-5）仍为有效证据**。修正后的探索流程下重跑会是 `status=characterization_completed` 并带 `numerical_controls`，但按审核指示**未重跑整套 CPU 模型验证**；新行为由 tiny-model 针对性单测覆盖（§4.1）。GPU FP32 正式运行将用修正后代码。
  - batched A−B = **1.38e-5 / 1.62e-5**；A−C = 1.81e-5 / 2.56e-5；B−C = 1.76e-5 / 2.37e-5；argmax 全一致；权重前后相同。
  - `precision_backend.active_during_run` = TF32 全关 + matmul `highest`；`default_at_entry`（**本进程进入时的默认，非历史 BF16 记录**）= matmul tf32 False / cudnn tf32 True / highest。
  - 实测确认 runner 把该 characterization 报告**拒绝**为凭据（`validate_hook_gate` 抛 ValueError）。
- **2×2 矩阵现状**：CPU·BF16=0.0、CPU·FP32≈1.6e-5、GPU·BF16=0.375/0.75 已测；**GPU·FP32 待第 4 步批准后测**。

## 9. 第④步 GPU FP32 对照结果（已执行，单次，GPU3）
**运行**：`artifacts/hooks/KV_FULL_GPU_FP32_CONTROL_20260914.json`，`status=characterization_completed`、4 个非凭据标记齐全、`model_source=locked_official_checkpoint`、manifest sha256 `96985947…`。资源：释放已核实的 GPU3 预留（pid 811416，SIGTERM 优雅停止、pid 文件删除、jsonl `stopped`）→ 60s 只读审计 → 准入（min_sampled_free≈58 GiB ≥ 44）→ 单 worker（GPU3、UUID 强校验、不换卡）→ wall≈107s → **恢复预留**（新 pid 1666871、`started`+`heartbeat` 确认、GPU3 空闲回到 25.7 GiB）。GPU5(433135)/SenseVoice/其他用户进程未碰。峰值显存 allocated 9.44 GiB / reserved 9.46 GiB（< 32 GiB 预算）；权重前后相同；budget 本次计入 42.8s，Phase 0 累计 **128.7s / 18000s**。

**TF32（审核点①）**：`active_during_run` = matmul tf32 **False** / cudnn tf32 **False** / matmul precision **highest**（显式关闭，已核验）；`default_at_entry`（本进程进入时默认，非历史 BF16 记录）= matmul False / cudnn True / highest。

**三路径（GPU3·FP32·TF32 关·eager·next_token=[[49],[350]]）**：

| 对照 | batched row0 / row1 | single-row row0 / row1 | argmax |
|---|---|---|---|
| A−B | 3.72e-5 / 3.77e-5 | 1.57e-5 / 1.91e-5 | 全一致 |
| A−C | 4.05e-5 / 4.10e-5 | 1.85e-5 / 4.01e-5 | 全一致 |
| B−C | 1.55e-5 / 1.86e-5 | 1.84e-5 / 2.56e-5 | 全一致 |

`numerical_controls`（审核点②可恢复）：baseline_repeat=0.0（GPU FP32 重复确定）；identity/zero_alpha/self_patch/kv_identity=0（passed）；**left_padding=2.67e-5、kv_vs_full=3.77e-5 均 > `64·eps_fp32`=7.6e-6 → passed=False**（探索模式**记录并继续**、未提前中止 → 仍采到完整 A/B/C）；projection_logit=0.87（passed）、token_accounting=336/336。真 C 正常（cache 1→5、全 finite、position 每步正确）。

**完成的 2×2 矩阵（A−B 最大绝对差）**：

| | BF16 | FP32（TF32 关） |
|---|---|---|
| CPU 官方 | 0.0 | 1.6e-5 |
| GPU3 官方 | 0.375 / 0.75 | **3.7e-5 / 3.8e-5** |

**判读（定性；量级预测仅参考，见 §1）**：BF16→FP32（TF32 关）使 GPU A−B 从 0.75 **下降约 4–5 个数量级到 ~3.7e-5**，与 CPU FP32（1.6e-5）同量级；A−C、B−C 同样降到 ~1e-5；argmax 全保留。→ **支持**「GPU BF16 的大 A−B 差异主要来自 BF16 形状相关有限精度舍入」（H_precision）。实际下降倍数（~2e4×）与 eps 线性参照（0.75/65536≈1.1e-5）同量级但不精确相等——按 §1，eps 线性缩放**仅参考、非硬判据**，深层网络误差不必线性随 eps，故不据此过度量化。
- **仍为「支持」非「证明」**：未做 kernel trace；FP32 下 A−B（3.7e-5）仍 > `64·eps_fp32`，说明 full-vs-cache 在各精度下都非逐位相同，只有**量级**随精度收缩；精确 kernel 级机制仍属推测。
- **不判为 uncertain**：下降幅度大、batched/single-row 一致、GPU FP32≈CPU FP32 同量级，非中间/矛盾结果。

**T03 状态（不变）**：BF16 主配置 A−B=0.75>0.5 → **T03 保持 failed**；FP32 为 characterization（`authoritative_t03_status=failed_bf16_primary_unchanged`、`does_not_unlock_t04=true`、runner 拒绝其作凭据）→ **T04 不解锁**。未放宽阈值、未挑选通过子对照。FP32 也超其自身 `64·eps_fp32` 门限（3.7e-5>7.6e-6），说明该 dtype 缩放门限对 GPU 上 full-vs-cache 过严——这是后续后端/阈值决策的背景，但**本批不自动改阈值、不自动展开后端扫描**；任何后续单变量步骤另提最小方案审核。
