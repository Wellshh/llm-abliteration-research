# 远端运行 T00–T04

正式 GPU worker 每次只使用一张授权卡。GPU 3 主卡、GPU 5 备用卡各有 32 GiB 项目额度；两卡不能合并为一次 64 GiB 实验，也不会自动切卡。所有正式 test 均保持关闭。

## 安装与本地验证

远端研究目录：`/home/jybai/research/MiniCPM5_Research_Plan_v1/minicpm5_research_plan`。

```bash
cd /home/jybai/research/MiniCPM5_Research_Plan_v1/minicpm5_research_plan
bash scripts/bootstrap_server.sh
.venv/bin/python scripts/make_pilot_data.py --seed 20260912
.venv/bin/python scripts/run_pilot.py --dry-run
```

安装只修改项目 `.venv`；不修改生产环境。已验证的精确依赖另存于 `artifacts/setup/requirements-resolved.txt`。本地 Windows 可用 `py -3.12` 替换命令中的 `.venv/bin/python`；CPU 数据和资源解析单测不需要安装模型依赖。

```powershell
$env:PYTHONPATH = 'src'
py -3.12 -m unittest discover -s tests -v
py -3.12 scripts/make_pilot_data.py --seed 20260912
py -3.12 scripts/run_pilot.py --dry-run
```

默认数据为 V 120 家族×3条件，T 60家族×4条件，共600条。四种V规则由独立有限世界验证器穷举验证；同家族的条件和标签映射保持一致。数据命令再次执行只接受相同内容，不覆盖不同seed的数据。S许可与拒绝rubric、C语言控制、人类双审、长度/否定词匹配、未见正式模板尚待完成。

## 资源审计与模型锁定

```bash
.venv/bin/python scripts/audit_resources.py --seconds 60 --output-dir artifacts/audits/manual-001
.venv/bin/python scripts/lock_model.py --resolve-revision main --cache-dir .cache/huggingface --output artifacts/model/MODEL_MANIFEST.json
.venv/bin/python scripts/check_hooks.py --device cpu --output artifacts/hooks/tiny-cpu-001.json
```

模型只在第一次显式锁定时解析 `main` 为完整SHA。锁文件记录官方文件哈希、BF16 safetensors元素数、config、tokenizer、原生模板、thinking=False与上下文标签tokenization、依赖版本。后续运行离线读锁，不访问浮动revision、不执行remote code、不改变原始权重。若输出锁已存在，命令拒绝覆盖；模型更新必须使用新审计目录。

tiny hooks是随机小Llama的实现验证，并不是MiniCPM5实验结果。真实checkpoint验证使用：

```bash
.venv/bin/python scripts/check_hooks.py --device cuda:0 --dtype bfloat16 --model-lock artifacts/model/MODEL_MANIFEST.json --output artifacts/hooks/minicpm-gpu-001.json
```

GPU入口先取得统一Linux进程锁、采样至少60秒、核对GPU UUID/调度器绑定、预算及余量，才导入并使用CUDA。可用显存不足预算+12GiB、同卡已有受管预留、MIG启用、调度器绑定不明确都会停止，不杀进程、不覆盖调度器设置。PyTorch allocator限制不是全进程硬隔离。

既有32GiB预留是独立CUDA进程，不能与新的32GiB worker叠加。运行前需通过受管预留的正常生命周期交还主卡额度，然后重新审计；脚本不会自行终止它。GPU5已有SenseVoice，不动它。正式worker退出后，如恢复预留，仍须独立满足现场预算+12GiB门槛。

## 小样本基线与恢复

```bash
.venv/bin/python scripts/run_pilot.py --max-families 12
```

默认选12个完整V家族，共36条。配置文件是 `configs/pilot.json`：单卡BF16、eager、greedy、prompt上限2048、输出上限128、batch=1。只开放baseline与identity_hook；不允许选择方向或读取正式test。需要CPU检查时显式传 `--device cpu`，它不能代替GPU资源或速度证据。

内容哈希决定 `artifacts/runs/<run_id>/`，保存manifest、原始事件、不可覆盖结果分片、失败记录、token anchors及汇总。完全相同的命令可恢复；改变模型、数据、代码、配置或依赖将产生新的run_id。格式错误、截断、超长prompt均保留，不能计为ABSTAIN；基础设施失败单独留档。

T已具备四态gold、纯内存sandbox、读写记录、确定性重放和严格原生parser contract；`run_pilot.py --task V/T/both` 会保留T格式失败与动作序列。真实锁定checkpoint hook gate、原生模板运行时验证和T模型评价仍须单独通过阶段门；CPU/mock测试不计作模型实测。T单次生成只报告下一步动作，多轮最终成功需单独实现。S/C、双人审查和配对条件功效模拟未完成前，阶段门保持关闭。

## Mutagen与输出管理

现场发现现有 `minicpm` 会话的本地源是 `E:\minicpm`，本任务工作目录是 `E:\minicpm-research`，不是同一目录；会话当时也处于重连状态。本次保留现有会话，显式部署新增框架文件到远端，并记录 `artifacts/setup/DEPLOYMENT.json`。原有研究计划、AGENTS、预注册和预留二进制不被部署脚本覆盖。

后续编辑应先统一实际Mutagen源目录。不要创建两个指向同一远端目录的活动双向会话。环境、模型缓存、大型输出和进程锁不应进入源代码同步；环境/缓存使用现有已忽略的 `.venv`、`.cache`。研究worker锁固定留在远端 `/tmp`，不可同步替换或删除。正式运行期间不要同步修改代码，运行manifest中的source hash用于复核版本。

当前目录无Git提交时，manifest明确记录 `git_commit=null`、`git_diff=null` 和源文件SHA256；不会伪造commit。研究结论必须来自真实输出，不能以dry-run、数据gold或随机小模型单测代替实测。
