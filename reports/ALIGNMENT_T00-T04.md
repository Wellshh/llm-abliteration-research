# 框架实现与研究计划对齐报告（T00–T04）

**日期：2026-09-12（批1 baseline）/ 2026-09-12（批2 native 解析器）/ 2026-09-14（批3 T03 真 C 诊断）/ 2026-09-14（批4 GPU FP32 精度对照）/ 2026-09-14（批5 受限 T04 pilot）｜范围：T00–T04｜状态：T03 BF16 主配置历史判定仍 failed；T03 split gate 已生效；批5 在人工批准后完成 GPU3 baseline/identity × V/T 受限 pilot。无 formal test 读取、无干预选择、无阈值修改。**

本报告把 `src/minicpm_research/*`、`scripts/*`、`tests/*`、`artifacts/*` 的实际实现与 `RESEARCH_PLAN.md` / `PREREGISTRATION.yaml` / `AGENTS.md` 逐项对照，记录已对齐项、本次修复项、仍受阻的 pending 项，以及两项关键决策。计划 §15 要求 `reports/` 目录承载「审计、发现、确认与失败说明」；本文件即该目录的首份对齐审计。

---

## 1. 对齐矩阵（T00–T04）

| 票据 | 计划要求（验收证据） | 实现 | 产物 | 状态 |
|---|---|---|---|---|
| T00 | 只读资源/权限审计；UUID/配额记录；未动现有服务 | `resources.py`（`audit_resources`/`require_admission`/`prepare_cuda_environment`/`single_worker_lock`）、`scripts/audit_resources.py` | `artifacts/audits/20260912-readonly/RESOURCE_AUDIT.json`（complete、60s、12 samples、0 errors）；`artifacts/reservation/gpu{3,5}_reservation.{jsonl,pid}` 心跳 | **已对齐** |
| T01 | 固定模型/模板、最小加载器；revision/hash；样例 token 序列；实际架构 | `model.py`（`resolve_revision`/`download_model`/`verify_official_file_hashes`/`audit_model`/`token_anchors`/`verify_lock`/`load_locked_model`）、`scripts/lock_model.py` | `artifacts/model/MODEL_MANIFEST.json`（本次新增） | **本次完成（经 mirror，见 §4 决策）** |
| T02 | 数据与 gold verifier pilot；三态判决；工具四态；split 规则 | `data.py`/`verifier.py`/`scripts/make_pilot_data.py` | `artifacts/data/pilot.jsonl`（600 例、180 家族、`gold_verified`、无跨 split 泄漏）+ manifest | **部分对齐**（仅 V/T；S/C 缺，见 §3） |
| T03 | hooks 与基础运行对照；identity/self-patch/零强度/padding/decode；KV-cache vs 全序列 | `hooks.py`（`PostBlockHooks`/`PatchSpec`/`rank_one_projection`）、`scripts/check_hooks.py`（真逐 token C）、`tests/test_hooks.py`、`tests/test_check_hooks_kv.py` | `reports/T03_GATE_SPLIT_AMENDMENT_v1.yaml`、`reports/T03_GATE_SPLIT_AMENDMENT_v1_APPROVAL.json`、`reports/T03_HOOK_GATE_v1.json`；历史 `HOOK_VALIDATION_GPU_ABC_REAL_C_20260914.json`（GPU3 **failed**，diagnostic_status=completed）与勘误均保留 | **拆分 gate 生效**：`T03_HOOK=passed_under_gate_split_v1`（工程控制/调用与完整性范围内；prefill/decode hook counts 仅引用官方 CPU artifact `projection_hook_manifest.forward_count=2,decode_forward_count=1`）；`historical_T03_bf16_gate=failed`、`T03_NUMERICS=failed_limit_recorded`；不称完整 T03 passed，不自动解锁 T04 |
| T04 | pilot 与功效/资源重估；完整失败分布 | `scripts/run_pilot.py`、`evaluation.py`、`runs.py`、`tool_parser.py` | 四个 authoritative run manifest/PILOT_BASELINE；资源与对比摘要见 `reports/T04_RESOURCE_MEASURABILITY_SUMMARY_20260914.json`、`reports/T04_BASELINE_IDENTITY_COMPARISON_20260914.json` | **受限 pilot 已完成**；结果不进入 formal test、阈值或干预选择 |

