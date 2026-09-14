# Research execution contract

本仓库用于 MiniCPM5 的拒绝编辑与决策机制研究。先读 RESEARCH_PLAN.md、PREREGISTRATION.yaml 和 SOURCES.json。

## 当前任务范围

仅按 T00–T04 开始：只读资源/授权审计；锁定模型与模板；实现合成数据和 gold verifier；测试 hooks；小样本 pilot。其余阶段必须满足计划中的阶段门。这里列出的 scripts 是待实现的接口，不代表已有可运行实验框架。

## 资源与权限

- 2026-09-10 已由服务器管理员在本研究线程中明确授权 GPU 3 为主卡、GPU 5 为备用卡，并授权两卡分别常驻预留 32 GiB；GPU 3 固定使用 UUID `GPU-e5c246b7-afc2-cccd-e66d-fa1ca4eb089e`，GPU 5 固定使用 UUID `GPU-500c112e-cdd9-4e0d-d709-63de81493d96`。授权持续至管理员明确撤销；每次进程启动仍须记录现场资源审计。
- 默认禁止 GPU 0/1/2/4/6/7。GPU 5 上已有 SenseVoice 等进程，不得终止、重配或干扰；其预留必须独立通过实时显存门槛。
- 不终止任何现有进程，包括用户自己的 SenseVoice；不改生产环境、驱动、MPS、MIG、SGLang/vLLM 服务。
- 最多一个正式实验 GPU worker；允许 GPU 3、GPU 5 各一个常驻预留进程。每卡初始 32 GiB 作业或预留预算、12 GiB 全卡余量。管理员直接授权视为每卡 32 GiB 项目额度；启动仍要求对应卡实时空闲显存至少为预算加余量。
- 不自动换卡、不自动多卡实验、不为吞吐启动额外实验 workers。两个预留进程不构成多卡实验；正式 run 仍只绑定一个已授权 UUID，且不得静默合并两卡结果。调度器环境不自行覆盖。
- 不长期缓存全 token 激活，不把大缓存写入共享 /dev/shm。允许在 GPU 3 和 GPU 5 上各运行一个名为 `autoplacer-RL` 的受管常驻预留进程，以实际 CUDA 分配分别保留不超过 32 GiB；每个进程必须强校验预期 UUID，并记录 PID、进程名、UUID、分配量、心跳和启停时间，不得伪装成实验计算。每小时复核全卡余量；管理员撤销、任一卡余量低于 12 GiB、进程异常或正式 worker 无法接管时，立即释放对应卡预留。禁止在同一卡多进程囤卡或超预算分配。

## 科研纪律

- 不以 H2 为目标答案。H1–H6 可以并存；REJECT 与 ABSTAIN 是不同输出。
- 模型配置、精度、模板、tool parser、版本和 tokenization 以锁定 revision 的实际文件为准；不复制报告中的猜测。
- 原始权重只读。先 runtime hooks，不先做永久权重改写、LoRA、SFT、SAE。
- 干预选择不许使用 V/T 的正式测试效应；冻结前不得查看封存 test 输出。
- 不把同一 semantic family 的 paraphrases、translations、标签交换跨 split 分配。
- 输出格式错误、截断、循环是结果，不删除、不记成弃权。
- probe、cosine、PPL、KL、工具语法正确率均不能单独证明完整机制保留。
- 不自动对目标方向回归掉“共享 component”来制造正交。
- patching 必须记录在投影前后的位置以及后续投影是否持续；禁止把取消干预当成局部修复。
- 不将跨 checkpoint 差异简单归因于 RL，不将全层运行时 postblock 投影冒充原论文完全相同的权重正交化。
- 所有模型工具动作仅在离线假数据 sandbox 执行。不接真实账户、生产数据库、邮件或用户设备。

## 每次提交的要求

报告实际执行命令、退出状态、git commit/diff、run manifest、原始输出位置、测试结果与未解决项。环境失败、阴性结果和假说不成立不得隐藏。没有实际 GPU 执行时明确写“未运行”，不能生成伪造 metrics。

每张票据先实现最小可测试版本；不重写无关代码，不搭建新服务平台。代码应有类型、错误处理、单元测试和断点续跑；日志不包含密钥或个人账户信息。
