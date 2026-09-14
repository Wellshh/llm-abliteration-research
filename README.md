# MiniCPM5 科研计划包 v1.0

日期：2026-09-10（最后对齐 2026-09-12）。状态：详细设计与预注册草案；未注册。已完成 GPU 3 只读资源审计与合成小模型的 **CPU** hook 验证；**无 CUDA/模型 smoke run，模型实验未运行**。模型已锁定到官方 revision `62b9b3bd4308e72905c5bce38c1d6689549c525d`，hash 绑定经 `hf-mirror.com` 完成（`provenance=mirror_file_hashes_verified`，弱于官方 Hub；官方 Hub 复核 pending 网络）。详见 `reports/ALIGNMENT_T00-T04.md`。

- `RESEARCH_PLAN.md`：完整研究计划、假说矩阵、数据、干预、因果验证、统计、资源、阶段门和执行票据。
- `PREREGISTRATION.yaml`：机器可读的预注册草案。`model`/`environment`/`rendering` 已由 T01 模型锁回填；`intervention`/`statistics`/`data` 的选择与 hash 字段仍为 `null`，需 Phase 1 现场填写；不能当作已冻结配置。
- `AGENTS.md`：执行 agent 的权限、范围、资源和科研纪律。
- `SOURCES.json`：一手来源、原三份报告及本次核验范围；明确未取得的原始配置。
- `estimate_resources.py`：仅用 Python 标准库重算参数/缓存预算及近似样本量，**不是模型实验程序**。
- `RESOURCE_ESTIMATES.json`：上述估算程序输出；全部是按假设配置计算，不是 GPU 实测。
- `artifacts/model/MODEL_MANIFEST.json`：T01 模型锁产物（revision、各文件 sha256、经 mirror 的 hash 绑定、token anchors、环境版本）；`provenance=mirror_file_hashes_verified`，官方 Hub 复核 pending。
- `reports/ALIGNMENT_T00-T04.md`：框架实现与计划的对齐矩阵、偏差、决策与 pending 清单。

第一批只执行计划的 T00–T04。管理员已授权 GPU 3 主卡和 GPU 5 备用卡，并允许两卡分别在资源门槛内运行 32 GiB 受管常驻预留；正式实验仍限单 GPU worker。模型 revision 与模板/token anchors 已锁定核验；T04 的 native 工具解析器与 T 评估代码已实现并单测（`src/minicpm_research/tool_parser.py`），T pilot **代码就绪**，但真模型 native 输出验证与 GPU pilot **仍未运行**；正式扫描或解封 test 仍需真模型 hook 验证与 pilot 通过后再启动。