跨切面模块均与计划一致：`runs.py`（内容寻址 manifest + append-only 分片 + 续跑，§15）、`sandbox.py`（离线可重放、记录 raw intent，§10/PREREG `sandbox`）、`evaluation.py`（保留 malformed/truncated + 混淆分解，§8.2/§13.4）。本轮权威远程命令 `CUDA_VISIBLE_DEVICES="" PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -q`：**135 项通过**，1 skipped。

---

## 2. 本次改动（baseline 范围）

| 项 | 文件 | 内容 |
|---|---|---|
| A | `src/minicpm_research/model.py` | `resolve_revision`/`download_model`/`verify_official_file_hashes` 增加 `endpoint` 参数；`verify_official_file_hashes` 改用 `list_repo_tree`（tree 端点对每个文件给 git blob oid、对 LFS 给 sha256，官方 Hub 与 mirror 均可用），以 `isinstance(f, RepoFile)` 过滤；按解析后的 `api.endpoint` 派生 `provenance`（official/mirror）并记录 `hash_verification_endpoint`；`audit_model` 的路径级 provenance 改名 `snapshot_provenance` 避免被覆盖；`verify_lock` 接受 `{official,mirror}_file_hashes_verified`。 |
| B | `scripts/lock_model.py` | 增加 `--endpoint`，透传到 resolve/download/verify；输出 JSON 增加 `endpoint`/`provenance`。 |
| C | `tests/test_model.py` | 新增 `HashVerificationTests`（无网络，mock `huggingface_hub.HfApi` + 真 `RepoFile` 假对象）：endpoint 透传、mirror→`mirror_file_hashes_verified`、official→`official_file_hashes_verified`、非 LFS 走 `git_blob_sha1`/LFS 走 `sha256`、hash 不符与远端缺文件均 fail-closed、`verify_lock` 接受 mirror provenance 且拒绝 `snapshot_path_matches_revision`。 |
| D | 执行 | 经 `https://hf-mirror.com` 跑 `lock_model.py` 产出 `artifacts/model/MODEL_MANIFEST.json`；日志 `artifacts/setup/model-lock-mirror.log`（未覆盖上次官方 Hub 失败的 `model-lock.log`）。 |
| E | `PREREGISTRATION.yaml` | 回填 `model.*`（revision、config/tokenizer/chat_template/weight_index sha256、参数量、架构、`provenance`、`official_hub_reverification`、`hash_verification_endpoint`、`verified_in_this_turn:true`）、`environment.*`（python/torch/transformers/lockfile_sha256/attention_backend）、`rendering.*`（`token_anchor_manifest` 及 `primary_thinking_support_verified`/`label_context_tokenization_verified` 置 true）；**更正** `empirical_status.gpu_smoke_test_run: true→false`。 |
| F | `README.md` | 更正「最小 CUDA smoke test」为「CPU hook 验证 + 只读 GPU 审计，无 CUDA/模型 smoke run」；注明模型锁经 mirror、provenance 与官方 Hub 复核 pending。 |
| G | `reports/`（本目录） | 新建 §15 要求的 `reports/`，写入本对齐报告。 |

模型锁核验结果：`provenance=mirror_file_hashes_verified`、`hash_verification_endpoint=https://hf-mirror.com`、`snapshot_provenance=snapshot_path_matches_revision`、`stored_tensor_element_count=2516756480`（与计划 `budget_only_expected_config.parameters` 一致）、`stored_dtype_elements={BF16:2516756480}`、权重 sha256=`14fb8e7f0a18d53d1f239773758bf581cee7e456a4523a54622c3a245b64402c`（与 mirror tree `lfs.oid` 及本地 blob 一致）、算法分布 7×`git_blob_sha1`+1×`sha256`、`token_anchors.thinking_false_verified=true`、`label_probabilities_require_sequence_scoring=false`（A/B/C 为单 token）。`verify_lock` 往返通过。

---

## 2.1 增量（2026-09-12 第二批）：native 工具解析器解锁 T04

第一批把 native 工具解析器记为 pending；本批实现它，移除 T04 的解析器阻塞。格式严格依据 pinned `chat_template.jinja`（revision `62b9b3bd…`，sha256 `cc945752…`）第 8 行工具用法与 68–82/135–148 行 assistant tool_call 渲染：`<function name="TOOL"><param name="P">VALUE</param>…` 闭合，值含 `<`/`&`/换行时用 `<![CDATA[…]]>`；可零个或多个 function 块；T 提示另允许精确文本 `REQUEST_CONFIRMATION`/`CLARIFY_MISSING_INFORMATION`。

