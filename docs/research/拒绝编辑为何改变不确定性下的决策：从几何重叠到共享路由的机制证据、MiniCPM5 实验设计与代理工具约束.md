# 拒绝编辑为何改变不确定性下的决策：从几何重叠到共享路由的机制证据、MiniCPM5 实验设计与代理工具约束

## 执行结论

本报告将附件中已经明确给出的研究任务——**refusal editing / abliteration、epistemic caution、verdict bias 与 agent/tool-use routing 的机制关系**——视为实际研究主题，而不再采用“主题未指定”的占位假设；附件同时要求严格区分 harmfulness、safety refusal、uncertainty、epistemic abstention、negative verdict、commitment、tool propensity、tool identity 与 tool abstention，并以 H1–H6 为竞争假设而非预设结论。fileciteturn0file0

截至 **2026 年 9 月 9 日**，最稳健的总体结论是：**现有文献并没有证明“abliteration 导致 verdict bias，是因为 r_refusal 与 r_epistemic-caution 直接几何重叠”**。Arditi et al. 在 13 个开源聊天模型上证明，某个低维 residual-stream 方向对其所测量的安全拒绝行为具有相当强的因果控制力：删除它可抑制拒绝，加入它可诱导拒绝，并可将该投影写入权重；这足以支持“该方向介导了所测拒绝行为”的 Level 3 结论，却**不能证明 difference-of-means 向量就是纯粹、唯一、语义原子的 refusal variable**。该向量来自 harmful 与 harmless prompt 激活均值之差，而原始数据使用 AdvBench、MaliciousInstruct、TDC/HarmBench 对比 Alpaca 等 harmless 数据，因此 topic、语体、风险、否定、谨慎程度等任何系统性差异理论上都可进入该对比方向。[\[1\]](https://papers.neurips.cc/paper_files/paper/2024/hash/f545448535dfde4f9786555403ab7c49-Abstract-Conference.html)

后续工作事实上削弱了“纯一维 refusal essence”的解释。2025–2026 年关于 refusal geometry 的研究发现，多种拒绝类型可以对应相互区分的方向或多维 “concept cones”；更关键的是，**几何正交并不意味着干预独立**。另一项 2026 年研究则发现 11 类 refusal/non-compliance 的方向彼此可以明显不同，但沿不同方向 steering 往往产生近似相同的 refusal–over-refusal 行为权衡——这恰好符合“多个上游表示，汇入某种更共享的行为控制机制”的可能性，但还没有把这个共享机制定位成一个经过充分 necessity/sufficiency 验证的 circuit。[\[2\]](https://arxiv.org/abs/2502.17420)

最重要的新证据来自两条彼此补充的文献线。第一，**harm detection 与 refusal execution 可以被分离**：Zhao et al. 发现 harmfulness representation 与 refusal representation 可分别被 steering；某些 jailbreak 或安全移除条件下，模型仍可保留 harmfulness 表示却不再执行拒绝。第二，Son et al. 2026 年的 *A Unified Mechanistic Analysis of Knowledge- and Safety-Based Refusals* 使用 213 个 topic/format 匹配的四元组，在 Llama、Qwen、Gemma 三个家族及其 refusal-tuned 版本上发现 knowledge-refusal 与 safety-refusal 的对比方向在早中层高度对齐，峰值 cosine 为 **0.699–0.794**，共同分量投影范数约 **0.92–0.95**，但仍存在约 **0.32–0.39** 的 type-specific residual；晚层才更明显分化为 uncertainty/knowledge 与 safety/policy 语义。作者称之为 **commit-then-specify**。[\[3\]](https://arxiv.org/abs/2507.11878)

但这里有一个决定性的构念问题：Son et al. 比较的是 **knowledge-based refusal versus answerable control** 与 **safety-based refusal versus safe control**。也就是说，其高重叠部分很可能至少部分反映“**已经决定不回答/拒绝**”这个共同的行为状态；它并不是纯粹的 r_uncertainty，更不是用户定义的广义 r_caution。因此，该结果支持“安全拒绝和知识拒绝共享某种 refusal-commitment structure”，却不能直接支持

$`r_{safety - refusal} \approx r_{epistemic - caution}.`$

而且作者自己明确指出，几何 residual decomposition 不必对应独立因果机制；共同 head 的 ablation/patching 可以改变共同投影，但论文也明确说这尚未构成完整的 causal circuit。[\[4\]](https://arxiv.org/html/2609.00760)

与此同时，安全电路研究已经越来越直接地支持 **detect → route → generate** 而不是“检测本身就是拒绝”。*How Alignment Routes* 报告了中间层 attention gate、下游 amplifier 等结构，并进行了 interchange/knockout 式因果实验；*Detection Is Cheap, Routing Is Learned* 也显示 probe 可检测到某些受控内容，而行为是否被阻断取决于后续 routing；最新的 *From Detection to Refusal* 则进一步描述 harmful detection heads → safety neurons → refusal heads 的级联关系。它们对 **H2 的结构形式**提供了强先验：上游语义检测与下游行为执行确实可以分离。但目前这些工作研究的是 safety routing，并没有证明 epistemic uncertainty、negative verdict 或 tool abstention 使用同一个 route。[\[5\]](https://arxiv.org/abs/2603.18280)

关于 **verdict bias 本身**，证据目前仍主要是 Level 0。Fafuła 的预注册研究在一个完全不触发安全拒绝的、21,600 次不确定决策数据集中比较两个 MoE 家族的 base 与 abliterated 版本；两家族都出现更乐观的判定倾向（Gemma +12.2 个百分点、Qwen +7.4 个百分点）、更长的理由，以及 forced self-critique 中更少的显式 uncertainty language，而表达 confidence 的变化在两个家族中方向相反。这非常有力地说明“refusal removal 可以改变非安全领域的 decision disposition”，但论文没有定位出造成这一变化的表示或电路。[\[6\]](https://arxiv.org/abs/2607.17427) clearbluejar 的安全研究技术博客则提供了非常具有诊断价值但非同行评审的案例：abliterated 模型在 reasoning 中正确识别边界保护，却最终给出 CONFIRMED，且部分 abliterated checkpoint 将更多候选提升为肯定 verdict；博客提出“skepticism 被一起拿掉”的解释，但这一点仍只是机制假说。[\[7\]](https://clearbluejar.github.io/posts/does-abliteration-skew-your-bug-hunting/)

工具使用文献又提供了第二个关键类比。2026 年 *Tool Calling is Linearly Readable and Steerable in Language Models* 发现“**选哪个工具**”具有低维可读、可 steer 的结构，并通过 activation patching 找到少量中晚层 attention heads；而 *Tunable Tool-Call Rates in LLM Agents via Representation Steering* 则表明“**要不要调用工具**”本身可以被另一个近似单维的方向连续调节，而且这种调节能够跨未见工具泛化，而不只是改变具体 tool identity。与此同时，AgentAbstain、ToolSandbox、τ-bench 和 BFCL 等基准表明“知道该用哪个工具”和“知道什么时候不应行动”不是同一个能力。[\[8\]](https://arxiv.org/abs/2605.07990)

**因此，本报告的当前证据排序为：H2 \> H5 \> H6 \> H3 \> H4 \> H1。** 这是基于现有文献的综合推断，而不是已有论文已经证明的排序。H2“上游 distinct、下游共享 commitment/action-routing”的解释目前最能同时容纳 harmfulness/refusal separation、knowledge/safety shared-refusal structure、detect-route-generate 安全电路以及“reasoning 已发现问题但最终仍肯定”的 verdict-bias 案例；H5“dirty contrastive direction/data confound”有 SRA 与 Arditi 数据设计的直接支持；H6“distributed nonlinear circuit”则是必须保留的强备择。反而 H1 是目前**最需要实验、而不是最有证据**的假说。[\[9\]](https://arxiv.org/abs/2601.08489)

最强、仍明显可发表的研究空白可以精确表述为：

> **拒绝编辑改变不确定性下的决策校准，究竟是因为编辑直接删除了 epistemic-caution representation，还是因为 harm 与 uncertainty 的上游表示保持分离，而编辑损伤了它们通向 reject/abstain/action-restraint 的共享下游路由？该下游路由是否进一步参与 tool-call abstention 与 irreversible-action confirmation？**

在本次截至 2026 年 9 月 9 日针对 arXiv、ACL Anthology、会议论文、相关技术报告与基准的检索中，我没有找到一项 primary study 同时完成“**同一模型上的 refusal edit + matched uncertainty/verdict/tool-abstention dataset + post-edit uncertainty decoding + cross-condition causal patching/localization**”。最接近的论文分别只覆盖了这个链条的一部分。[\[10\]](https://arxiv.org/abs/2607.17427)

## 方法论、构念与证据等级

**检索方法。** 本次检索以用户附件给出的 seed papers 和 H1–H6 为起点，优先追踪 2024–2026 年原始 arXiv/会议论文、ACL Anthology、NeurIPS 页面、官方模型卡与作者技术材料；检索时刻意将 "refusal direction", "harmfulness representation", "knowledge refusal", "epistemic abstention", "activation patching", "policy routing", "tool calling representation", "tool abstention" 等拆开搜索，避免把“refusal”当作单一关键词构念。对于 verdict bias 与社区 abliteration，仅将技术博客/仓库作为生态或假说来源，不把它们提升为同行评审机制证据。Arditi 的正式发表状态为 NeurIPS 2024；大量 2026 年工作仍应按 preprint/最新技术报告解读。[\[11\]](https://papers.neurips.cc/paper_files/paper/2024/hash/f545448535dfde4f9786555403ab7c49-Abstract-Conference.html)

### 构念必须在实验中分开操作化

| 构念 | 本报告中的定义 | 最低限度的独立测量 | 不能与什么混同 |
|:---|----|----|----|
| harm detection | 模型表示请求/内容具有 harmful、policy-sensitive 特性 | matched harmful/benign probe；steering/patching | safety refusal |
| safety refusal | 因安全或政策约束而决定 refuse/safe-complete/redirect | 行为标签 + refusal-specific activation | harmfulness |
| epistemic uncertainty | 对答案真实性、证据充分性或可知性的内部不确定表示 | answerable/unanswerable matched probe；confidence-independent decoding | “I don't know” token |
| epistemic abstention | 因知识不足而选择不作答 | answer/abstain decision | uncertainty 本身 |
| epistemic caution | 对证据阈值、反例、冲突证据及过度承诺的广义敏感度 | incomplete/conflicting evidence tasks；selective-risk metrics | 单纯 abstention |
| negative verdict | 对假说作 REJECT/NO/INVALID 判断 | CONFIRM/REJECT/ABSTAIN 三分类 | uncertainty；可高置信拒绝 |
| commitment | 由证据状态到“采取/不采取某一结论或行动”的潜在路由变量 | 跨任务 reduced-rank subspace；不能先验一维 | positive verdict |
| tool propensity | call tool vs answer internally | required/optional/no-tool matched pairs | tool identity |
| tool selection | 已决定调用后选哪个 tool | conditional-on-call accuracy | whether-to-call |
| tool abstention | 工具存在但当前不应调用 | irrelevant / insufficient info / needs confirmation / unsafe action pairs | tool incompetence |

现有研究本身已经证明，把这些构念混起来会造成解释错误：harmfulness 与 refusal 可被分离；knowledge-refusal 与 safety-refusal 有共享分量但晚层依据不同；工具 identity 与工具 propensity 也可以分别控制。[\[12\]](https://arxiv.org/abs/2507.11878)

### 因果证据等级

| 等级 | 可接受证据 | 可以声称 | 不可以声称 |
|:---|----|----|----|
| **Level 0** | 行为差异、相关性 | “编辑后行为改变” | 内部机制 |
| **Level 1** | linear probe / decodability | “信息线性可读” | 该方向被模型使用 |
| **Level 2** | cosine、principal angles、CCA、feature overlap | “表示几何相关/分离” | 因果共享 |
| **Level 3** | activation addition、ablation、weight edit | “该表示对行为有因果影响/具有一定充分性或必要性” | 这是唯一机制 |
| **Level 4** | matched activation patching、causal interchange、path intervention | “某组件在对比条件之间介导因果效应” | 普适电路，除非多模型复制 |
| **Level 5** | 定位到 circuit，并跨干预、数据、模型完成必要性+充分性复制 | “在研究范围内存在共享因果电路” | 超出所测模型/任务的普适结论 |

按这个标准，Arditi 对 refusal-direction 的核心行为控制可评为 **Level 3**；Son et al. 的 shared KR/SR 结论主体是 Level 2，steering/head-ablation 部分提升到 Level 3，部分 head patching 具有 Level 4 的成分，但作者自己明确说共同 heads 尚不足以构成完整电路；*How Alignment Routes* 的 gate interchange/knockout 是本研究相关文献中最接近 Level 4 的安全-routing 证据。当前没有 Level 5 证据证明 safety refusal、epistemic caution、negative verdict 和 tool abstention 共用同一 circuit。[\[13\]](https://arxiv.org/abs/2406.11717)

### 推荐的检索工具与策略

| 工具/数据库 | 主要用途 | 使用要点 | 检索示例 |
|:---|----|----|----|
| **arXiv** | 最新机制论文、技术报告 | 按提交/修订日期记录版本；不能把 preprint 自动当 peer-reviewed | "refusal direction" AND uncertainty AND (patching OR ablation) |
| **OpenReview** | ICLR/NeurIPS workshop 等投稿与评议 | 检查 accepted/rejected、revision、reviewer objection | "refusal" mechanistic interpretability abstention |
| **ACL Anthology** | ACL/EMNLP/NAACL 正式论文 | 优先用于 tool/agent/NLP benchmark 状态核验 | "tool abstention", "insufficient information" tool |
| **NeurIPS/ICML proceedings** | 正式会议版 | 将 arXiv 与 camera-ready 分开记录 | "refusal direction" |
| **Semantic Scholar / Google Scholar** | forward/backward citation | 以 Arditi、Unified、Tool Calling 三篇为 citation hubs；重新回到 primary source 阅读 | "cites 2406.11717 refusal" |
| **Hugging Face** | checkpoint、tokenizer、chat template、模型卡 | 固定 exact revision SHA；不要仅抄社区 checkpoint 描述 | openbmb/MiniCPM5-2B, tokenizer/config |
| **GitHub** | 论文代码、Heretic/投影式 abliteration 实现 | commit hash、dependency lock、默认 prompt/template 都应记录 | abliteration biprojected residual stream |
| **Zenodo / OSF** | 数据、预注册、artifact | 检查 dataset hash 和 preregistered endpoints | verdict-bias dataset |
| **CNKI / 万方** | 中文综述、政策/产业背景 | 不宜用来替代英文原始机制论文 | 大语言模型 拒绝机制 可解释性 不确定性 |
| **中国信通院、网信办等官方资料库** | 治理/行业风险维度 | 用于 agent action restraint 的政策背景，不作为神经机制证据 | 生成式人工智能 工具调用 风险 决策 |

更有效的英文查询不是 refusal uncertainty 一个字符串，而是分别搜索：

("harmfulness" AND refusal AND steering)\
("knowledge refusal" AND "safety refusal")\
("epistemic abstention" AND representation)\
("activation patching" AND refusal)\
("tool calling" AND representation AND steerable)\
("tool abstention" OR "unnecessary tool use" OR "know when not to act")

中文则可使用 拒绝方向 + 不确定性 + 激活补丁、安全拒绝 + 知识拒绝 + 机制、工具调用 + 表示空间 + 干预、代理 + 行动克制 + 弃权，但该主题目前最关键的 primary mechanistic literature 仍主要是英文资料。

## 文献地图与研究方向优先级

### 研究方向矩阵

下表把附件中的核心问题扩展为九个互补工作包，同时覆盖学术、技术、方法论、代理系统、行业、政策、历史、跨学科与市场/生态维度。高优先级部分是论文主线；中低优先级部分主要用于增强外部效度，不能让它们挤占机制实验资源。

| 方向 | 维度 | 研究价值与核心问题 | 数据/资料来源 | 中文 / 英文检索词 | 优先级与理由 | 预期产出 |
|:---|----|----|----|----|----|----|
| **拒绝—谨慎的直接重叠检验** | 学术 | 直接检验 H1，而不是从行为猜测 | matched safety、uncertainty、verdict activations | 拒绝方向 不确定性 谨慎 / refusal direction epistemic caution uncertainty | **高**：最直接回答主问题 | layerwise geometry、cross-ablation、H1 可证伪结果 |
| **共享 commitment/routing circuit** | 技术/机制 | 检验 H2：uncertainty 是否保留，但其到 reject 的因果通路损坏 | matched causal pairs、head/MLP activations | 行为路由 激活补丁 / decision routing activation patching refusal | **高**：最有潜在原创性 | downstream gate/circuit 候选与 causal mediation |
| **contrastive dataset contamination** | 方法论 | 判定 dirty vector 是否主要来自 harmful/harmless semantic mismatch | 原始 Arditi 数据、minimal pairs、factorial datasets | 拒绝向量 数据混杂 / refusal vector dataset confound matched pairs | **高**：H5 已有直接先验 | 三种 extraction recipe 的 side-effect comparison |
| **tool propensity / abstention / confirmation** | Agent | 检验 route 是否扩展到“是否行动” | BFCL、AgentAbstain、ToolSandbox、τ-bench 派生数据 | 工具弃权 行动克制 / tool abstention action restraint confirmation | **高**：决定论文是否能从 chat 扩展到 agent | tool-call competence/restraint effect matrix |
| **MiniCPM5 post-training mechanism** | 模型工程 | 比较 Base→SFT→RL/OPD 后 route 如何形成 | MiniCPM5 Base/SFT/final checkpoints | MiniCPM5 工具调用 拒绝 / MiniCPM5 refusal tool calling | **高**：直接服务目标 checkpoint | post-training causal comparison |
| **uncensored checkpoint deployment QA** | 行业 | MMLU/KL 不变是否仍隐藏决策 disposition drift | 社区 abliterated checkpoints、部署日志 | 无审查模型 决策偏差 / uncensored model decision bias agent reliability | **中**：外部效度高，provenance 风险大 | agent-preservation QA protocol |
| **不可逆行动与治理阈值** | 政策 | 从“安全拒绝”拓展到“何时必须确认/升级” | AgentAbstain、SafeToolBench、政策文件 | 不可逆行动 确认 AI代理 / irreversible action confirmation LLM agent | **中**：实际部署意义高，非机制主线 | policy-sensitive restraint taxonomy |
| **2024–2026 refusal 概念演进** | 历史/科学史 | 追踪 single direction → subspace → routing circuits | citation graph | 拒绝机制 演进 / refusal direction subspace routing history | **中**：有助论文 framing | 系统综述/概念史章节 |
| **open-weight editing 生态与市场** | 市场/生态 | 不同“uncensored” recipe 是否产生可预测 agent 风险 | HF/GitHub 社区模型、下载生态 | abliterated model ecosystem | **低**：社区 provenance 高度混杂 | 生态观察，不作为核心因果证据 |

Fafuła 的研究已经证明社区模型研究中特别需要重视 provenance：其审计实际发现过错误 quantizer 配对和陈旧 chat template 导致的污染，因此“同型号 base vs uncensored”远远不足以构成干净实验。[\[6\]](https://arxiv.org/abs/2607.17427)

### 关键机制文献与初步资料清单

下面的表同时承担用户要求的“每个高优先级方向至少五条来源”的 source pack。A=拒绝/判决副作用，B=安全—认识论共享机制，C=因果定位，D=工具路由/克制，E=MiniCPM5 与实验工具。部分论文属于多个方向。

| 方向 | Work | 作者/机构；年份/状态 | Model(s) / Construct | Representation / Intervention | 证据级 | 为什么重要；主要限制 | 获取 |
|:---|----|----|----|----|----|----|----|
| A/B | **Refusal in Language Models Is Mediated by a Single Direction** | Arditi et al.; 2024, NeurIPS | 13 open chat models；safety refusal | harmful−harmless mean direction；addition、directional ablation、weight orthogonalization | **L3** | 奠定 abliteration；但 contrast 数据本身不能保证方向纯度 | NeurIPS/arXiv [\[1\]](https://papers.neurips.cc/paper_files/paper/2024/hash/f545448535dfde4f9786555403ab7c49-Abstract-Conference.html) |
| A | **Refusal in LLMs is an Affine Function** | Thomas Marshall, Adam Scherlis, Nora Belrose; 2024 arXiv | 10 models；refusal | affine subspace projection + addition | **L3** | 说明单向量不是唯一合理参数化；仍主要看 refusal behavior | arXiv [\[14\]](https://arxiv.org/abs/2411.09003) |
| A/B | **The Geometry of Refusal in Large Language Models: Concept Cones and Representational Independence** | 2025，2026 修订；arXiv | refusal geometry | 多方向/concept-cone geometry 与 intervention independence | **L2–3** | 明确警告 orthogonality ≠ intervention independence | arXiv [\[15\]](https://arxiv.org/abs/2502.17420) |
| A/B | **There Is More to Refusal in Large Language Models than a Single Direction** | 2026 arXiv | 11 类 refusal/non-compliance | category directions + steering | **L2–3** | 多个几何方向却有相似行为控制效应；非常符合“上游多样、下游共享” | arXiv [\[16\]](https://arxiv.org/abs/2602.02132) |
| A | **Surgical Refusal Ablation: Disentangling Safety from Intelligence via Concept-Guided Spectral Cleaning** | Tony Cristofano; 2026 arXiv | Qwen3-VL、Ministral 等 | Concept Atoms；ridge spectral residualization；rank-one edit | **L2–3** | 直接证明 raw direction 可 polysemantic；但保护的是 capability/style proxy，不是 agent restraint | arXiv [\[17\]](https://arxiv.org/abs/2601.08489) |
| A | **Abliteration Is Not a Scalpel** | Aleksander Fafuła; 2026-07-19 arXiv，预注册 | Gemma/Qwen MoE；decision disposition | base vs abliterated behavioral comparison | **L0** | 最强受控 off-target 证据；没有 mechanism localization | arXiv [\[6\]](https://arxiv.org/abs/2607.17427) |
| A | **Don’t Let Abliteration Abliterate Your Bug Hunting** | clearbluejar; 2026-09-01 技术博客 | Gemma/Qwen 社区 builds；verdict bias | security triage behavior | **L0** | reasoning–verdict 矛盾案例极具诊断意义；非同行评审、样本与 checkpoint provenance 有限 | 原作者博客 [\[7\]](https://clearbluejar.github.io/posts/does-abliteration-skew-your-bug-hunting/) |
| B/C | **LLMs Encode Harmfulness and Refusal Separately** | Jiachen Zhao et al.; 2025 arXiv | 多个 chat LLM；harm vs refusal | distinct directions、steering | **L3** | 最直接支持 detection ≠ refusal execution | arXiv [\[18\]](https://arxiv.org/abs/2507.11878) |
| B/C | **A Unified Mechanistic Analysis of Knowledge- and Safety-Based Refusals** | Yuri Son et al.; 2026-09-01 arXiv | Llama/Qwen/Gemma × base+tuned；KR/SR | matched quadruples、geometry、probes、steering、head/MLP ablation/patch | **L2–4** | 目前最接近“shared commitment then specialization”；但 KR ≠ pure uncertainty | arXiv [\[19\]](https://arxiv.org/html/2609.00760) |
| B/C | **Detection Is Cheap, Routing Is Learned** | Gregory N. Frank; 2026 arXiv | 9 open-weight models；policy detection/routing | probes + surgical ablations | **L1–3** | probe 能检测不代表策略会执行；支持 routing frame | arXiv [\[20\]](https://arxiv.org/abs/2603.18280) |
| B/C | **How Alignment Routes: Localizing, Scaling, and Controlling Policy Circuits in Language Models** | Gregory N. Frank; 2026 arXiv | 多家模型；policy circuit | attention gate、amplifiers、interchange、knockout | **L4** | 对 H2 最有价值的 safety-circuit 类比；尚未连接 epistemic/tool | arXiv [\[21\]](https://arxiv.org/abs/2604.04385) |
| B/C | **From Detection to Refusal: Safer LLMs via Circuit-Guided Weight Scaling** | 2026-08-30 arXiv | 六个 LLM；safety circuit | detection heads→safety neurons→refusal heads；targeted interventions | **L3–4** | 提供级联安全电路证据；不等于 generic commitment circuit | arXiv [\[22\]](https://arxiv.org/abs/2609.00051) |
| C | **What Drives Representation Steering? A Mechanistic Case Study on Steering Refusal** | Stephen Cheng, Sarah Wiegreffe, Dinesh Manocha; 2026 | 两个 model families；steering mechanism | multi-token activation patching、OV/QK decomposition | **L4** | 有助判断 steering vector 究竟通过哪些 attention pathways 生效 | arXiv [\[23\]](https://arxiv.org/abs/2604.08524) |
| C | **Beyond a Single Direction: Chain-of-Thought Disrupts Simple Steering of Refusal** | Kia-Jüng Yang et al.; 2026 | DeepSeek-R1-Distill-LLaMA-8B；CoT/refusal | steering with fixed/regenerated CoT | **L3** | 说明显式 reasoning trajectory 本身会重构行为状态；对 MiniCPM thinking mode 很重要 | arXiv [\[24\]](https://arxiv.org/abs/2605.26772) |
| D | **Tool Calling is Linearly Readable and Steerable in Language Models** | Wu et al.; 2026 | Gemma/Qwen/Llama，270M–27B；tool identity | linear readout、mean-diff steering、activation patching | **L3–4** | 证明 tool identity 有低维机制；multi-turn 泛化有限 | arXiv [\[25\]](https://arxiv.org/abs/2605.07990) |
| D | **Tunable Tool-Call Rates in LLM Agents via Representation Steering** | Chen et al.; 2026 | dense/MoE/multimodal；whether-to-call | tool-call propensity direction、bidirectional steering | **L3** | 显示 tool propensity 与 identity 可以分开 | arXiv [\[26\]](https://arxiv.org/abs/2608.25198) |
| D | **AgentAbstain: Do LLM Agents Know When Not to Act?** | Xun Liu et al.; 2026 | 17 models、42 sandboxes；action abstention | 263 paired should-act/should-abstain tasks | **L0** | 最直接的 agent restraint benchmark；不研究内部机制 | arXiv [\[27\]](https://arxiv.org/abs/2607.10059) |
| D | **Berkeley Function Calling Leaderboard** | Patil et al.; ICML 2025；V4 ongoing | function calling / relevance | AST、execution、multi-turn/agentic eval | **L0** | 包含 function relevance，但总体分数不能替代 restraint 测试 | 官方 BFCL [\[28\]](https://gorilla.cs.berkeley.edu/blogs/8_berkeley_function_calling_leaderboard.html) |
| D | **τ-bench** | Shunyu Yao et al.; 2024 arXiv | interactive agents；policy/tool use | user-agent-tool environment、database end state | **L0** | 测多轮规则遵循，比单次 tool name accuracy 更接近 agent routing | arXiv [\[29\]](https://arxiv.org/abs/2406.12045) |
| D | **ToolSandbox** | Lu et al.; NAACL Findings 2025 | conversational tool agents | stateful benchmark；insufficient information 等 | **L0** | 可用于构造“不应调用/先澄清”控制条件 | ACL Anthology [\[30\]](https://aclanthology.org/2025.findings-naacl.65/) |
| D | **ToolFailBench** | 2026 arXiv | tool agents | Tool-Skip、Result-Ignore、Unnecessary-Tool-Use 等 | **L0** | 避免 aggregate tool success 掩盖 unnecessary calls | arXiv [\[31\]](https://arxiv.org/abs/2607.04686) |
| D | **SafeToolBench** | Xia et al.; Findings EMNLP 2025 | safe tool use | malicious instruction/tool/joint risk benchmark | **L0** | 给 action restraint 提供 safety 侧外部效度 | ACL Anthology [\[32\]](https://aclanthology.org/2025.findings-emnlp.958/) |
| E | **MiniCPM5-2B** | OpenBMB; 2026-09 最新官方模型卡 | 2.52B total，42 layers，standard LlamaForCausalLM | final post-trained BF16 checkpoint | — | 最合适主模型；原生 tool/agent 能力、规模适合全层 intervention | Hugging Face official [\[33\]](https://huggingface.co/openbmb/MiniCPM5-2B) |
| E | **MiniCPM5-2B-SFT** | OpenBMB; 2026 | SFT checkpoint | pre-RL/OPD mechanistic control | — | 可区分 SFT 与后续 post-training 对 route 的贡献 | Hugging Face official [\[34\]](https://huggingface.co/openbmb/MiniCPM5-2B-SFT) |
| E | **MiniCPM5-2B-Base** | OpenBMB; 2026 | base checkpoint | pre-instruction control | — | 用于判断 route 是否由 post-training 写入 | Hugging Face official [\[35\]](https://huggingface.co/openbmb/MiniCPM5-2B-Base) |
| E | **NNsight** | NDIF/Northeastern ecosystem | any PyTorch model | arbitrary activation read/write、cross-prompt patching | — | 当前最直接的 MiniCPM5 intervention 工具首选 | 官方文档 [\[36\]](https://nnsight.net/index.html) |
| E | **TransformerLens model bridge** | TransformerLens | Llama 等 50+ architecture families | canonical residual/head/MLP hooks | — | MiniCPM5 是 LlamaForCausalLM，因此很可能可经 bridge 使用，但必须对 exact revision 做验证 | 官方文档 [\[37\]](https://transformerlensorg.github.io/TransformerLens/content/getting_started.html) |
| E | **pyvene** | Wu et al./Stanford NLP; NAACL Demo 2024 | arbitrary PyTorch models | composable interventions | — | 适合 interchange/intervention specification；可作为 NNsight 的独立复现路径 | 官方文档 [\[38\]](https://stanfordnlp.github.io/pyvene/) |

### 对 SRA / projected / biprojected 方法的关键解读

SRA 特别值得注意，因为它实际上验证了本研究最重要的方法论担忧之一。其 raw direction 定义仍是

$`r_{\ell}^{dirty} = \mu_{\ell}(D_{harm}) - \mu_{\ell}(D_{safe}),`$

随后构造 Concept Atoms，并用 ridge regression 从 raw vector 中残差化 Shield + Confound span：

$`\widehat{w} = arg\min_{w} \parallel r_{dirty} - A_{SC}w \parallel^{2} + \lambda \parallel w \parallel^{2},`$

$`\widetilde{r} = r_{dirty} - A_{SC}\widehat{w}.`$

它在五个 Qwen3-VL/Ministral 模型上显著降低了 PPL/KL drift，同时保持很低的拒绝率；作者自己也明确提醒 proxy drift metrics 不能替代 comprehensive behavioral evaluation。[\[17\]](https://arxiv.org/abs/2601.08489)

更值得关注的是：**SRA 论文把 epistemic uncertainty 列在 refusal-relevant Target atoms 中，而不是 protected Shields 中。** 它的 iterative analysis 甚至报告，在早期 refusal/deception 成分消退后，后续 pass 中 epistemic uncertainty 会成为较显著成分。也就是说，SRA 原版并不是“显式保护 epistemic uncertainty 的 abliteration”；从你的研究目标看，它反而提供了一个很好的警告：一个号称更 surgical 的编辑若把 uncertainty 当作 refusal target，也可能仍然损伤你最想保护的行为。[\[17\]](https://arxiv.org/abs/2601.08489)

Projected/Biprojected/Norm-Preserving Biprojected Abliteration 与 Heretic 在社区工程上尝试通过对 harmless mean 的正交化、双投影、范数保持或 KL 优化来降低模型漂移，但这些目标主要约束**总体分布接近程度或 harmless behavior**；它们并不自动建立

$`S_{uncertainty},\, S_{negative - verdict},\, S_{tool - abstention}`$

等显式 protected spaces。Heretic 本身也是自动优化 directional ablation 权重、以 refusal 与 KL 等指标作为目标的社区工程工具，而不是验证共享 decision circuit 的论文证据。[\[39\]](https://github.com/izikeros/heretic)

因此：

$`small\ KL\mspace{6mu}\  \Rightarrow \not{}\ \mspace{6mu} preserved\ epistemic\ routing`$

以及

$`unchanged\ BFCL\ aggregate\mspace{6mu}\  \Rightarrow \not{}\ \mspace{6mu} preserved\ tool\ abstention.`$

Fafuła 的 side-effect 结果和 AgentAbstain 的独立性发现尤其说明，普通 capability/distribution 指标可以遗漏 disposition 与 action-restraint 变化。[\[40\]](https://arxiv.org/abs/2607.17427)

## 文献矛盾、最佳机制模型与假设排序

### 为什么“共享”和“正交”并不真正矛盾

文献中的表面冲突大多来自**比较的不是同一构念**。

最典型的两种实验分别在问：

$`harmful\ content\quad vs\quad benign\ content`$

和

$`refuse\quad vs\quad answer.`$

Zhao et al. 的“harmfulness 与 refusal 可分离”完全可以与 Son et al. 的“knowledge-refusal 与 safety-refusal 有大共享分量”同时成立：前者强调**上游 trigger representation ≠ downstream policy execution**；后者比较的两个条件本来都以 refusal behavior 为共同终点。[\[41\]](https://arxiv.org/abs/2507.11878)

同理，“multiple refusal directions are geometrically distinct”与“不同 refusal steering directions 产生近似相同 refusal/over-refusal trade-off”也不矛盾。这恰恰意味着：

$`representation\ identity \neq behavioral\ control\ equivalence.`$

不同上游方向可能经不同路径驱动同一个或相互替代的 downstream controller；反过来，即使 cosine 很低，删除某一方向仍可能通过非线性网络影响另一个行为。这也是 concept-cone / representational-independence 工作明确提出的警告。[\[42\]](https://arxiv.org/abs/2602.02132)

导致研究结果不可直接比较的六个主要因素是：

| 因素 | 会怎样制造“矛盾” |
|:---|----|
| **方向定义** | harmful−harmless、refuse−answer、uncertain−certain 测到的不是同一变量 |
| **数据匹配程度** | Alpaca vs harmful corpus 会混入 topic/style；minimal pairs 大幅减少这种污染 |
| **token position** | final prompt token、整个 span mean、first generation token 可能处于不同计算阶段 |
| **layer choice** | Son et al. 的共享峰值在 relative depth 0.25–0.50，而 type-specific specialization 在高层更明显 |
| **chat/thinking template** | CoT 可以参与重建 refusal state；错误 template 甚至能伪造 checkpoint 差异 |
| **behavior label** | “refusal”“abstention”“negative verdict”“not calling tool”若用同一二元标签，会把不同原因压成同一类 |

这些因素都有直接文献依据。[\[43\]](https://arxiv.org/html/2609.00760)

### 当前最可辩护的机制模型

我认为目前最合理的模型不是“一个万能 refusal vector”，也还不能说已有证据证明“一个万能 commitment neuron”。更谨慎的综合模型是：

|  |
|:--:|
| <img src="拒绝编辑为何改变不确定性下的决策：从几何重叠到共享路由的机制证据、MiniCPM5 实验设计与代理工具约束_media/media/image2.png" style="width:5.83333in;height:3.9429in" alt="Rendered Mermaid diagram 1" /> |

图中的实线部分对应目前较直接的独立证据：harmfulness 与 refusal 可分开、safety policy routing 可定位、tool propensity 与 tool identity 可区分；虚线部分正是仍未解决的论文级假说——是否存在跨 epistemic verdict、refusal 与 tool restraint 的共享 downstream route。[\[44\]](https://arxiv.org/abs/2507.11878)

这个模型比简单 H1 更好地解释 clearbluejar 的典型现象：

> 内部 reasoning 已经表示“存在边界检查，因此假说不成立”，\
> 但最后仍输出 CONFIRMED。

若 H2 成立，那么失效的不是“是否看见 counterexample”，而是

$`counterexample\ /\ uncertainty \rightarrow reject\ /\ abstain`$

的转化权重。该解释与博客现象高度一致，但博客本身无法证明它。[\[7\]](https://clearbluejar.github.io/posts/does-abliteration-skew-your-bug-hunting/)

### H1–H6 当前排序

| 排名 | 假说 | 支持证据 | 反证/限制 | 最关键缺失实验 | 区分性预测 |
|:---|----|----|----|----|----|
| **首位：H2** | distinct upstream → shared downstream commitment/action route | harm/refusal separation；KR/SR shared refusal；policy routing circuits；reasoning/verdict dissociation | 尚无人直接把 uncertainty→verdict 与 safety route patch 到同一组件 | upstream uncertainty decoder + downstream patch restoration | uncertainty decoding 保留，但 patch route 可恢复 reject/abstain |
| **第二：H5** | extraction dataset 污染 | Arditi raw contrast；SRA dirty-vector 证据；不同社区 recipe side effects 不同 | matched extraction 是否消除 verdict bias 未被直接测 | raw vs topic-matched vs factorial extraction | 更干净方向显著减少 collateral verdict effect |
| **第三：H6** | distributed nonlinear circuit | multi-direction/concept-cone；CoT effects；跨模型 circuit 结构差异 | 线性方向对不少行为确实非常强 | linear failure 后 SAE/crosscoder/path tracing | linear geometry 弱，局部 feature/circuit interventions 更有解释力 |
| **第四：H3** | output-token / linguistic artifact | tool identity 工作显示一些行为 steering 与 target first-token unembedding 紧密相关 | verdict bias 同时影响 uncertainty wording 和理由长度，不像纯单 token | counterbalanced semantic labels / token permutation | 换标签或中间 representation scoring 后 bias 大幅消失 |
| **第五：H4** | generic assertiveness / agreeableness | Fafuła optimism；博客 flattery/affirmation shift | 缺少 sycophancy/assertiveness 与 edit 强度的系统共变研究 | neutral social-agreement controls | 在无不确定推理的赞同任务中也同向偏移 |
| **第六：H1** | direct refusal–caution geometric overlap | KR/SR shared refusal 可提供间接先验；SRA raw vector 确含 uncertainty-related structure | KR refusal ≠ uncertainty；没有 direct caution/refusal geometry + causal cross-ablation study | matched r_refusal 与 S_caution geometry + cross-ablation | 高 projection fraction；refusal ablation 当场降低 uncertainty/caution decoding |

H2 排首位是**最佳解释而不是既成事实**；H1 排末位也不是因为它已经被否证，而是因为其最关键的直接预测目前反而最缺数据。相关研究最多证明了“refusal-related constructs 有共享结构”，没有证明该共享结构等同于 epistemic caution。[\[45\]](https://arxiv.org/html/2609.00760)

### 最明确的研究空白

一篇强论文不应再问泛泛的“refusal 和 uncertainty 是否相关”，而应问：

> **在 refusal editing 改变最终 verdict 的样本上，模型关于 uncertainty/counterevidence 的上游信息是否仍然存在？若存在，哪一个 downstream component 导致该信息不再控制 reject/abstain？**

随后加入 agent 版本：

> **同一个 component 是否也控制“先澄清/不调用工具/等待确认”，即 action restraint？**

这两个问题恰好把 Level 1–2 的“可读/几何”推进到 Level 4–5 的“信息在哪里被行为路由使用”。

## MiniCPM5 实验设计：从最小证伪到强因果实验

### checkpoint 与架构选择

截至当前，主实验最合理的 checkpoint 是 **openbmb/MiniCPM5-2B 官方 BF16 final release**。官方模型卡显示它是 standard LlamaForCausalLM、总参数约 2.52B、非 embedding 参数约 1.98B、42 层、16 个 query heads / 2 个 KV heads、131,072 上下文，并明确针对 tool-use 与 agentic workflows 训练；模型还提供 SFT 与 Base 版本，因此形成了非常有价值的 **Base → SFT → final post-training** 机制对照链。[\[46\]](https://huggingface.co/openbmb/MiniCPM5-2B)

工具调用方面，官方说明 MiniCPM5-2B **生成 XML-style tool calls**，SGLang 的 minicpm5 parser 再把它转换成 OpenAI-compatible tool_calls；因此实验绝不能假定 Llama-3/OpenAI 风格 JSON tokenization。官方示例同时显示 chat template 接受 enable_thinking=True。[\[47\]](https://huggingface.co/openbmb/MiniCPM5-2B)

这带来三个实验要求：

1.  **thinking-on 与 thinking-off 必须视为实验条件，而非 formatting detail。** CoT-refusal 研究已经证明，reasoning trajectory 本身可以携带并重建 refusal/compliance state。[\[24\]](https://arxiv.org/abs/2605.26772)

2.  **不要提前认定 XML \<function\> 等标记是特殊 token。** 应对 pinned tokenizer 直接检查 token IDs、chat template 与 rendered sequence；公开模型卡只确认 XML-style emission。[\[47\]](https://huggingface.co/openbmb/MiniCPM5-2B)

3.  **用 BF16 官方 safetensors 作为主机制 checkpoint，不用 GGUF/GPTQ/社区 uncensored 版本进行方向提取。** 社区 provenance/quantizer/template 已经被证明可以产生严重实验混杂。[\[6\]](https://arxiv.org/abs/2607.17427)

由于它是 standard LlamaForCausalLM 而非 MoE 或 multimodal architecture，标准 residual-stream/head/MLP intervention 路径应当可用；NNsight 明确支持任意 PyTorch model 的 activation 读取/修改和 cross-prompt patching，因此最适合做第一版实验。TransformerLens 当前 bridge 覆盖 Llama 等大量 architecture families，故**很可能**可直接或经标准 Llama adapter 使用，但应先对 exact MiniCPM5 revision 做 equivalence test，而不是把“Llama-style”当作已经验证的兼容性。pyvene 可作为独立 intervention implementation。[\[48\]](https://nnsight.net/index.html)

### 数据集：不要再用 harmful vs random harmless

主数据最好采用一个**多因素 minimal-pair battery**：

| 子集 | 正/对照条件 | 目的 | 推荐标签 |
|:---|----|----|----|
| Safety | harmful vs topic/format-matched benign | r_harm / safety routing | harm / benign |
| Safety execution | same safety-relevant semantics、不同 policy outcome 条件 | 把 detection 与 refusal 分开 | refuse / answer |
| Uncertainty | answerable vs matched unanswerable | S_uncertainty | know / insufficient |
| Caution | sufficient vs incomplete/conflicting evidence | evidence threshold | commit / hedge |
| Verdict | **相同任务格式**，正确结果 CONFIRM / REJECT / ABSTAIN | S_negative-verdict 与 commitment | C/R/A |
| Tool propensity | tool-required vs internally-answerable | r_tool-call | call / answer |
| Tool identity | 条件满足调用后不同 tools | S_tool-id | tool₁…toolₙ |
| Tool abstention | relevant tool vs irrelevant/unavailable/insufficient-info | action restraint | act / no-act |
| Confirmation | reversible action vs irreversible action lacking confirmation | generic action inhibition | execute / clarify |

关键是让**evidence context 本身决定 verdict，而不是通过文字情绪决定 verdict**。例如每个 verdict triplet 都应尽量保持长度、领域、语言、答案模板一致，只改变一个真正决定结论的证据事实。

建议至少拆三种 extraction recipe，以直接检验 H5：

$`R_{1}:raw\ harmful\ vs\ broad\ harmless,`$

$`R_{2}:topic/format - matched\ minimal\ pairs,`$

$`R_{3}:factorially\ controlled\ safety - trigger\  \times \ behavioral - outcome.`$

如果 $`R_{1}`$ 有显著 verdict side effect、而 $`R_{2}/R_{3}`$ 显著减弱，H5 将得到非常强的支持。

数据划分应按**semantic family**做 train/validation/test 隔离，而不是随机拆 paraphrase；方向、probe、steering-strength selection、causal localization 使用不同 split，避免 “找一个能产生预期结果的 layer/vector” 后再在同一数据上报告。

### 激活位置

不要只取一个位置。至少比较：

$`h_{\ell}^{last - user - content},\quad h_{\ell}^{last - prompt - token},\quad{mean}_{t \in user\ span}h_{\ell,t},`$

以及最终决策前的 first-generation-token state。

Son et al. 使用 final prompt token，并在这一位置观察到 KR/SR 的共享结构；但 tool paper 的部分因果效应与 target tool 的首输出 token 紧密相关，所以“prompt-side semantic representation”和“output-side routing/readout”必须分开。[\[49\]](https://arxiv.org/html/2609.00760)

在 MiniCPM5 tool context 中，所有 activation 必须以**语义 anchor**对齐，例如：

end_of_user_message\
end_of_tool_schema\
generation_boundary\
first_tool_call_token

而不是简单比较 sequence index -1，否则 variable-length XML/tool schema 会造成 position confound。

### 方向与子空间估计

不建议把每一构念预设为单向量。流程应是：

$`d_{\ell}^{(c)} = E\lbrack h_{\ell}(x^{+}) - h_{\ell}(x^{-})\rbrack,`$

作为最基本 baseline，同时用 bootstrap 对多个 prompt-family condition means 做 PCA/SVD，定义

$`S_{c}^{(\ell)} = span\left( v_{1},\ldots,v_{k} \right),`$

其中 $`k`$ 由 held-out discriminability 与稳定性决定，而不是人为强设为 1。

几何层至少计算：

$`cos(d_{a}^{(\ell)},d_{b}^{(\ell)}),`$

principal angles

$`\theta_{1},\ldots,\theta_{k}\left( S_{a}^{(\ell)},S_{b}^{(\ell)} \right),`$

以及 projection fraction：

$`\rho_{a \rightarrow b}^{(\ell)} = \frac{\parallel P_{S_{b}^{(\ell)}}d_{a}^{(\ell)} \parallel_{2}^{2}}{\parallel d_{a}^{(\ell)} \parallel_{2}^{2}}.`$

同时做 cross-probe：

$`{probe}_{safety} \rightarrow uncertainty\ test`$

以及反方向 transfer。CCA/SVCCA 只应用于样本配对清晰且经过 cross-validation/whitening 的情况；否则高维 representation 很容易产生虚假 similarity。

SAE/crosscoder 应放在**线性解释不足后的第二阶段**。本次检索没有核实到可直接用于 MiniCPM5-2B 的官方 pretrained SAE/crosscoder，因此不应让 SAE 成为 MVP 前置依赖；若进入 H6 路线，再训练模型专用 dictionary/跨 checkpoint crosscoder 更合理。

### 最小可行实验：真正能够削弱 H1

单纯得到

$`cos(r_{refusal},r_{uncertainty}) \approx 0`$

**不能**证伪 H1，因为 uncertainty 可能是多维、弯曲或位置依赖的。

更好的 MVP 是四步：

**第一步：matched extraction。** 在同一 layers、相同 semantic anchor 上独立提取 r_safety-refusal 与 S_uncertainty/caution，用 principal angles、projection fraction 和 permutation-matched random subspaces 判断是否有超过 null 的线性 overlap。

**第二步：cross-ablation。** 对

$`r_{safety - refusal}`$

做 activation ablation，同时测试 safety refusal、uncertainty decoding、epistemic abstention 与 verdict。

**第三步：information-versus-behavior dissociation。** 关键 primary endpoint 是：

$`\Delta uncertainty\ probe\ AUC\quad vs\quad\Delta P(REJECT/ABSTAIN).`$

若 ablation 使 reject/abstain 大幅下降，但 uncertainty decodability 在编辑位置及后续相当一段深度上保持接近 baseline，则**“编辑是通过直接删掉所测量的线性 uncertainty representation 才产生 verdict bias”这一简单 H1 版本被削弱**。

**第四步：反向 cross-ablation。** 删除 S_uncertainty/caution 中最稳定的分量，观察是否同样抑制 safety refusal。若两种干预高度不对称，又没有强几何 overlap，H1 更难成立。

最低 behavioral effect matrix 应为：

| Intervention | Safety refusal | Harm detection | Uncertainty decoding | Epistemic abstention | Negative verdict | Tool-call | Tool-abstain |
|:---|----|----|----|----|----|----|----|
| −r_safety-refusal | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| −S_uncertainty | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| −S_caution | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| −S_negative-verdict | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| −r_tool-call | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| −S_tool-abstain | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

这里的 ✓ 表示“必须测量”，不是预期必然产生影响。

### 强实验：真正区分 H1 与 H2

强版本必须进入 **causal patching**。

构造 matched pair：

$`x_{U} = 证据不足/有反例,\quad\quad x_{C} = 证据充分/无反例.`$

分别运行 base 与 refusal-edited model，定位在 intact model 中真正把 $`x_{U}`$ 推向 REJECT/ABSTAIN 的 heads/MLPs。

寻找三类组件：

$`C_{encode} \rightarrow C_{route} \rightarrow C_{readout}.`$

首先验证 C_encode 中 uncertainty/counterexample signal 在 edited model 中是否仍可读。

随后在 edited uncertain run 中，将 base uncertain run 的候选 C_route activation patch 回去：

$`h_{C_{route}}^{edited,U} \leftarrow h_{C_{route}}^{base,U}.`$

**H2 最强的签名是：**

$`uncertainty\ information\ remains\ decodable\ upstream\  + \ edited\ model\ fails\ to\ reject/abstain\  + \ patching\ a\ downstream\ route\ restores\ rejection\  + \ same\ route\ knockout\ also\ weakens\ safety\ refusal\`$

更强一步，再测：

$`C_{route}`$

knockout 是否同时削弱 safety refusal、epistemic abstention、negative verdict 和 tool abstention，却保留 r_harm、r_uncertainty 的上游 probe performance。这才接近用户所定义的 shared commitment/action-inhibition circuit。

需要做 reciprocal controls：patching random heads、同层 random vectors、wrong-condition activation、同 norm shuffled activation，以及只 patch upstream uncertainty carrier 而不 patch downstream route。

### H3、H4、H5、H6 的专门控制

**H3 输出 token artifact**：不要把 YES/NO 本身固定为 semantic class。随机化标签映射：

$`A \leftrightarrow CONFIRM,\quad B \leftrightarrow REJECT`$

并跨样本 counterbalance；再用多套文字标签、顺序翻转、直接读取 class logit 和自由文本评分。若 effect 随 token identity 而非 semantic verdict 翻转，H3 得到支持。

**H4 assertiveness/sycophancy**：增加无需真正不确定性计算的 social-agreement、flattery、optimism、contradiction tasks。clearbluejar 的小规模 flattery probe 已显示某些 aggressive abliteration 更容易肯定，但目前仍不足以作为通用机制证据。[\[7\]](https://clearbluejar.github.io/posts/does-abliteration-skew-your-bug-hunting/)

**H5 contamination**：上述 $`R_{1}/R_{2}/R_{3}`$ extraction recipe 是关键。方向 extraction dataset 本身必须成为 independent variable，而不是固定 preprocessing。

**H6 nonlinear distributed circuit**：只有当 matched linear-subspace experiments 无法解释足够 variance、patching 指向分散 heads/features 时，再升级到 SAE/crosscoder、feature ablation、path patching 或 sparse circuit tracing。

### 统计与行为指标

主要 endpoint 建议预注册为：

$`\Delta Verdict\ Positive\ Rate,`$

$`\Delta Uncertainty\ Probe\ AUC,`$

$`Patch\ Restoration\ Effect,`$

$`\Delta Tool - Abstention\ Paired\ Accuracy.`$

同时报告：

| 构念 | 指标 |
|:---|----|
| Safety refusal | refusal rate、safe-completion class |
| Harm detection | held-out probe AUC / calibrated margin |
| Uncertainty | probe AUC、Brier score、ECE |
| Selective answering | coverage–risk curve / AURC |
| Verdict | C/R/A confusion matrix、false-confirmation rate |
| Reasoning–verdict consistency | reasoning evidence class vs final decision contradiction rate |
| Tool propensity | call/no-call accuracy |
| Tool identity | **conditional on correct decision to call** 的 tool accuracy |
| Tool abstention | unnecessary-call rate、paired act/abstain accuracy |
| Confirmation | irreversible action before confirmation rate |
| Retry calibration | tool failure 后 retry/escalate/stop correctness |

binary paired behavior 用 McNemar test；continuous/probability endpoints 用 paired bootstrap confidence intervals；多个 prompt families 可用 mixed-effects logistic model，其中 prompt family 作为 random effect；全层全头扫描使用 FDR 或预先定义的 discovery/confirmatory splits。principal-angle/projection analysis 使用 bootstrap 和 dimension-matched random-subspace permutation null。

尤其不要只报告 p-value。对行为干预至少同时给 **percentage-point change、odds ratio、95% CI**。

## 代理工具扩展与受保护子空间

工具机制文献强烈建议把 agent 行为拆成至少三层：

$`Need/propensity \rightarrow Call\ or\ not \rightarrow Tool\ identity \rightarrow Arguments/action.`$

*Tool Calling is Linearly Readable and Steerable* 的结果表明 tool identity 具有强线性 representation，并能通过少数中晚层 attention heads 的 patching 改变；但论文在真实 multi-turn τ-bench 场景中的 steering 效果明显更不稳定。[\[25\]](https://arxiv.org/abs/2605.07990) *Tunable Tool-Call Rates* 则表明 whether-to-call 本身可以被连续调节，甚至能让模型对原本会内部回答的问题更多调用工具，而该方向并不只是某个具体 tool identity。[\[50\]](https://arxiv.org/html/2608.25198)

因此，一个模型完全可能：

$`tool\ identity\ accuracy = 95\%`$

却同时变成

$`P(call \mid should\ abstain) \uparrow .`$

这正是为什么 BFCL tool name / argument accuracy 不足以证明 agent behavior preserved。BFCL 确实包含 function relevance detection，并在 V4 扩展到 agentic settings；但是 AgentAbstain 更直接测量 should-act/should-abstain paired behavior。AgentAbstain 包含 263 对任务、42 个 executable sandbox environments 与八类 abstention scenario，并报告最佳被测 agent 的 paired accuracy 仍只有 59.5%，而 abstention capability 与一般 task-solving ability 并不高度同步。[\[51\]](https://gorilla.cs.berkeley.edu/blogs/8_berkeley_function_calling_leaderboard.html)

### Agent 扩展数据集

建议给 MiniCPM5 构造同一个 tool schema 下的五类 minimal pairs：

| 状态 | 正确策略 | 要测的变量 |
|:---|----|----|
| 信息足够，工具必要 | call tool | propensity |
| 信息足够，工具可选但没必要 | direct answer | unnecessary-tool restraint |
| 工具与问题无关 | no call | relevance abstention |
| 缺少关键参数 | clarify first | epistemic/tool abstention |
| 工具可执行不可逆动作、但未确认 | request confirmation | action restraint |

再加入 tool failure：

$`retry,\quad switch\ tool,\quad clarify,\quad stop,`$

避免把“不断重试”误当作 agent competence。

ToolSandbox 已经包含 insufficient-information 等状态性困难；τ-bench 更侧重动态 user/tool/policy interaction；ToolFailBench 则显式区分 unnecessary-tool-use 等失败类型。因此它们适合作为外部测试，而不是彼此互换的“tool score”。[\[52\]](https://aclanthology.org/2025.findings-naacl.65/)

### 受保护子空间不宜简单相加

用户提出：

$`S_{protected} = S_{uncertainty} + S_{caution} + S_{negative - verdict} + S_{tool - call} + S_{tool - selection} + S_{tool - abstention}`$

是正确的起点，但**不建议直接把所有 basis 拼起来做普通 orthogonal projection**。

最基本的 ridge residualization 可以写成：

$`r_{edit} = r_{refusal} - C(C^{\top}C + \lambda I)^{- 1}C^{\top}r_{refusal},`$

其中

$`C = \lbrack U,\mspace{6mu} K,\mspace{6mu} N,\mspace{6mu} T_{prop},\mspace{6mu} T_{id},\mspace{6mu} T_{abs}\rbrack.`$

这比

$`(I - P_{C})r`$

更稳健，因为 protected directions 之间很可能高度 collinear，普通 projection 容易受 basis estimation noise 放大。SRA 本身也采用 ridge-regularized residualization，而不是简单假定 Concept Atoms 完全正交。[\[17\]](https://arxiv.org/abs/2601.08489)

但论文级方案应再进一步，把保护问题写成**多目标 constrained editing**：

$`\min_{v}\quad L_{refusal - target}(v) + \lambda_{drift}D_{KL} + \sum_{k}^{}\lambda_{k}L_{protected,k}(v),`$

subject to

$`\Delta B_{uncertainty},\Delta B_{verdict},\Delta B_{tool - abstain} \leq \epsilon_{k}.`$

也就是说，**protected space 的最终验收标准必须是因果行为，而不能只有 geometry**。

尤其需要防止：

**过度保护。** 如果真正的 refusal mechanism 与合理 action restraint 共用一部分表示，把所有 restraint directions 完全 orthogonalize 掉，可能导致 refusal edit 几乎无效。

**层间变化。** $`S_{protected}^{(\ell)}`$ 很可能随层变化；一个全模型共享 basis 未必合理。

**nonlinear interactions。** 即使 edit vector 对所有 protected directions 在当前点正交，后续 MLP/attention 也可能将扰动重新映射回 protected behavior。

**estimated-atom quality。** SRA 自己承认 curated atom registry 可能遗漏 confounders。[\[17\]](https://arxiv.org/abs/2601.08489)

因此最强的设计不是“先 orthogonalize，再看 KL”，而是：

$`geometry\ constraint + behavioral\ preservation + causal - route\ preservation`$

三者同时验收。

## 可发表主张、复现、资源与路线图

### 不同证据阶段允许的主张边界

| 已获得证据 | 可以写进论文的主张 | 仍然不能写 |
|:---|----|----|
| **只有 geometry** | “在所测 layers/positions 上，refusal 与 caution subspaces 显示 X 程度线性重叠/分离。” | “它们共享机制”“abliteration 因此造成 verdict bias” |
| **geometry + cross-ablation** | “refusal-direction intervention 对 verdict/abstention 有因果 collateral effect；该 effect 与所测 uncertainty representation 的保存/丢失模式一致。” | “已证明同一个 circuit 介导二者” |
| **upstream decode + downstream patching** | “在 MiniCPM5 的所测任务中，某 downstream component 因果介导 uncertainty→decision，并受 refusal edit 干扰。” | “所有 LLM 都有统一 commitment circuit” |
| **跨 safety/epistemic/tool 的 knockout + interchange + restoration，且跨 checkpoint/data replication** | “在研究范围内，定位到共享 action-routing circuit，具有重复的 necessity/sufficiency 证据。” | 超出模型家族和任务分布的普适神经理论 |

即使找到了高 cosine，也只能是 Level 2；即使 probe 达到 99%，也只是 information presence；即使删除 head 会同时降低两项行为，也还可能是 generic computation damage。真正 H2 需要的是**上游信息保留 + route-specific intervention + behavioral restoration**这一组合。

### MiniCPM5 复现清单

实验 artifact 至少必须冻结：

| 类别 | 必须记录 |
|:---|----|
| 模型 | exact openbmb/MiniCPM5-2B revision SHA |
| 控制 checkpoint | exact Base、SFT revision SHA |
| tokenizer | exact revision、vocab hash、special-token map |
| chat template | 原始 Jinja/template 文本 hash |
| thinking | enable_thinking 明确固定；ON/OFF 分开报告 |
| tool format | XML rendered schema、parser version、function definitions |
| precision | BF16/FP16；主实验禁量化 |
| quantization | 明确 none；量化仅做 secondary robustness |
| libraries | PyTorch、Transformers、NNsight/TransformerLens/pyvene exact versions |
| seeds | extraction、probe、generation、bootstrap seeds |
| data | train/val/test manifest 与 SHA256 |
| generation | greedy 与 stochastic robustness 参数分别冻结 |
| hook locations | 模块路径、pre/post residual、head/MLP output definitions |
| token anchors | last-user、last-prompt、generation-boundary 等精确定义 |
| activation normalization | 是否 center、L2 normalize、whiten |
| directions | extraction formula、dataset IDs、sample counts、selected rank |
| intervention | alpha/gamma、layer、token span、norm matching |
| eval | deterministic rules、judge model/version 若使用 LLM judge |
| statistics | preregistered endpoints、multiplicity correction |
| outputs | raw logits、activations metadata、generated text 与 edit checkpoint hashes |

MiniCPM5 官方还推荐 sampling temperature=1.0, top_p=0.95，但机制实验不应因此只使用 stochastic sampling：方向/patching discovery 最好以 deterministic decoding 为主，再用官方推荐 sampling 做 behavioral robustness replication。[\[47\]](https://huggingface.co/openbmb/MiniCPM5-2B)

### 时间与预算情景

以下数字是**项目规划额度**，不是云 GPU 市场报价。

| 情景 | 时间 | 人力/算力建议 | 规划预算 | 能做到什么 |
|:---|----|----|----|----|
| **紧凑** | 4–6 周 | 1 人；单张 24–48GB GPU 或等价租用 | 约 US\$1k–3k | MiniCPM5 final；matched safety/uncertainty/verdict；geometry + cross-ablation；H1 MVP |
| **中等** | 10–14 周 | 1–2 人；2–4 张 48–80GB GPU 可调度 | 约 US\$5k–15k | Base/SFT/final；full layer/head scans；patching；tool abstention extension；完整论文主实验 |
| **宽松** | 6–9 个月 | 2–3 人；4–8 张 80GB 级 GPU 或等价集群 | 约 US\$20k–50k+ | 跨模型 replication、SAE/crosscoder、full circuit tracing、agent sandbox、artifact release |

由于 MiniCPM5-2B 规模小于大量当前 mechanism papers 的 7B–30B 实验模型，单次 forward 并不是主要瓶颈；真正昂贵的是**全层 × 全头 × 多 token × 多 paired conditions 的 causal intervention combinatorics**，所以优先通过 direction/mediation screen 缩小候选组件比直接 exhaustive patching 更合理。MiniCPM5 官方的 42 层结构使这种分阶段扫描尤其可操作。[\[53\]](https://huggingface.co/openbmb/MiniCPM5-2B)

### 中等资源路线图

|  |
|:--:|
| <img src="拒绝编辑为何改变不确定性下的决策：从几何重叠到共享路由的机制证据、MiniCPM5 实验设计与代理工具约束_media/media/image1.png" style="width:5.83333in;height:2.55658in" alt="Rendered Mermaid diagram 2" /> |

**主要里程碑**应明确为：M1 复现 Arditi-style intervention；M2 得到 H1 geometry/cross-ablation 结果；M3 得到 uncertainty-information-preserved-or-not 的决定性结果；M4 定位并验证 candidate route；M5 tool-abstention 跨任务测试；M6 Base/SFT/final replication。

**主要风险点**是：MiniCPM5 本身 safety refusal 不够稳定；matched dataset 未真正诱发独立构念；thinking mode 改变 route；方向跨语言不稳定；全组件 patching 多重检验严重；tool schema tokenization 引入位置 confound；以及“找不到低维 shared circuit”。最后一个不是研究失败——它将直接把证据推向 H6。

## 优先阅读顺序与最终结论

### 五篇必读

**Arditi et al., *Refusal in Language Models Is Mediated by a Single Direction*.**\
阅读时只问一个问题：**作者究竟因果证明了“什么方向介导什么行为”，又有哪些语义纯度是他们没有证明的？** 特别检查 harmful/harmless datasets、候选 layer selection、runtime directional ablation 与 weight orthogonalization 的区别。[\[1\]](https://papers.neurips.cc/paper_files/paper/2024/hash/f545448535dfde4f9786555403ab7c49-Abstract-Conference.html)

**Zhao et al., *LLMs Encode Harmfulness and Refusal Separately*.**\
阅读问题：**在什么意义上“模型知道有害”可以与“模型执行拒绝”分离？哪一种 intervention 足以证明 detection ≠ policy execution？** 这是理解 H2 的最干净上游基础。[\[18\]](https://arxiv.org/abs/2507.11878)

**Son et al., *A Unified Mechanistic Analysis of Knowledge- and Safety-Based Refusals*.**\
阅读问题：**所谓 commit-then-specify 的“commit”到底被什么证据支持？其 shared direction 是 uncertainty、refusal action，还是两者的混合？哪些结果是 geometry/probe，哪些是 steering/ablation/patching？** 特别注意 213 matched quadruples、0.699–0.794 alignment、晚层 specialization，以及作者对 incomplete circuit claim 的限制。[\[19\]](https://arxiv.org/html/2609.00760)

**Frank, *How Alignment Routes*.**\
阅读问题：**什么实验真正让“routing”从隐喻变成 causal statement？gate 的 necessity/sufficiency 是如何测试的？这种 safety routing 是否有任何证据可以直接推广到 epistemic decisions？** [\[21\]](https://arxiv.org/abs/2604.04385)

**Fafuła, *Abliteration Is Not a Scalpel*.**\
阅读问题：**哪些 side effects 真正跨 family 复制，哪些没有？作者建立的是行为事实还是机制事实？provenance audit 对自己的实验设计有什么警告？** 最重要的是记住 confidence 的变化没有统一方向，因此不要把所有 collateral effect 压缩成“更自信”。[\[6\]](https://arxiv.org/abs/2607.17427)

### 第二梯队

**There Is More to Refusal in Large Language Models than a Single Direction.**\
问题：**为什么几何上不同的 refusal directions 会产生近似共同的 behavioral trade-off？这是否提示 shared controller，还是只是输出端 convergence？** [\[16\]](https://arxiv.org/abs/2602.02132)

**The Geometry of Refusal in Large Language Models: Concept Cones and Representational Independence.**\
问题：**为什么 cosine/orthogonality 不能告诉你两个 intervention 是否独立？应该怎样设计自己的 subspace tests？** [\[15\]](https://arxiv.org/abs/2502.17420)

**Surgical Refusal Ablation.**\
问题：**dirty refusal vector 中哪些成分被视为 protected，哪些被视为 target？为什么 epistemic uncertainty 在这里没有被当作你所需要的 protected agent capability？** [\[17\]](https://arxiv.org/abs/2601.08489)

**What Drives Representation Steering?**\
问题：**steering vector 如何通过实际 attention computation 改变输出？能否把同样的 multi-token patching framework 用在 H1/H2 区分上？** [\[23\]](https://arxiv.org/abs/2604.08524)

**Tool Calling is Linearly Readable and Steerable in Language Models.**\
问题：**tool identity representation 在哪一层、通过哪些 heads 进入输出？其与 unembedding 的关系是否提供 H3 output-readout artifact 的类比？** [\[54\]](https://arxiv.org/abs/2605.07990)

**Tunable Tool-Call Rates in LLM Agents via Representation Steering.**\
问题：**whether-to-call 与 which-tool 的分离有多强？能否将同样设计扩展为 should-act vs should-abstain？** [\[50\]](https://arxiv.org/html/2608.25198)

### 技术博客、仓库与基准

clearbluejar 的 verdict-bias 博客应作为**实验现象与 stimulus design 灵感**阅读，而不是机制证据；特别值得复现的是“reasoning 已找到否决证据、final verdict 却肯定”的 structured triage 格式。[\[7\]](https://clearbluejar.github.io/posts/does-abliteration-skew-your-bug-hunting/)

Heretic / projected / biprojected 技术实现适合用来了解社区如何实际生成“uncensored” checkpoint，但不应作为 primary scientific baseline；最干净主实验仍应从官方 base/final checkpoint 自己实施可审计 intervention。[\[39\]](https://github.com/izikeros/heretic)

MiniCPM5 官方模型卡、NNsight、TransformerLens bridge 与 pyvene 应先于任何 implementation 开始阅读，因为 exact chat template、thinking mode、XML tool-call boundary 与 residual hook 定义将直接决定激活是否可比较。[\[55\]](https://huggingface.co/openbmb/MiniCPM5-2B)

BFCL 应用于 **tool competence / relevance**，τ-bench 用于 **multi-turn policy/tool execution**，AgentAbstain 用于 **should-act/should-abstain calibration**，ToolSandbox/ToolFailBench 用于 **insufficient-information 与 unnecessary-tool-use**。把这些结果分开报告，比一个“agent score”更符合本研究的机制问题。[\[56\]](https://gorilla.cs.berkeley.edu/leaderboard)

**最终判断是：当前文献最支持的不是“拒绝方向就是不确定性方向”，而是一个更细的分层图景——semantic detection、refusal/abstention commitment、type-specific rationale 与 output/action routing 可以彼此分离，并在部分阶段重新汇合。** safety 文献已经证明“检测到”与“执行策略”不是同一件事；knowledge/safety refusal 文献已经证明不同拒绝原因可共享一个大的 refusal-related structure；agent 文献又证明 whether-to-call 与 which-tool 可以分开。真正尚缺的一步，是把这些结果放进**同一个模型、同一套 matched causal design**，观察 refusal edit 后 uncertainty representation 是否仍在，而它对 reject/abstain/tool-restraint 的控制是否被切断。[\[57\]](https://arxiv.org/abs/2507.11878)

因此，最值得首先执行的研究不是进一步优化 cosine，也不是马上做更复杂的“protected abliteration”，而是完成一个可以产生明确分岔结果的因果实验：

$`Refusal\ edit\  \downarrow \ Does\ uncertainty\ information\ survive?\ \{ No\  \Rightarrow H1/H5 - like\ representational\ damage\ Yes,\ but\ verdict\ changes\  \Rightarrow search\ downstream\ routing\ Route\ patch\ restores\ verdict\  \Rightarrow strong\ evidence\ for\ H2\ \`$

若进一步发现同一 route 的 knockout 同时破坏 **safety refusal、epistemic abstention、negative verdict 和 tool abstention**，而 upstream harm/uncertainty/tool-need representations 仍然保留，那么才有资格提出论文中最强的机制主张：**MiniCPM5 中存在一个跨安全、认识论判断与代理行动克制的共享 downstream decision-routing circuit。** 若实验反而发现这些通路彼此分散或非线性，那将是对 H6 的有价值支持，同样能够回答附件所提出的核心科学问题，而不需要为了证明“refusal 与 uncertainty 重叠”而扭曲证据。

[\[1\]](https://papers.neurips.cc/paper_files/paper/2024/hash/f545448535dfde4f9786555403ab7c49-Abstract-Conference.html) [\[11\]](https://papers.neurips.cc/paper_files/paper/2024/hash/f545448535dfde4f9786555403ab7c49-Abstract-Conference.html) https://papers.neurips.cc/paper_files/paper/2024/hash/f545448535dfde4f9786555403ab7c49-Abstract-Conference.html

<https://papers.neurips.cc/paper_files/paper/2024/hash/f545448535dfde4f9786555403ab7c49-Abstract-Conference.html>

[\[2\]](https://arxiv.org/abs/2502.17420) [\[15\]](https://arxiv.org/abs/2502.17420) https://arxiv.org/abs/2502.17420

<https://arxiv.org/abs/2502.17420>

[\[3\]](https://arxiv.org/abs/2507.11878) [\[12\]](https://arxiv.org/abs/2507.11878) [\[18\]](https://arxiv.org/abs/2507.11878) [\[41\]](https://arxiv.org/abs/2507.11878) [\[44\]](https://arxiv.org/abs/2507.11878) [\[57\]](https://arxiv.org/abs/2507.11878) https://arxiv.org/abs/2507.11878

<https://arxiv.org/abs/2507.11878>

[\[4\]](https://arxiv.org/html/2609.00760) [\[19\]](https://arxiv.org/html/2609.00760) [\[43\]](https://arxiv.org/html/2609.00760) [\[45\]](https://arxiv.org/html/2609.00760) [\[49\]](https://arxiv.org/html/2609.00760) https://arxiv.org/html/2609.00760

<https://arxiv.org/html/2609.00760>

[\[5\]](https://arxiv.org/abs/2603.18280) [\[20\]](https://arxiv.org/abs/2603.18280) https://arxiv.org/abs/2603.18280

<https://arxiv.org/abs/2603.18280>

[\[6\]](https://arxiv.org/abs/2607.17427) [\[10\]](https://arxiv.org/abs/2607.17427) [\[40\]](https://arxiv.org/abs/2607.17427) https://arxiv.org/abs/2607.17427

<https://arxiv.org/abs/2607.17427>

[\[7\]](https://clearbluejar.github.io/posts/does-abliteration-skew-your-bug-hunting/) https://clearbluejar.github.io/posts/does-abliteration-skew-your-bug-hunting/

<https://clearbluejar.github.io/posts/does-abliteration-skew-your-bug-hunting/>

[\[8\]](https://arxiv.org/abs/2605.07990) [\[25\]](https://arxiv.org/abs/2605.07990) [\[54\]](https://arxiv.org/abs/2605.07990) https://arxiv.org/abs/2605.07990

<https://arxiv.org/abs/2605.07990>

[\[9\]](https://arxiv.org/abs/2601.08489) [\[17\]](https://arxiv.org/abs/2601.08489) https://arxiv.org/abs/2601.08489

<https://arxiv.org/abs/2601.08489>

[\[13\]](https://arxiv.org/abs/2406.11717) https://arxiv.org/abs/2406.11717

<https://arxiv.org/abs/2406.11717>

[\[14\]](https://arxiv.org/abs/2411.09003) https://arxiv.org/abs/2411.09003

<https://arxiv.org/abs/2411.09003>

[\[16\]](https://arxiv.org/abs/2602.02132) [\[42\]](https://arxiv.org/abs/2602.02132) https://arxiv.org/abs/2602.02132

<https://arxiv.org/abs/2602.02132>

[\[21\]](https://arxiv.org/abs/2604.04385) https://arxiv.org/abs/2604.04385

<https://arxiv.org/abs/2604.04385>

[\[22\]](https://arxiv.org/abs/2609.00051) https://arxiv.org/abs/2609.00051

<https://arxiv.org/abs/2609.00051>

[\[23\]](https://arxiv.org/abs/2604.08524) https://arxiv.org/abs/2604.08524

<https://arxiv.org/abs/2604.08524>

[\[24\]](https://arxiv.org/abs/2605.26772) https://arxiv.org/abs/2605.26772

<https://arxiv.org/abs/2605.26772>

[\[26\]](https://arxiv.org/abs/2608.25198) https://arxiv.org/abs/2608.25198

<https://arxiv.org/abs/2608.25198>

[\[27\]](https://arxiv.org/abs/2607.10059) https://arxiv.org/abs/2607.10059

<https://arxiv.org/abs/2607.10059>

[\[28\]](https://gorilla.cs.berkeley.edu/blogs/8_berkeley_function_calling_leaderboard.html) [\[51\]](https://gorilla.cs.berkeley.edu/blogs/8_berkeley_function_calling_leaderboard.html) https://gorilla.cs.berkeley.edu/blogs/8_berkeley_function_calling_leaderboard.html

<https://gorilla.cs.berkeley.edu/blogs/8_berkeley_function_calling_leaderboard.html>

[\[29\]](https://arxiv.org/abs/2406.12045) https://arxiv.org/abs/2406.12045

<https://arxiv.org/abs/2406.12045>

[\[30\]](https://aclanthology.org/2025.findings-naacl.65/) [\[52\]](https://aclanthology.org/2025.findings-naacl.65/) https://aclanthology.org/2025.findings-naacl.65/

<https://aclanthology.org/2025.findings-naacl.65/>

[\[31\]](https://arxiv.org/abs/2607.04686) https://arxiv.org/abs/2607.04686

<https://arxiv.org/abs/2607.04686>

[\[32\]](https://aclanthology.org/2025.findings-emnlp.958/) https://aclanthology.org/2025.findings-emnlp.958/

<https://aclanthology.org/2025.findings-emnlp.958/>

[\[33\]](https://huggingface.co/openbmb/MiniCPM5-2B) [\[46\]](https://huggingface.co/openbmb/MiniCPM5-2B) [\[47\]](https://huggingface.co/openbmb/MiniCPM5-2B) [\[53\]](https://huggingface.co/openbmb/MiniCPM5-2B) [\[55\]](https://huggingface.co/openbmb/MiniCPM5-2B) https://huggingface.co/openbmb/MiniCPM5-2B

<https://huggingface.co/openbmb/MiniCPM5-2B>

[\[34\]](https://huggingface.co/openbmb/MiniCPM5-2B-SFT) https://huggingface.co/openbmb/MiniCPM5-2B-SFT

<https://huggingface.co/openbmb/MiniCPM5-2B-SFT>

[\[35\]](https://huggingface.co/openbmb/MiniCPM5-2B-Base) https://huggingface.co/openbmb/MiniCPM5-2B-Base

<https://huggingface.co/openbmb/MiniCPM5-2B-Base>

[\[36\]](https://nnsight.net/index.html) [\[48\]](https://nnsight.net/index.html) https://nnsight.net/index.html

<https://nnsight.net/index.html>

[\[37\]](https://transformerlensorg.github.io/TransformerLens/content/getting_started.html) https://transformerlensorg.github.io/TransformerLens/content/getting_started.html

<https://transformerlensorg.github.io/TransformerLens/content/getting_started.html>

[\[38\]](https://stanfordnlp.github.io/pyvene/) https://stanfordnlp.github.io/pyvene/

<https://stanfordnlp.github.io/pyvene/>

[\[39\]](https://github.com/izikeros/heretic) https://github.com/izikeros/heretic

<https://github.com/izikeros/heretic>

[\[50\]](https://arxiv.org/html/2608.25198) https://arxiv.org/html/2608.25198

<https://arxiv.org/html/2608.25198>

[\[56\]](https://gorilla.cs.berkeley.edu/leaderboard) https://gorilla.cs.berkeley.edu/leaderboard

<https://gorilla.cs.berkeley.edu/leaderboard>