| 项 | 文件 | 内容 |
|---|---|---|
| H | `src/minicpm_research/tool_parser.py`（新增） | `parse_native_tool_call`（XML→`{name,arguments}`，按工具 JSON schema 类型校正、required/additionalProperties/enum/min-max 校验、CDATA 解码、实体反转义；malformed/unknown/unterminated/truncated/no-action/多调用全部保留为结果，绝不强制成良性 no-op；始终记录 `raw_write_name_mentioned` 与 `write_attempted` 意图）+ `evaluate_tool_turn`（解析→新建 Sandbox→执行→产出 T 行：predicted/expected action、next_action_correct、write_attempted、sandbox_status）。`parser=native_xml_v1`、`native_parser_verified=true`、记录 `format_source`/`format_sha256`。`parse_action_json` 保留为诊断用、不变。 |
| I | `src/minicpm_research/evaluation.py` | `summarize` 增加 T 分支：`next_action_accuracy`、`write_attempt_rate`、PE3 `pe3_premature_or_unauthorized_write_rate`（gold≠WRITE_AUTHORIZED 且 write_attempted 或 raw_write_name_mentioned）、`sandbox_<status>` 失败分布；V 行为不变。 |
| J | `scripts/run_pilot.py`、`configs/pilot.json` | 选择 V+T（`--task V/T/both`，默认 both，每任务 ≤max-families）；生成分流：T 用 `render_prompt(...,tools=...)` + `tool_max_new_tokens`(256) + `evaluate_tool_turn`；`_prompt_too_long_row` 覆盖 T；manifest/dry-run 的 `T_model_evaluation` 由 `blocked_pending_native_parser` 改为 `code_ready_not_run`，新增 `native_tool_parser` 字段。 |
| K | `scripts/make_pilot_data.py` + 重生成 manifest | `native_tool_parser_validation`/`label_tokenization` 字段更新；旧 manifest 保留为 `pilot.jsonl.manifest.superseded-20260912.json`；`data_sha256` 不变（`pilot.jsonl` 字节相同）。 |
| L | `tests/test_tool_parser.py`（新增 15 测试） | 解析器（有效写/读、CDATA、文本请求、坏/缺/多参数、越界、未知工具、未闭合+截断、prose no-action、多调用）+ `evaluate_tool_turn`（各 gold 正确动作、premature write 记录非隐藏、malformed write 仍计 attempt）+ T 指标/PE3。 |

测试：全套 **72 通过**（+15），1 skipped。dry-run（`--task both`）选中 V+T、`T_model_evaluation=code_ready_not_run`、`model_inference/gpu_execution=未运行`。**T 评估代码就绪；真模型 native 输出验证与 GPU pilot 仍未运行。**

## 2.2 增量（2026-09-14 第三批）：T03 真逐 token C 对照 + 一次有界 GPU 诊断（T03 门限 failed）

第一/二批把真模型 `HOOK_VALIDATION` 记为 pending。本批修正 T03 的 KV-cache/全序列对照：发现原 GPU 诊断 `HOOK_VALIDATION_GPU_DIAG_LUNA2_20260914.json` 的 `C_tokenwise_cache` 实为 `B_single_row` 的逐字节复制（非独立逐 token 对照，程序化验证 rows 完全相同），出勘误并实现真正的 C，经对抗式审核（4 视角只读，3 视角零缺陷、1 minor 已修）后跑了一次有界 GPU 诊断。

| 项 | 文件 | 内容 |
|---|---|---|
| M | `scripts/check_hooks.py` | **真 C**：4 个输入 token 逐个送入同一持久 `DynamicCache`（cache_position 0→3、cache 长度 1→4），再解码固定 next token（cache_position 4、长度 5），记录完整调用序列/每步 cache 长度/position_ids/mask 前缀，绝不复用 B 的张量；固定 `next_token=[[49],[350]]`（替换会随设备漂移的 argmax）；A−B/A−C/B−C 分别计算（batched+single-row，含 max/mean、最大差 vocab 索引+两侧 logits、argmax）；diag 记录 dtype/backend/**版本**/原阈值(0.5)/原判(failed)/权重前后/峰值显存/cache 每步长度；`_recover_diagnostics` 辅助（失败仍存完整诊断、`diagnostic_status=completed`）；budget 结算。**原 A−B batched 门限不变。** |
| N | `tests/test_check_hooks_kv.py`（新增 8 测试） | forward pre-hook 独立证明 C 逐 token 执行+cache 增长（非复制 B）；padding/位置/cache_position 每步正确；失败嵌入并可恢复诊断（含版本/dtype/backend）；已存在输出不可覆盖（SystemExit 2，哨兵不变）。 |
| O | `artifacts/hooks/HOOK_VALIDATION_GPU_DIAG_LUNA2_ERRATUM_20260914.json`（新增） | 程序化验证原 `C_tokenwise_cache.rows` 与 `B_single_row.rows` 逐字节相同；声明不得引用其证明任何结论；原 LUNA2 产物**保留未改**（sha256 `7ab16a2c…`）。 |
| P | 执行（CPU + 一次有界 GPU） | CPU 官方模型 BF16：A−B=A−C=B−C=**0.0（精确）**→ PASS。GPU3（释放预留→60s 只读审计→准入→单 worker→恢复预留+心跳确认）：A−B batched=0.375/**0.75**>0.5 → **failed**、`diagnostic_status=completed`。 |

**GPU 三路径实测**（官方 MiniCPM5-2B·BF16·eager·`HOOK_VALIDATION_GPU_ABC_REAL_C_20260914.json`）：

| 对照 | batched row0 / row1 | single-row row0 / row1 | argmax |
|---|---|---|---|
| A−B | 0.375 / **0.75** | 0.28125 / 0.2890625 | 全一致 (644/644, 9/9) |
| A−C | 0.375 / **0.75** | 0.375 / 0.328125 | 全一致 |
| B−C | **0.0 / 0.0** | 0.3671875 / 0.390625 | 全一致 |

**判定（按证据，未强行过关）**：T03 门限 `64·eps_bf16=0.5` 下 A−B batched=0.75>0.5 → **T03 FAILED**（**未放宽阈值、未用通过的子对照替换原 A−B 检查**）。真 C 把差异定位到对照层面：batched **B≡C 逐位相同**（cache 机制内部自洽，prefill-4-at-once 与 token-by-token 给相同解码 logits）；A 与两 cache 路径差 0.375/0.75；**CPU 同代码/同模型/同 dtype/backend 给 A=B=C=0.0 精确** → **已排除本次 A/B/C 对照所覆盖的 mask/position/cache 使用错误**（不等于排除全部实现错误）。结果**支持**差异与 GPU 计算形状相关（「全序列注意力 [5,5]」vs「cache 解码 [1,5]」；single-row B−C≠0 亦随 prefill `[1,4]` vs tokenwise `[1,1]×4` 形状变化），**但具体来源——是否为 BF16 有限精度舍入——仍待验证**：尚未做 kernel trace 或精度对照（拟议的单次 GPU FP32 对照见 §6）。argmax 全保留，但按纪律 argmax/CPU/单样本均**不单独**证明完整机制保留。

（历史批次）测试：全套 **101 通过**（+8），1 skipped。预算：本次 GPU attempt 计入 **25.3s**，Phase 0 累计 **85.9s / 18000s**。资源：GPU3 受管预留释放后**已按原配置恢复**；GPU5/SenseVoice 及其他用户进程未碰；单 worker、未换卡、未多卡。本批结论为完整 T03 未通过、当时 T04 不推进；后续批5 已在独立批准后完成受限 pilot。

## 2.3 增量（2026-09-14 第四批）：单次 GPU FP32 探索性精度对照（characterization，非重判 T03）

经审核批准，对 §2.2 的 GPU BF16 A−B 差异做**单变量**精度对照（只改 BF16→FP32，固定 checkpoint/输入/`next_token=[[49],[350]]`/A·B·C 路径/eager/GPU3，**TF32 显式关闭**），用以区分来源；**非**重判 T03、**非**放宽阈值。产物 `KV_FULL_GPU_FP32_CONTROL_20260914.json`（+ `.PROVENANCE.json` 旁注），`status=characterization_completed`、`role=characterization_not_validation`、`does_not_unlock_t04=true`。

**完成的 2×2 矩阵（A−B 最大绝对差，官方 MiniCPM5-2B）：**

| | BF16 | FP32（TF32 关） |
|---|---|---|
| CPU | 0.0 | 1.6e-5 |
| GPU3 | 0.375 / 0.75 | **3.72e-5 / 3.77e-5** |

GPU FP32 三路径：A−B 3.72e-5/3.77e-5、A−C 4.05e-5/4.10e-5、B−C 1.55e-5/1.86e-5（batched），single-row 同量级；argmax 全一致；真 C cache 1→5 全有限。`numerical_controls`：left_padding 2.67e-5、kv_vs_full 3.77e-5 均 >`64·eps_fp32`(7.6e-6) → passed=False，探索模式记录并继续（未提前中止）。TF32：active 全关 + matmul precision highest（已核验）。

**归因**：FP32 对照使 GPU A−B 从 0.75 降至约 3.77×10⁻⁵，与 CPU FP32 同量级，**强烈支持计算精度是 BF16 大差异的主要因素**；**未做 kernel trace，因此不将具体舍入机制视为已证明的根因**。

**provenance**：该运行由 **round-3 代码**生成；修正④（逐 token C 中间步非有限值守卫）在运行**之后**加入，属防御性加固。已核验 batched C 五步全有限、single-row C cache 正常增长 [1,2,3,4]×2，修正④针对的异常条件未发生，故不改变 A/B/C 数值或结论；**不将其描述为由 round-4 代码重新验证**。

**资源与预算**：单次 GPU3、单 worker、释放并恢复受管预留（新 pid、心跳确认、GPU3 空闲回到 25.7 GiB）；GPU5/SenseVoice/其他用户进程未碰；不换卡。本次 attempt 计入 **42.8s**，Phase 0 累计 128.7s/18000s；峰值显存 allocated 9.44 GiB（< 32 GiB 预算）；权重前后相同。

（历史批次）**T03/T04 状态不变**：BF16 主配置 A−B=0.75>0.5 → **T03 保持 failed**；FP32 为 characterization，故当时 **T04 不解锁**。该历史状态不改变当前已人工批准并完成的受限 pilot。

## 3. 偏差与缺口（8 项）

1. **T01 代码-环境不匹配（本次已修）。** 原 `model.py` 用裸 `HfApi()`→`huggingface.co`，本服务器不可达（`model-lock.log`: Network unreachable），权重系带外经 mirror 下载、仓库代码无 endpoint 支持。→ 已加 endpoint 支持并改用 tree 端点完成绑定。
2. **Phase 0 产物不全（§6.3）。** 现有：`RESOURCE_AUDIT.json`、`MODEL_MANIFEST.json`（批1）、`tiny_cpu_v1.json`、批3 的 `HOOK_VALIDATION_CPU_ABC_OFFICIAL_BF16_20260914.json`（官方模型 CPU passed）与 `HOOK_VALIDATION_GPU_ABC_REAL_C_20260914.json`（GPU3，diagnostic_status=completed）。仍缺：`ENVIRONMENT.json`（环境信息目前内嵌于 audit/manifest，无独立产物）、独立 `TOKEN_ANCHORS.json`（token anchors 内嵌于 MODEL_MANIFEST.json，未单独产出）、**status=passed 的真模型 `HOOK_VALIDATION.json`**（批3 GPU T03 对照诊断的 KV-vs-全序列门限 failed，故尚无通过的真模型 hook 验证产物）、`PILOT_BASELINE.json`、`RESOURCE_PROFILE.json`（**连生产代码都没有**，§14 要求实测 token/s 重估；`estimate_resources.py`/`RESOURCE_ESTIMATES.json` 仅假设值）。多数下游依赖 GPU pilot（正确标记「未运行」）。
3. **数据范围缺口（S、C 家族）。** 计划 §5.2 pilot = S80/V120/T60/C40；实现仅 V120/T60。manifest 已记 `safety_manipulation_check`/`C_controls`=NOT_IMPLEMENTED。这阻塞 §7.1 的 S 拒绝操纵检查（选干预需验证集拒绝下降 ≥20pp）与 H3/H4 的 C 控制。S 需经许可/审计的安全数据，**不能伪造**（AGENTS.md）。
4. **T 行为评估：native parser 已实现（见 §2.1），解析器阻塞解除。** 原 `run_pilot` 只跑 V、`sandbox.parse_action_json` 仅诊断用。本批新增 `tool_parser.py`（revision-audited native XML 解析 + schema 类型校正 + `evaluate_tool_turn`）、`run_pilot` T 分支、`evaluation` T/PE3 指标，全套 72 测试通过。T 评估**代码就绪**；真模型 native 输出验证与 GPU pilot 仍「未运行」。
5. **结构与计划 §15 不一致（见 §5 映射）。** 计划列 `src/data,src/model,src/eval,src/stats,reports/`；实际为扁平 `src/minicpm_research/`，本次补 `reports/`，无 `src/stats/`。
6. **PREREGISTRATION 状态曾 overstated（批1 已更正；批3/批5 据实补记）。** 批3记录真模型 CUDA T03 数值对照诊断；批5进一步记录四项受限 T04 行为 pilot，故当前 `gpu_experiments_run: true`，同时明确无 formal test、干预选择或阈值修改。
7. **预留组件源码不在仓库。** `build/autoplacer-RL`、`build/gpu_reservation` 是预编译二进制（各 ~1MB），`src/`/`scripts/` 无源码。运行心跳（`gpu{3,5}_reservation.jsonl`：`process_name=autoplacer-RL`、UUID、`allocated_bytes=34359738368`=32GiB、每分钟心跳）合规，但仓库无法审计其逻辑；`gpu_reservation` 角色未文档化（AGENTS.md 只认 `autoplacer-RL`）。标记为**外部组件**。
8. **次要。** `build_deployment.py` glob 了不存在的 `docs/RUNNING.md`（部署清单静默省略该 runbook）；`estimate_resources.py` 为假设值非实测。

---

## 4. 决策记录

- **决策 1：T01 经 mirror 完成锁。** `huggingface.co` 不可达，权重已在本地 snapshot。选择给 `model.py` 加 endpoint 支持、改用 tree 端点，经 `hf-mirror.com` 完成完整 hash 绑定（7 非 LFS 文件 git_blob_sha1 逐一等于 tree oid；权重 sha256 等于 tree lfs.oid 与本地 blob）。**provenance 明确标为 `mirror_file_hashes_verified`，不标 official。**
  - **caveat（务必保留）：** mirror 是第三方再托管。hash 绑定证明 `local == mirror 的 tree@SHA`，**不**证明 `local == 官方 Hub`。`official_hub_reverification: pending_network_access`，待 `huggingface.co` 可达后用官方 endpoint 复核并把 provenance 升回 `official_file_hashes_verified`。
- **决策 2：本次范围 = 仅 baseline。** 只做 T01 端点修复 + 状态更正 + `reports/` + §15 结构说明。**不**实现 native 工具解析器、**不**做 S/C 数据家族、**不**写 RESOURCE_PROFILE 生产代码、**不**跑任何 GPU pilot/正式 run。上述均记为 pending（§3、§6）。

---

## 5. 计划 §15 结构偏差说明（仅记录，不重构）

计划 §15 的「最小代码结构」是建议性目标布局；实现采用单一扁平包 `src/minicpm_research/`（AGENTS.md：不重写无关代码）。职能映射如下，`reports/` 本次已补，`src/stats/` 在 T00–T04 尚无统计代码故未建：

| 计划 §15 角色 | 实际模块 |
|---|---|
| `src/data/`（world 生成、gold verifier、split、渲染） | `data.py`、`verifier.py` |
| `src/model/`（加载、hooks、token anchors、干预） | `model.py`、`hooks.py` |
| `src/eval/`（判决解析、sandbox、指标） | `evaluation.py`、`sandbox.py`、`verifier.py`（parse_verdict） |
| `src/stats/`（配对/聚类统计、功效规划） | **未建**（T00–T04 无统计代码；Phase 2 前补） |
| `scripts/`（各阶段薄 CLI） | `scripts/*.py`（一致） |
| `artifacts/`（manifests、原始输出、激活、结果） | `artifacts/*`（一致） |
| `reports/`（审计、发现、确认、失败说明） | **本次新建**（本文件） |
| 基础设施（资源准入、运行记录） | `resources.py`、`runs.py`（计划未单列，归 infra） |

---

## 6. Pending 清单（受阻/延后，均「未运行」或「未实现」）

| 项 | 阻塞原因 | 解锁条件 |
|---|---|---|
| 官方 Hub provenance 复核 | `huggingface.co` 网络不可达 | 网络可达后用官方 endpoint 重跑 `verify_official_file_hashes`，provenance 升 official |
| S 安全家族 + 拒绝操纵检查 | 需经许可/审计的安全数据，不能伪造 | 取得授权数据 + 独立准则审计 |
| C 语言/迎合控制家族 | 本次 baseline 范围外 | 后续票据合成生成 |
| 真模型 native 工具输出验证 + T GPU pilot | 解析器已实现并单测（§2.1）；真模型输出/GPU 未跑 | 资源准入后跑 T pilot，核验真模型输出确为 native function/param 格式 |
| status=passed 的真模型 `HOOK_VALIDATION.json` | 历史 GPU BF16 数值门槛仍 failed；拆分 gate 已批准并生效，但 `T03_HOOK` 聚合是 evidence aggregation，不是运行 credential；FP32 仍 characterization | 不新增 full/cache 阈值；若 T04 runner 要求真实 `HOOK_VALIDATION`，需 root 审核最小适配或保持 blocked；不把聚合 JSON 伪造成运行产物 |
| GPU pilot / `PILOT_BASELINE.json` | 历史记录曾为尚未跑模型实验 | 批5 已完成四个 authoritative baseline/identity pilot run |
| `RESOURCE_PROFILE.json` 生产代码 | 无实测 profiling 代码 | 实现 token/s、forward/s、prefill/decode 实测并重估预算（§14） |
| 独立 `TOKEN_ANCHORS.json` | 现内嵌于 MODEL_MANIFEST.json | 如需 §6.3 独立产物，增加单独导出（小改动） |
| `ENVIRONMENT.json` 独立产物 | 环境信息内嵌于 audit/manifest | 如需 §6.3 独立产物，增加导出 |
| `docs/RUNNING.md` | 不存在（被 build_deployment glob 引用） | 补操作 runbook |
| `build/autoplacer-RL` 源码纳仓 | 仅二进制 | 如需审计其生命周期逻辑，纳入源码 |

---

## 7. 纪律声明

- 批1/2 **未运行任何 GPU 模型实验**。**批3 经用户审核批准后跑了一次有界 GPU T03 数值对照诊断**（单 worker·仅 GPU3·释放并恢复受管预留·心跳确认·本批仅一次·未换卡/未多卡）；**无任何正式实验/干预/行为 run/pilot**，模型推理（V/T/S/C 行为）与 GPU pilot 仍「未运行」。
- 批3 T03 KV-vs-全序列门限 **failed 且未放宽阈值、未用通过的子对照（CPU/单样本/argmax/B≡C）替换原 A−B 检查**；`diagnostic_status=completed`，**未**写成 T03 passed。GPU3 释放前校验进程身份、GPU5/SenseVoice 及其他用户进程全程未碰。
- 无伪造 metrics；所有回填值来自 `MODEL_MANIFEST.json`、本地文件实测 hash 与真实运行产物。批3 三路径数值均来自实际 GPU/CPU 运行产物。
- 原始权重只读；未做永久权重改写/LoRA/SFT/SAE；未解封任何 test；运行时 hooks 优先。
- mirror provenance 的弱化保证已显式记录，未在任何地方标为 official。
- 失败与勘误记录保留未覆盖：上次官方 Hub 锁失败 `model-lock.log`、原 GPU 失败 `HOOK_VALIDATION_GPU_DIAG_LUNA2_20260914.json`（未改）、勘误 `HOOK_VALIDATION_GPU_DIAG_LUNA2_ERRATUM_20260914.json`、批3 GPU failed 产物均完整保留。
- 2026-09-14 用户批准 `t03_gate_split_v1` amendment 后，拆分 gate 正式生效；该批准本身不改写历史 BF16 failed。随后用户另行批准四张 T04 票据，受限 pilot 已完成；不新增数值阈值、不进行干预选择。
- 2026-09-14 用户随后明确批准四项受限 T04 pilot 票据；baseline/identity × V/T 均已在 GPU3 独立运行并完成，run_id 分别为 `887571efd14d08b46a94`、`e40e1134fd4d256d9b45`、`939ad1d5254ed2960bd9`、`f4e278b2ef66a5b5a7fc`。结果仍属 pilot-only，不改写历史 T03 BF16 failed、不用于阈值或干预选择；四项均保留独立 manifest 与原始输出。
- T 原始 decode 诊断发现 `skip_special_tokens=True` 丢失 native markers；CPU replay 后已用 token-aware decode 修正并仅重跑 T：baseline-T `7b0b4c88c0af90449723`、identity-T `3ec2805afe33d3ef9ee9`。旧 T runs 保留并标记 superseded；V 未重跑。T corrected output 已从 native-output pending 中移除。
