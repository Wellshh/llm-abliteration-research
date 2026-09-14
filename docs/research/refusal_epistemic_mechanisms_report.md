# Mechanistic Study of Refusal Editing, Epistemic Caution, Verdict Bias, and Agent/Tool-Use Routing in LLMs

**A deep-research report prepared for experimental work on MiniCPM5**

*Date: 2026-09-09. Evidence discipline: every mechanistic claim is tagged with an evidence level — L0 behavioral, L1 probe readout, L2 representational geometry, L3 steering/ablation, L4 activation patching / interchange, L5 localized circuit necessity + sufficiency. L1–L2 findings are never described with causal language. Geometry is treated as hypothesis-generating, never as causal proof.*

## 1. Executive conclusion

**What is established (multi-source, replicated).** Refusal behavior in instruction-tuned LLMs is mediated by representations that are (a) *high-dimensional* — refusal concepts occupy cones or multi-direction subspaces of dimension roughly 5–7 across four independent measurement methods [^1] [^2] [^3] [^4] — yet (b) *low-rank controllable* — a single difference-of-means (DIM) direction suffices to behaviorally disable refusal across many models [^5] <sup>1</sup>. The semantics of that single direction are underdetermined: topic-matched control experiments show the classic harmful-vs-harmless contrast is confounded, and the extracted direction may encode “harm” or “danger” as much as “refusal” [^6]. Safety behavior decomposes into at least three stages — detection (cheap, pre-existing), routing (learned, lab-specific, fragile), and generation — with partial L4 causal localization of a gate-plus-amplifier motif in one model family [^7] [^8] [^9]. Abliteration has real, measurable disposition side effects: a preregistered 21,600-decision study found systematic optimism shifts (+12.2pp Gemma, +7.4pp Qwen) and thinning of uncertainty language with capability covariates intact [^10], and an independent security-audit case study documented *verdict bias* — abliterated models returning CONFIRMED verdicts that their own chain-of-thought contradicts [^11]. Whether-to-call in tool use is a separately readable and steerable linear direction, distinct from which-tool routing, and knowledge-selective [^12] [^13]. Tool abstention is a capability orthogonal to task-solving competence and is essentially invisible to mainstream agent benchmarks (BFCL irrelevance ≈ 10% of score; τ-bench is goal-state only) [^14] [^15] [^16]. No published abliteration-protection method protects *decision* mechanisms — uncertainty, abstention, negative verdicts, tool restraint; the leading spectral-cleaning method (SRA) explicitly treats epistemic uncertainty as a *target* to ablate [^17].

**What is contested.** Whether safety-based and knowledge/epistemic refusal share representation is the field’s live contradiction: one study finds a common component carrying 92–95% of both shifts with commit-then-specify ordering [^18]; another finds near-orthogonal raw directions (mean cos ≈ 0.05) and selective ablation effects [^19]. The disagreement is methodological (control-subtracted shifts vs raw cross-dataset DIM; matched vs unmatched pairs; layer selection) and is precisely the crux this research program must resolve.

**What is speculation.** Any claim that “the refusal direction *is* an uncertainty direction” (naive H1); any causal reading of cosine similarity or probe accuracy; any claim that standard benchmarks (perplexity, MMLU, GSM8K, KL, BFCL) certify that decision mechanisms survived an edit; and the single-author anecdote (“The Retreat”) that abliteration first converts “I cannot” into “I do not know” before removing that too <sup>17</sup> — which, if replicated, would be direct evidence for shared downstream routing (H2) but currently rests on one unreviewed preprint.

**Bottom line for the MiniCPM5 program.** The best current mechanistic model is **H2-flavored**: upstream harm and uncertainty representations are largely distinct, converging on a shared, low-rank, post-training-installed commit/abstain/reject routing stage; refusal-direction abliteration removes the dominant shared component and thereby shifts disposition on *every* construct routed through that stage — including epistemic abstention and negative verdicts. H1 survives only in a weakened form (raw extracted directions overlap because extraction picks up the shared routing component; concept-purified residuals are predicted to be orthogonal). The discriminating experiment is cleanly specified, MiniCPM5 is an unusually tractable target (vanilla Llama architecture, official Base/SFT/RL checkpoint ladder, native XML tool calling) [^20] [^21], and the gap — no causal localization of the commit stage for epistemic constructs, no abliteration × tool-abstention measurement — is real and publishable.

## 2. Conceptual taxonomy

A persistent failure mode of this literature is construct conflation. This report keeps the following ten constructs strictly separate; any experiment or claim must name exactly which it touches.

| \# | Construct | Definition (operational) | Canonical instrument |
|----|----|----|----|
| C1 | **Safety refusal** | Declining a harmful policy-violating request | HarmBench-style prompts; refusal rate |
| C2 | **Harmfulness detection** | Internal representation that an input is harmful, regardless of output | Probes/patching at instruction token positions [^22] <sup>7</sup> |
| C3 | **Epistemic uncertainty** | Internal state reflecting low knowledge/confidence about an answer | Probes on answerable/unanswerable pairs; semantic entropy [^23] [^24] |
| C4 | **Epistemic abstention** | Behaviorally declining to answer (“I don’t know”) | IDK rate on matched unanswerable items [^25] [^26] |
| C5 | **Epistemic caution** | Graded hedging/qualification under incomplete or conflicting evidence | Uncertainty-word density; calibrated verbalized confidence [^27] [^28] |
| C6 | **Negative verdict** | Rejecting a specific hypothesis/claim given evidence (REJECT in CONFIRM/REJECT/ABSTAIN) | Verdict tasks with matched evidence, label-counterbalanced [^29] |
| C7 | **Generic commitment/abstention** | The domain-general decision to commit to an output vs abstain, across domains | The hypothesized shared routing stage S_commit — the object of H2 |
| C8 | **Tool-use propensity (whether-to-call)** | Deciding to invoke any tool vs answer directly | Call-rate on required/optional/irrelevant splits <sup>12</sup> [^30] |
| C9 | **Tool selection (which-tool)** | Choosing the correct tool and arguments among candidates | AST accuracy; tool-identity directions <sup>13</sup> <sup>15</sup> |
| C10 | **Tool abstention / action restraint** | Declining to call when information is insufficient or the action is dangerous/irreversible | AgentAbstain, ToolBeHonest, ST-WebAgentBench consent checks <sup>14</sup> [^31] [^32] |

Three distinction rules used throughout: **(a)** detection (C2, C3) vs decision (C7) vs expression (C1, C4, C5) — each pair is dissociable, and each dissociation has been observed in isolation (harm detection survives jailbreaks that suppress refusal <sup>22</sup>; internal correctness signals reach 0.80–0.97 AUC while outputs sit at 0.44–0.64 <sup>24</sup>; hedging is unfaithful to intrinsic uncertainty <sup>28</sup>). **(b)** Chat vs agent context is a mechanistic boundary, not a deployment detail: chat refusal rates do not transfer to agent settings, and forced tool calls suppress refusal [^33]. **(c)** “Confidence” splits into at least three channels — logit calibration (degraded by RLHF [^34]), verbalized confidence (better calibrated but systematically overconfident [^35] [^36]), and behavioral commitment (the channel verdict bias lives in <sup>10</sup>) — which can move in opposite directions under the same edit <sup>10</sup>.

## 3. Literature map (by mechanism, not chronology)

### Stream A — The single-direction paradigm and its assumptions

Arditi et al. established that a DIM direction r = μ_harmful − μ_harmless, extracted per layer at post-instruction token positions and selected to minimize a bypass score subject to induce\>0 and KL\<0.1, behaviorally disables refusal at negligible cost <sup>5</sup>. Weight orthogonalization is equivalent to all-layer ablation of that rank-one direction <sup>5</sup>. The paradigm carries three load-bearing assumptions, each now challenged: (i) *the contrast isolates refusal* — falsified in its strong form by topic-matched controls, where the contrast fails completely, showing topic confounds drive magnitude <sup>6</sup>; (ii) *one direction = one mechanism* — falsified by Stream B; (iii) *benign-metric stability implies benign semantics* — falsified by Stream D. Notably, the original paper’s own App. L.3 documents incoherent post-abliteration reasoning, and TruthfulQA degrades consistently <sup>5</sup>.

### Stream B — Multi-direction refusal

Four methods converge: refusal occupies a subspace, not a line. Concept cones of dimension 5–7 with demonstrated representational *independence* (orthogonality is insufficient) <sup>2</sup>; SOM-based extraction finding k≈5–7 directions <sup>3</sup>; dominant-plus-secondary structure <sup>4</sup>; and an 11-category study finding geometrically distinct category directions (pairwise cos −0.06…0.92) sitting atop a shared 1-D “whether-to-refuse” control knob, with SAE decomposition showing a shared core (591/517/421 latents at layers 9/20/31) plus category-specific tails <sup>1</sup>. RepIt finds concept-specific subspaces of 100–200 dims [^37]. Affine (translated) rather than purely directional refusal geometry [^38] and single-neuron gating cases [^39] bound the picture from both sides. **Synthesis: representation is high-dimensional; control is low-rank.** Single-direction abliteration removes the dominant shared core — which is exactly the component one would expect to carry cross-construct commitment effects.

### Stream C — Knowledge- vs safety-based refusal

The unified mechanistic analysis (213 contrastive quadruples, 6 models) reports: peak-layer KR–SR shift alignment 0.699–0.794; a common component explaining 92–95% of both shifts with residuals of 0.32–0.39; asymmetric probe transfer (SR→KR 0.80–0.86 vs KR→SR 0.58–0.63, present already in base models); type-specific grounding only in final layers — a “commit-then-specify” picture at L2–L3, explicitly not a complete circuit <sup>18</sup>. Directly opposed: near-orthogonal raw directions (mean cos 0.049 Llama-3.1-8B, −0.039 Qwen3-8B, 0.123 Gemma) and selective ablation (safety refusal 0.98→0.16 while epistemic abstention 0.82→0.88, CI spanning zero) <sup>19</sup>. See §4, CZ-1 for the reconciliation. Independent supporting structure: base-model entity-recognition SAE latents are causally repurposed by chat tuning to gate refusal [^40]; Anthropic’s biology study finds “can’t answer” features are default-*on* for any Human/Assistant prompt and inhibited by known-answer features, while the harmful-request refusal feature is built separately in finetuning [^41]; one polysemantic harm-general feature drives “cannot” phrasing [^42].

### Stream D — Side effects and verdict bias

Two independent behavioral sources establish the phenomenon. The preregistered WSE study (21,600 decisions, zero refusals in the corpus — a pure side-effect design): optimism +12.2pp (Gemma) / +7.4pp (Qwen); uncertainty-word thinning (−0.95/−2.17 per 100 words); verbalized confidence reverses sign across families (−0.008 vs +0.109, non-overlapping CIs); capability covariates rule out generic degradation — “expressed doubt lives in the report, not in the behavior” <sup>10</sup>. The security-audit case study: base Gemma-4 models graduate exactly 1 candidate (the real CVE) from a directory audit while abliterated variants flag 3–4; at scale the Heretic variant rates 96% of 144 candidates VALID vs the base’s 65% of 40, and never surfaces the real CVE; 7/7 hand-checked positives are false, including verbatim CoT–verdict dissociations (“prevents writing beyond the provided capacity” → CONFIRMED anyway); a flattery probe moves affirmations 3→10 and 8→12 — “It’s a dial, not a switch” <sup>11</sup>. Additional signals: GSM8K is the most sensitive standard benchmark (−26.5% worst case) [^43]; multi-step agentic looping reported anecdotally with clean controls [^44]. **Crucially, the side-effect literature itself states the gap: no mechanistic localization of these effects exists** <sup>10</sup>.

### Stream E — Protection methods and what they actually protect

- **SRA** (single-author preprint, unreviewed, no official code): models the dirty vector as r = s + Σα_k a_k over a Concept Atom Registry — Targets include *epistemic uncertainty*; Shields are Logic/Math/Coding/Curiosity; Confounds are negation grammar, sentiment, affirmatives — and ridge-residualizes r̃ = r − A_SC·ŵ, with λ→0 recovering the orthogonal-projection limit (I−P_C)r. Author-reported: 0–2% refusal at KL 0.044 vs 2.088 for standard abliteration <sup>17</sup>. SRA is the most sophisticated protection method *and* it ablates epistemic uncertainty by design — the exact hazard this research program is concerned with. Its anecdotal “Retreat” observation (“I cannot” → “I do not know”, then that too is ablated) is, if replicated, direct H2 evidence <sup>17</sup>.

- **grimjim lineage**: projected abliteration (protect the 1-D harmless mean), biprojected (two layers; partial refusal return — the “Hydra” effect), NPBA (row-norm preservation; NatInt 21.33 vs 18.72 base) [^45].

- **Heretic**: co-minimizes refusal count and KL-on-harmless via Optuna-TPE over direction indices and per-component kernels; protects distributional similarity only [^46].

- **Theory**: LEACE gives distributional-guarantee concept erasure [^47]; INLP/nullspace projection is the classical limit [^48]; SPLINCE extends to nonlinear concepts [^49]. CRACKEN demonstrates cross-domain spillover — orthogonal does not mean functionally independent [^50]. Only Wang et al.’s false-refusal work protects a *decision boundary* (true vs false refusal) [^51].

- **Taxonomy**: the M1–M8 ecosystem classification organizes variants [^52]; ecosystem persistence is documented in [^53].

**Gap G1 (protection):** no method protects uncertainty/abstention/negative-verdict/tool-routing mechanisms. **Gap G2:** no abliteration method has been evaluated on abstention-quality or BFCL-divergence metrics.

### Stream F — Detect → route → generate circuits

“Detection Is Cheap, Routing Is Learned”: detection probes are accurate everywhere, routing is lab-specific and fragile, cross-model transfer fails (cos 0.004), and Yi-1.5-9B shows “detection present; routing never installed” (max L3) <sup>7</sup>. “How Alignment Routes”: in Qwen3-8B a gate head (L17.H17, post-detection) drives amplifier heads (L22.H7, L23.H2, L22.H4) and carrier heads (L30–35); gate direct logit attribution is \<1% yet interchange necessity is p\<0.001 (sufficiency 0.3%); the motif appears across 12 models / 6 labs / 2B–72B with lab-specific head identities; cipher bypass collapses gate necessity 70–99%, and plaintext-gate injection rescues 48% of refusals; dose-response runs REFUSAL→EVASION→FACTUAL (max L4) <sup>8</sup>. “From Detection to Refusal”: Harmful Detection Heads (early/mid) → Safety Neurons (MLP mediators) → Refusal Heads (generation), patching closing ≤70.6% of the pathway gap, and weight scaling +26.5% safety at 1.7% utility cost across 6 models (max L4) <sup>9</sup>. The one peer-reviewed anchor: harmfulness is represented at instruction tokens, refusal at post-instruction tokens; steering dissociates them via reply-inversion; jailbreaks suppress the refusal signal while the harm signal stays high (max L3) <sup>22</sup>. On the epistemic side, the closest analog — Hidden Error Awareness — finds probes at 0.95 AUROC but steering and patching *fail*: “diagnostic, not causal” [^54]. Circuit-reuse methodology (78% head overlap across tasks; repair 49.6%→93.7%) offers the decisive template for testing whether two constructs share a circuit [^55].

### Stream G — Tool-calling mechanisms

Tool *identity* is linearly readable from the last prompt token (2nd-to-last layer, 2–3 queries per tool) and steerable (83–100% tool switches), with the causal component localized to the target tool’s first-token unembedding row; base models encode tool identity (69–82% cosine readout vs 2–10% by generation); multi-turn degrades (−30/+10pp); PCA’s “small subspace” claim fails matched-prompt controls and is disowned by the authors <sup>13</sup>. *Whether-to-call* is a separate single direction, readable from the \<tool_call\> opener logprob, tunable α-sweep from 0→1 call rate, and — critically — *knowledge-selective*: ablating it collapses the known/unknown call gap from +0.26 to +0.02, i.e., the signal distinguishing known from unknown questions travels along this direction; which-tool routing is preserved <sup>12</sup>. One tool-agent safety paper (ASA) was withdrawn over an author dispute — do not cite its findings [^56]. Behavioral anchors: necessity discrimination AUROC 0.89–0.96 with Probe&Prefill cutting calls −48% at 1.7% accuracy cost [^57]; necessity-vs-action probes are near-orthogonal in late layers (Knowing-Doing Gap) [^58]; syntactic tool-call validity stays \>93% post-abliteration (Willing-but-Unable) [^59]. **Nobody has measured refusal-direction × whether-to-call geometric overlap, nor abliteration’s effect on call rates or abstention.**

### Literature table

| Work | Year | Model(s) | Construct studied | Representation | Intervention | Causal strength | Relevance to our hypothesis | Limitations |
|----|----|----|----|----|----|----|----|----|
| Arditi et al. <sup>5</sup> | 2024 | Llama-2/3, Qwen, Gemma 7–70B | Safety refusal (C1) | Single DIM direction | Ablation, weight orthogonalization, activation addition | L3 | Defines the edit under study; selection criteria | Topic confound <sup>6</sup>; semantics unclear; TruthfulQA degradation |
| Petrov <sup>6</sup> | 2026 | Multiple | Extraction confounds | Topic-matched contrasts | — | L2 | Load-bearing critique of H5 | Negative result on one contrast family |
| Joad et al. <sup>1</sup> | 2026 | Llama, Gemma | 11 refusal categories | Multi-direction + SAE core/tail | Directional ablation | L3 | Shared 1-D knob = H2-friendly | Category taxonomy may be incomplete |
| Wollschläger et al. <sup>2</sup> | 2025 | Several | Concept cones | Cone dim 5–7, RepInd | — | L2 | Orthogonality ≠ independence (kills naive projection) | No causal tests |
| Piras et al. <sup>3</sup> | 2026 | Several | Refusal subspace | SOM k≈5–7 | — | L2 | Convergent dimensionality | Cluster-count sensitivity |
| Zhao et al. <sup>22</sup> | 2025 | Llama-3, others | C2 vs C1 separation | Token-position split (t_inst vs t_post) | Steering, reply inversion | L3 | Detect ≠ decide template; jailbreak mechanism | Steering only, no patching |
| Wang et al. <sup>51</sup> | 2025 | Several | False refusal | True/false refusal vectors | Ablation | L3 | Only decision-boundary protection | Narrow construct |
| Unified KR/SR <sup>18</sup> | 2026 | Llama-3-8B, Qwen2.5-7B, Gemma-2-9B (base+Seq-KS) | C1 vs C4 | Common component 0.92–0.95; commit-then-specify | Probe transfer, projection | L2–L3 | Strongest pro-shared-structure evidence | Authors disclaim circuit; unmatched-pair critique applies |
| Aaliyan et al. <sup>19</sup> | 2026 | Llama-3.1-8B, Qwen3-8B, Gemma | C1 vs C4 orthogonality | Control-subtracted shifts | Selective ablation | L3 | Strongest contra-H1 evidence | Workshop paper; construct definitions differ from <sup>18</sup> |
| Ferrando et al. <sup>40</sup> | 2025 | Gemma-2 | Chat-vs-base refusal gating | SAE latents (entity recognition) | Latent steering | L3–L4 | Post-training repurposes base circuitry | Single family |
| Anthropic Biology <sup>41</sup> | 2025 | Claude | Default-on “can’t answer” | Feature circuits | Feature attribution | L3–L4 | Abstention as default; refusal built separately → H2 | Proprietary model, partial sufficiency |
| Templeton et al. <sup>42</sup> | 2024 | Claude | Harm feature | Polysemantic SAE feature | Feature clamping | L3 | Single-feature “cannot” drive | Polysemanticity |
| clearbluejar <sup>11</sup> | 2026 | Gemma-4-26B/31B + abliterated variants | Verdict bias (C6) | — | Behavioral audit + flattery probe | L0 | The motivating phenomenon, verbatim dissociations | Blog; small n; single domain |
| Fafuła <sup>10</sup> | 2026 | Gemma, Qwen (+abliterated) | Disposition side effects | — | Preregistered behavioral battery (21,600 decisions) | L0 | Confirms side effects independent of refusal; confidence sign reversal | Explicitly no mechanistic grounding |
| Young <sup>43</sup> | 2025 | Several | Capability sensitivity | — | Behavioral | L0 | GSM8K worst-case −26.5%; KL–refusal r=0.87 | No mechanism |
| SRA (Cristofano) <sup>17</sup> | 2026 | Llama, Qwen | Protected abliteration | Concept-atom spectral decomposition | Ridge residualization | L3 | State-of-the-art protection; targets uncertainty (!); “The Retreat” | Single-author, unreviewed, no code |
| grimjim <sup>45</sup> | 2024–25 | Llama, Qwen | Protected abliteration | Harmless-mean projection | Projected/biprojected/NPBA | L3 | Practitioner state of practice; Hydra effect | Blog/Gist; no decision-construct protection |
| Heretic <sup>46</sup> | 2025 | Many | Automated abliteration | Direction index + kernels | Optuna-TPE KL co-minimization | L3 | Protects distribution similarity only | No mechanism protection |
| Frank (Routing) <sup>7</sup> | 2026 | 12+ models | Detect vs route | Probes, nulls, LOCO-CV | — | L3 | Routing is learned/lab-specific; transfer fails | L3 ceiling |
| Frank (Gate) <sup>8</sup> | 2026 | Qwen3-8B + 11 others | Safety routing circuit | Gate+amplifier+carrier heads | Interchange, injection | L4 | Only L4 shared-controller test; dose-response | Single group; unreplicated |
| Chu/Sun/Weng <sup>9</sup> | 2026 | 6 models | Detect→route→generate | HDH→SN→RH pathway | Patching, weight scaling | L4 | Three-stage pathway; practical +26.5% safety | Head identities model-specific |
| Hidden Error Awareness <sup>54</sup> | 2026 | Several | Epistemic detection | Probes 0.95 AUROC | Steering/patching (fail) | L1 (causal fails) | The epistemic analog of detection-is-cheap | “Diagnostic, not causal” |
| Merullo et al. <sup>55</sup> | 2024 | GPT-2 | Circuit reuse | Head overlap | Repair/patching | L4 | Template for shared-circuit test (H2 decisive) | Small model |
| Ji et al. (VUF) <sup>27</sup> | 2025 | Llama-3.1-8B, Mistral-7B, Qwen2.5-7B | C5 expression | Single verbal-uncertainty direction | Steering | L2–L3 | Expression/representation separable; ~30% hallucination cut | Moderate corr with semantic uncertainty |
| Stolfo et al. [^60] | 2024 | Llama | Confidence regulation | Neurons | Ablation | L3 | Confidence has dedicated units | Calibration ≠ commitment |
| Yona et al. <sup>28</sup> | 2024 | Gemini, GPT | C5 faithfulness | — | Prompting | L0 | Hedges unfaithful to intrinsic uncertainty | Behavioral only |
| Zhou et al. [^61] | 2023 | GPT-family | Epistemic markers | — | Prompt injection | L0 | Markers swing accuracy \>80% without knowledge change | Mimicry interpretation |
| Gekhman et al. [^62] | 2024 | PaLM/Pythia-class | Hallucination origin | — | SFT on unknowns | L0 (training-dynamics) | Affirmative bias is *installed* by SFT | Training-level, not activation-level |
| R-Tuning [^63] | 2024 | LLaMA-2, Mistral | C4 training | — | Refusal-aware SFT | L0 | Abstention generalizes as meta-skill | No mechanism |
| Kadavath et al. [^64] | 2022 | Anthropic models | Self-knowledge | — | P(True)/P(IK) elicitation | L0 | Behavioral baseline for self-evaluation | Elicited outputs, not internals |
| Azaria & Mitchell [^65] / Orgad [^66] / Geom-Correctness <sup>24</sup> | 2023–26 | Mistral, Llama | C3 internal signal | Probes 0.80–0.97 AUC | — | L1 | Internal correctness ≠ output | Contested by [^67] |
| Seo/Xiao/Chi <sup>67</sup> | 2025 | Several | Probe critique | Selectivity analyses | — | L1 | Privileged self-knowledge contested | — |
| Tian et al. <sup>35</sup> / Xiong et al. <sup>36</sup> | 2023–24 | GPT-4, ChatGPT, Claude | Verbalized calibration | — | Elicitation | L0 | Calibrated-yet-overconfident tension (CZ-7) | Format-dependent |
| Persona vectors [^68] / Vennemeyer [^69] / Sharma [^70] | 2023–25 | Llama, Qwen | Sycophancy/persona (H4) | Persona directions; sycophancy split | Steering | L2–L3 | H4 supported as real but *not one thing* — against simple H4 | Construct fuzziness |
| Zheng et al. <sup>29</sup> | 2024 | 20 LLMs | Verdict format bias | Token priors on option IDs | — | L0 | H3 (label-token artifact) is real — must counterbalance | MCQ-only |
| Acquiescence Bias [^71] | 2025 | 5 models | Yes/no bias | — | Framing battery | L0 | Token-level “no” bias — contradicts naive acquiescence | Legal-domain tasks |
| Wu et al. <sup>13</sup> | 2026 | Gemma, Llama, Qwen | C9 which-tool | Pairwise DIM tool directions | Steering | L3 | Tool identity readable/steerable; base-model encoding | Multi-turn degradation; PCA claim retracted |
| Chen et al. <sup>12</sup> | 2026 | Qwen3-4B, Llama-3.1-8B | C8 whether-to-call | Single direction at opener token | Ablation, α-sweep | L3 | Knowledge-selective commit direction — H2 analog in tool domain | Two models |
| When2Tool <sup>57</sup> / Knowing-Doing <sup>58</sup> | 2025–26 | Several | C8 necessity | Probes AUROC 0.89–0.96 | Probe&Prefill | L1–L3 | Necessity vs action dissociation | Probe-level |
| AgentAbstain <sup>14</sup> | 2026 | Frontier models | C10 | — | Paired act/abstain eval | L0 | Abstention independent of capability (59.5% best) | Benchmark, not mechanism |
| AgentHarm <sup>33</sup> | 2025 | Several | Chat→agent refusal transfer | — | Agentic jailbreak | L0 | Chat refusal doesn’t transfer; forced calls suppress refusal | Scaffolding confounds |
| Willing-but-Unable <sup>59</sup> | 2026 | Abliterated models | Tool syntax post-edit | — | BFCL-style eval | L0 | Syntax \>93% intact post-abliteration — decision quality unmeasured | Syntax-only |
| BFCL <sup>15</sup> / τ-bench <sup>16</sup> / ToolSandbox [^72] / API-Bank [^73] | 2024–26 | Many | C8–C10 measurement | — | Benchmarks | L0 | Define the measurement blind spot (irrelevance = 10% of BFCL v4) | Abstention-blind by design |
| MiniCPM5 card/config <sup>20</sup> <sup>21</sup> | 2026 | MiniCPM5-1B/2B | Target model | Vanilla LlamaForCausalLM | — | — | Feasibility: 42L/2048d, ChatML+XML tools, Base/SFT/RL ladder | transformers≥5.6 pin vs TL 2.x |
| Marks & Tegmark [^74] / Hewitt & Liang [^75] / Makelov [^76] / Heimersheim & Nanda [^77] / Geiger DAS [^78] | 2019–24 | Several | Methodology | DIM vs probes; patching validity | — | — | The causal-inference guardrails for §8 | — |

*(Stream assignment note: peer-reviewed anchors are NeurIPS 2025* <sup>22</sup>*, ICLR 2024* <sup>29</sup> <sup>36</sup> <sup>70</sup>*, ICLR 2025* <sup>51</sup> <sup>40</sup> <sup>66</sup>*, ICML 2025* <sup>2</sup>*, NAACL 2024* <sup>63</sup>*, TACL 2025* [^79]*, ACL 2025* [^80]*, EMNLP 2023–24* <sup>28</sup> <sup>61</sup> <sup>35</sup> <sup>62</sup>*; the 2026 arXiv mechanistic papers* <sup>18</sup> <sup>10</sup> <sup>17</sup> <sup>7</sup> <sup>8</sup> <sup>9</sup> <sup>13</sup> <sup>12</sup> *are preprints, several with partial venue confirmation; practitioner sources* <sup>11</sup> <sup>45</sup> <sup>46</sup> <sup>52</sup> *are blogs/tools and are cited as such.)*

## 4. Contradictions in the literature — and their methodological causes

**CZ-1 (the crux): shared vs orthogonal safety/epistemic refusal.** <sup>18</sup> finds a 92–95% common component; <sup>19</sup> finds mean cos ≈ 0.05 and selective ablation. The reconciliation is methodological, and each half of it is itself a finding: (i) *extraction recipe* — <sup>18</sup> uses raw cross-dataset DIM shifts, which include any shared commit component; <sup>19</sup> uses control-subtracted per-concept shifts, which remove it. (ii) *Pair matching* — unmatched pairs let topic/length/style confounds inflate raw alignment (the Petrov critique <sup>6</sup>). (iii) *Layer choice* — safety signal peaks ~L22, epistemic ~L9 in <sup>19</sup>’s models; comparing at a single “peak refusal layer” biases toward safety. (iv) *Construct definition* — “epistemic refusal” in <sup>19</sup> is abstention on unanswerables (C4), while <sup>18</sup>’s KR mixes knowledge-boundary detection (C3) and abstention (C4). **Both can be simultaneously true: raw directions correlate through a shared commit component (H2), while concept-purified residuals are orthogonal (contra strong-H1).** This is exactly the discrimination our experiment must operationalize.

**CZ-2: cone dimensionality vs one-knob control.** Resolved (§3 Stream B): representation high-dimensional, control low-rank. Not a contradiction — but it *predicts* that single-direction edits have side effects concentrated on constructs sharing the knob.

**CZ-3: transferability vs lab-specificity of routing.** <sup>7</sup> shows cross-model transfer fails (cos 0.004); <sup>9</sup> shows the same three-stage motif in 6 models. Resolution: the *motif* transfers; the *component identities* do not. Consequence for MiniCPM5: expect a gate-like structure somewhere mid-stack, but find it de novo — do not import Qwen head indices.

**CZ-4: confidence sign reversal.** Abliteration moves verbalized confidence down in Gemma (−0.008) and up in Qwen (+0.109), non-overlapping CIs <sup>10</sup>. Unresolved. Interpretation: the *disposition* shift (affirmation bias) is cross-family consistent, while its *verbal expression* is family-specific — consistent with expression and decision being separate knobs (VUF <sup>27</sup>).

**CZ-5: privileged self-knowledge.** Probes read correctness at 0.80–0.97 AUC <sup>65</sup> <sup>66</sup> <sup>24</sup>; critiques show probes exploit question-side regularities and that retrieval-error hallucinations are internally indistinguishable from correct answers <sup>67</sup>. All evidence is L1. Practical rule: probe accuracy is hypothesis-generating only; every probe claim needs Hewitt–Liang selectivity controls <sup>75</sup>.

**CZ-6: yes-bias vs no-bias.** Sycophancy work assumes acquiescence bias <sup>70</sup>; a five-framing study finds a token-level *“no”* bias instead <sup>71</sup>; selection bias attaches to option-ID tokens <sup>29</sup>. Resolved to a design constraint: bias lives on *surface tokens* (H3 is real but partial), so verdict tasks must counterbalance label tokens, paraphrase, and measure token priors explicitly.

**CZ-7: verbalized confidence, calibrated or overconfident?** <sup>35</sup> reports ~50% relative ECE improvement over logits for RLHF models; <sup>36</sup> [^81] report pervasive overconfidence. Format- and generation-dependent; not load-bearing for H1–H6, but it disqualifies verbalized confidence as the sole behavioral metric for caution.

## 5. Best current mechanistic model

Assembling the convergent evidence (Streams B, C, F, G plus Insight 1–2, 7), the model best supported as of September 2026 is a **four-stage architecture with a shared, low-rank, post-training-installed commitment stage**. We present it as the working model, not as established fact; no component of the epistemic branch has L5 evidence, and the whole diagram is falsified or refined by the experiments in §8–§10.

INPUT (instruction tokens) POST-INSTRUCTION / PRE-OUTPUT\
┌───────────────────────────┐ ┌──────────────────────────────────────────┐\
│ DETECTION (cheap, │ │ GENERATION (specify) │\
│ pre-existing) │ │ │\
│ │ │ refusal phrasing heads \[34\] │\
│ harm features \[8\]\[20\] │──┐ │ IDK/hedge surface form \[37\] │\
│ entity/knowledge latents │ │ │ tool XML scaffold \[72\]\[110\] │\
│ \[18\]\[19\] │ │ ▲ │\
│ error-awareness probes │ │ │ type-specific grounding (final layers │\
│ \[35\]\[49\] │ │ │ only) \[16\] │\
└───────────────────────────┘ │ │ │\
▼ │ │\
ROUTING / COMMITMENT (learned, lab-specific, fragile) │\
┌──────────────────────────────────────────────┐ │\
│ S_commit: shared commit / abstain / reject │────────────────────────┘\
│ decision stage — low-rank (1-D knob atop │\
│ high-dim concept tails) \[3\]\[16\]\[33\] │\
│ gate+amplifier motif (safety, L4) \[33\]\[34\] │\
│ whether-to-call direction (tools) \[73\] │\
│ installed by post-training; abstention is │\
│ the base-model default \[19\]\[32\]\[58\] │\
└──────────────────────────────────────────────┘\
▲ ▲ ▲\
harm route epistemic route tool-necessity route\
(C2 input) (C3 input) (known/unknown input \[73\])

Key structural claims, each with its evidence ceiling:

1.  **Detection precedes and is dissociable from commitment** (L3: <sup>22</sup> <sup>7</sup>; L1-only for epistemic detection <sup>54</sup> <sup>24</sup>).

2.  **Commitment is a shared, low-rank stage.** The 1-D control knob atop multi-category refusal <sup>1</sup>, the 92–95% common component <sup>18</sup>, the dose-response REFUSAL→EVASION→FACTUAL under gate manipulation <sup>8</sup>, and the single knowledge-selective whether-to-call direction <sup>12</sup> are four independent observations of the same shape. (L2–L4 across the set; no L5.)

3.  **Abstention is the default; commitment is learned.** Default-on “can’t answer” features inhibited by known-answer features <sup>41</sup>; “routing was never installed” in under-aligned models <sup>7</sup>; SFT on unknowns linearly increases guessing <sup>62</sup>; chat tuning repurposes base latents <sup>40</sup>.

4.  **Specification (which refusal/abstention/verdict flavor) happens late**, in final layers and output heads <sup>18</sup> <sup>9</sup> <sup>27</sup>.

5.  **Abliteration acts on stage 2’s dominant component.** It removes the shared core while leaving concept tails <sup>1</sup>, which predicts the observed side-effect phenotype: disposition shifts on all constructs routed through S_commit (epistemic abstention, negative verdicts, plausibly tool-call restraint), with syntax and knowledge intact <sup>11</sup> <sup>10</sup> <sup>59</sup>. “The Retreat” anecdote is the qualitative signature <sup>17</sup>.

What this model deliberately does **not** assert: that r_refusal and r_caution are the same vector (rejected — CZ-1); that the gate is one attention head universally (head identities are lab-specific <sup>8</sup>); that the stage-2 shared component is a single neuron or direction rather than a low-rank subspace; that tool-call routing shares the *same* gate as safety/epistemic commitment rather than a *parallel* one (the agent extension, §11, is the test).

## 6. Hypothesis ranking H1–H6

Ranking by current evidential support, best first. Each entry: supporting evidence / contradicting evidence / missing experiment / discriminating prediction.

### Rank 1 — H2 (weak form): upstream-distinct constructs converge on a shared downstream commit/abstain/reject routing stage

- **Supporting:** commit-then-specify structure with 92–95% common component and final-layer-only type grounding <sup>18</sup>; 1-D knob over multi-category refusal <sup>1</sup>; gate+amplifier circuit with dose-response through disposition levels <sup>8</sup>; detection/routing dissociation <sup>7</sup>; default-on abstention with separately-built harm refusal <sup>41</sup>; knowledge-selective whether-to-call direction <sup>12</sup>; side-effect phenotype matching shared-core removal <sup>10</sup> <sup>11</sup>; “The Retreat” <sup>17</sup>.

- **Contradicting:** selective ablation of safety without epistemic movement in <sup>19</sup> (but see CZ-1 — control-subtraction removes the shared component by construction); whether-to-call’s causal component living in the unembedding row <sup>13</sup> rather than a mid-stack gate.

- **Missing experiment:** cross-ablation behavioral matrix (Intervention × {C1, C4, C5, C6, C8, C10}) plus circuit-reuse-style repair test <sup>55</sup> between safety refusal and epistemic abstention circuits.

- **Prediction:** refusal-direction ablation produces graded disposition shifts on epistemic abstention and negative-verdict rates proportional to each construct’s projection onto the shared component; patching the safety gate into epistemic contexts (and vice versa) partially transfers disposition; reparability of one construct’s behavior by the other’s circuit components.

### Rank 2 — H1 (weak form only): r_refusal overlaps r_caution because extraction picks up the shared routing component

- **Supporting:** raw-direction alignment between KR and SR shifts (0.699–0.794) <sup>18</sup>; the fact that DIM extraction at post-instruction positions is dominated by decision-stage signal <sup>5</sup> <sup>22</sup>; Marks–Tegmark evidence that DIM directions are more causally implicated than arbitrary probes <sup>74</sup>.

- **Contradicting:** near-orthogonal control-subtracted directions <sup>19</sup>; concept-cone independence results (orthogonality achievable, independence hard) <sup>2</sup>; topic-confound fragility of raw contrasts <sup>6</sup>.

- **Missing experiment:** the §9 minimum viable experiment — measure cos(r_refusal, r_caution) under matched minimal pairs with proper high-dimensional nulls [^82] [^83], then re-extract both directions with the shared commit component regressed out and measure again.

- **Prediction (strong H1):** residuals stay correlated after shared-component removal — we expect this to **fail**. **Prediction (weak H1):** raw cosines are significantly above the Cai–Fan–Jiang null <sup>82</sup> but collapse after control subtraction — the H2-consistent outcome. Falsifying strong H1 is a success condition of this program, not a failure.

### Rank 3 — H4 (partial): a generic assertiveness/agreeableness disposition shift explains part of the phenotype

- **Supporting:** sycophancy steering restores epistemic vigilance <sup>69</sup>; persona vectors show steerable disposition axes <sup>68</sup>; the flattery-probe dose response (“a dial, not a switch”) <sup>11</sup>; RLHF reward models prefer agreement <sup>70</sup>.

- **Contradicting:** sycophancy is not one thing — agreement and praise directions are distinct <sup>69</sup>; capability covariates are unchanged while disposition moves <sup>10</sup>; H4 alone does not explain knowledge-*selectivity* of the whether-to-call direction <sup>12</sup> or the commit-then-specify ordering <sup>18</sup>.

- **Missing experiment:** include a generic-agreeableness battery (user-opinion agreement, flattery) as a *control arm* in the cross-ablation matrix; if refusal-direction ablation moves C4/C6 but not generic agreeableness, H4 is bounded.

- **Prediction:** partial correlation — verdict bias correlates with assertiveness shifts, but epistemic abstention moves even at fixed agreeableness.

### Rank 4 — H5 (partial, methodological): dataset contamination in direction extraction inflates apparent overlap

- **Supporting:** topic-matched contrasts fail completely <sup>6</sup>; SQuAD-2.0-style unanswerables are surface-detectable (“entity salads, false premises”) [^84]; provenance contamination demonstrably inverts conclusions (quantizer mismatch flipped an “excision of doubt” pilot; stale chat templates mangled prompts) <sup>10</sup>.

- **Contradicting:** confounds explain *magnitude*, not the existence of the common component (which survives within-paper controls in <sup>18</sup>); probe-transfer asymmetry exists in base models where no refusal tuning data exists <sup>18</sup>.

- **Missing experiment:** the matched-minimal-pair datasets of §8 with topic/length/style balancing and split-half reliability floors; report alignment under progressively stricter controls as a dose curve.

- **Prediction:** raw overlap estimates shrink monotonically with control strictness; the H2-consistent residue is a shared *late* component, not an early conceptual one.

### Rank 5 — H6 (unfalsified, unpinned): a distributed nonlinear circuit that linear directions only shadow

- **Supporting:** cones are 5–7 dimensional <sup>2</sup> <sup>3</sup>; amplifier *sets* and carrier heads rather than single components <sup>8</sup>; Makelov’s demonstration that linear patching can produce illusory sufficiency via dormant pathways <sup>76</sup>; SPLINCE’s premise that some concepts are only nonlinearly erasable <sup>49</sup>.

- **Contradicting:** the empirical sufficiency of 1-D control <sup>5</sup> <sup>1</sup> <sup>12</sup> bounds how distributed the *controllable* core can be.

- **Missing experiment:** Boundless-DAS/pyvene distributed alignment search over subspaces rather than directions <sup>78</sup>; test whether a rank-k (k≈5–7) intervention outperforms rank-1 at equal norm.

- **Prediction:** rank-k edits dominate rank-1 edits in side-effect-free refusal removal; the recovered subspace aligns with the concept cone.

### Rank 6 — H3 (real but smallest): output-token / linguistic artifact

- **Supporting:** verdict bias attaches to surface label tokens (option-ID priors <sup>29</sup>; token-level “no” bias <sup>71</sup>); expression and representation of uncertainty are separable knobs <sup>27</sup>; epistemic markers flip behavior without knowledge change <sup>61</sup>.

- **Contradicting:** the verdict-bias dissociations show *reasoning* text affirming against the model’s own analysis, not merely label priors <sup>11</sup>; side effects appear in free-form decisions with no label tokens <sup>10</sup>.

- **Missing experiment:** the positional control of §8 — measure effects with verdict labels counterbalanced, paraphrased, and replaced by free-text commitment; H3 predicts effects shrink to label-token conditions only.

- **Prediction:** a minority share of the effect (token-prior magnitude), with the disposition shift surviving label rotation.

## 7. The exact research gap

One paragraph, stated precisely: The literature contains (a) robust behavioral evidence that refusal-direction editing shifts decision disposition under uncertainty — optimism, thinned uncertainty language, and verdict bias — with capabilities otherwise intact <sup>11</sup> <sup>10</sup>; (b) convergent but *contradictory* geometric evidence on whether safety refusal and epistemic abstention share representation <sup>18</sup> <sup>19</sup>; and (c) L4 circuit fragments for the safety branch only <sup>8</sup> <sup>9</sup>. What does not exist anywhere is a **causal discrimination between the two candidate mechanisms — direct geometric overlap of refusal and caution directions versus upstream-distinct constructs converging on a shared downstream commit/abstain/reject routing stage** — because no study has (i) extracted both constructs’ directions under matched minimal pairs with proper high-dimensional nulls and control subtraction, (ii) run the cross-ablation behavioral matrix (Intervention × {safety refusal, uncertainty, abstention, negative verdict, tool call, tool abstain}) to map the edit’s causal footprint, or (iii) localized the commitment stage for epistemic constructs at L4–L5. The gap extends to agents: no study has abliterated a model and measured the divergence between tool-call syntax (intact <sup>59</sup>) and tool-call *judgment* — whether-to-call rates on known/unknown splits and abstention on insufficient-information or dangerous-irreversible tasks <sup>14</sup> <sup>31</sup> <sup>32</sup> — even though whether-to-call is known to be a separate, knowledge-selective, steerable direction <sup>12</sup>. Closing this gap on MiniCPM5 is the contribution.

## 8. Proposed experiment for MiniCPM5 (design only — no implementation)

### 8.0 Model and provenance

Target: openbmb/MiniCPM5-2B (rev cd199ce3ee67549c42ef7372f809f2c63599a3e9, Apache-2.0, 42 layers, hidden 2048, GQA 16Q/2KV, pre-RMSNorm, untied embeddings, bf16, ~5 GB) <sup>20</sup>. Companions MiniCPM5-2B-Base, -SFT, -Midtrain form a training-stage ladder for §8.7. MiniCPM5-1B for fast iteration. Architecture is vanilla LlamaForCausalLM — no trust_remote_code, no MoE, no MLA, no muP scaling (those are MiniCPM4/3 quirks and do not transfer) <sup>20</sup> [^85]. Chat template is ChatML (\<\|im_start\|\>/\<\|im_end\|\>); tools are JSON signatures in a \<tools\> system block; tool calls are plain-text XML \<function name="…"\>\<param …\>…\</param\>\</function\> whose structural tokens are single vocab ids (2–21, 130072–130081) — giving exact token anchors for whether-to-call measurement <sup>21</sup>. Tooling: TransformerLens v3 TransformerBridge (smoke-test against the transformers≥5.6 pin early; raw HF hooks are a validated fallback at 0.999998 cross-backend cosine parity [^86]); nnsight [^87]; pyvene/Boundless DAS <sup>78</sup>; SAELens [^88]. VRAM \<8 GB — single consumer GPU suffices.

### 8.1 Datasets (five matched minimal-pair families)

All families balanced for topic, length, and surface style; split-half reliability floor reported for every extracted direction; label tokens counterbalanced (CZ-6).

- **A. Safety** — harmful vs harmless instruction pairs, *topic-matched* per the Petrov critique (each harmful prompt paired with a harmless prompt on the same topic) <sup>6</sup>; plus HarmBench-style severity gradations.

- **B. Epistemic uncertainty** — answerable/unanswerable pairs. Prefer naturally occurring unanswerables (NQ/TyDi) and true minimal pairs (QnotA, 400 pairs; KUQP, 320 pairs) over SQuAD 2.0, whose unanswerables are surface-detectable <sup>84</sup> <sup>26</sup> [^89] [^90]; SelfAware categories for coverage <sup>25</sup>. Each item tagged with the model’s own knowledge state (known/unknown by sampling consistency) to separate C3 (internal uncertainty) from C4 (abstention behavior).

- **C. Verdict** — claim–evidence pairs with identical evidence distributions and three balanced conditions whose correct verdicts are CONFIRM / REJECT / ABSTAIN (insufficient evidence). Labels rotated across synonym sets and positions; token priors measured and reported (Zheng controls) <sup>29</sup> <sup>71</sup>. Security-audit-style items reproduce the clearbluejar setting <sup>11</sup>.

- **D. Caution** — complete vs incomplete vs conflicting evidence versions of the same questions; measure hedging density and verbalized confidence separately from verdict (C5 vs C6) <sup>27</sup> <sup>28</sup>.

- **E. Tool use** — five conditions over matched task stems: tool *required* / *optional* / *irrelevant* / *unavailable* / *dangerous-irreversible* (irreversible actions with a consent checkpoint à la ST-WebAgentBench) <sup>32</sup>. Irrelevant-condition design follows BFCL irrelevance but scored for *what the model does instead* (abstain-with-explanation vs hallucinated call), the dimension BFCL’s 10% weighting ignores <sup>15</sup> <sup>30</sup> <sup>31</sup>. Tool-call competence (AST correctness when a call is made, C9) is measured separately from restraint (C10) and propensity (C8).

### 8.2 Controls

1)  Topic/length/style balancing (H5); (ii) label-token counterbalancing and paraphrase rotation (H3); (iii) generic agreeableness/flattery battery as a control arm (H4) <sup>69</sup> <sup>70</sup>; (iv) random-direction and random-subspace interventions matched in norm (null interventions); (v) high-dimensional geometric nulls — Cai–Fan–Jiang cosine null (\|cos\| ≈ N(0, 1/d); max-over-n-pairs correction √(2 log n / p)) and Absil–Edelman–Koev principal-angle null for subspace comparisons <sup>82</sup> <sup>83</sup>; (vi) probe selectivity controls (Hewitt–Liang) on every probe claim <sup>75</sup>; (vii) chat-template integrity checks — template hash pinned; a mangled-template arm as a positive control for provenance contamination <sup>10</sup>.

### 8.3 Activation positions and layers

Extraction at three anchor families, exploiting MiniCPM5’s deterministic template <sup>21</sup>: **P1** — last instruction token (\<\|im_end\|\> of the user turn; the t_inst site where harmfulness is represented <sup>22</sup>); **P2** — assistant boundary token (\<\|im_start\|\>assistant\n; the t_post-inst refusal site <sup>5</sup> <sup>22</sup>); **P3** — decision-relevant generation tokens (first verdict label token for family C; the \<function opener token for family E — a single vocab id, making whether-to-call logprob measurement exact <sup>12</sup> <sup>21</sup>). Suffix-anchored alignment (never absolute indices), left-padding for batched reads; variable-length \<tools\> blocks shift everything downstream, so all cross-prompt comparisons anchor on P1/P2/P3. Layers: full sweep (42 layers), with dense sampling in the early-mid band (epistemic peak ~L9-scale region per <sup>19</sup>, scaled to depth) and mid-late band (safety peak ~L22-scale; whether-to-call L21–24 on Qwen3-4B <sup>12</sup> — expect MiniCPM5-specific peaks, do not import indices).

### 8.4 Direction extraction and subspace methods

Per construct and per (position, layer): (a) DIM with matched-pair means <sup>5</sup> <sup>74</sup>; (b) control-subtracted DIM (each construct’s direction after regressing out the shared commit component — the CZ-1 reconciliation operationalized <sup>18</sup> <sup>19</sup>); (c) logistic-regression probe directions with selectivity controls <sup>75</sup>; (d) rank-k subspace extraction (PCA/SVD on centered difference matrices, k chosen by split-half stability, expecting k≈5–7 <sup>2</sup> <sup>3</sup>); (e) SAE/crosscoder feature overlap on the commit-band layers (train MiniCPM5 SAEs via SAELens — none exist publicly) <sup>88</sup>. Geometry battery: cosine + layerwise trajectory; principal angles (Björck–Golub) between construct subspaces [^91]; projection fraction ‖Q₁ᵀQ₂‖²_F/min(k); probe-transfer matrix (both directions, both constructs — the <sup>18</sup> asymmetry replicated under matched pairs); SVCCA only with dim\>n safeguards, never bare CKA [^92] [^93]. **All geometric results are reported against the nulls of 8.2(v) and labeled L2 — hypothesis-generating.**

### 8.5 Causal tests (the core)

1.  **Cross-ablation behavioral matrix.** Interventions: {refusal-direction ablation (rank-1), refusal-subspace ablation (rank-k), caution-direction ablation, uncertainty-direction ablation, whether-to-call-direction ablation, random-direction controls, weight-orthogonalization variant}. Measured outcomes: {safety refusal rate (C1), uncertainty probe persistence (C3, L1 only), abstention rate (C4), hedging/caution metrics (C5), verdict distribution on family C (C6), tool-call rate on known/unknown splits (C8), which-tool AST accuracy (C9), tool abstention/restraint quality (C10), agreeableness battery (H4 arm), standard capability metrics (reported but explicitly *not* treated as sufficiency evidence)}. Every cell reported with CIs; negative results reported.

2.  **Activation addition (sufficiency).** Add each extracted direction at its extraction site and measure the converse behavioral shift (induce refusal/caution/abstention/no-call), dose-response curve per direction <sup>5</sup> <sup>8</sup>.

3.  **Activation patching / interchange.** Noising (necessity) and denoising (sufficiency) runs per Zhang–Nanda best practices (continuous metrics, symmetric token replacement) [^94] <sup>77</sup>; resample ablation; cross-construct interchange — patch the safety-commit activation into epistemic contexts and vice versa (the H2-decisive test); Boundless DAS subspace interchange for H6 <sup>78</sup>; Makelov safeguards (test for dormant-pathway illusions) <sup>76</sup>.

4.  **Component localization.** Following the gate+amplifier template <sup>8</sup> and the HDH→SN→RH template <sup>9</sup>, but discovered de novo on MiniCPM5: head-level attribution over the commit band, MLP-neuron screening for mediator units, carrier/output-head analysis at P3. Circuit-reuse quantification between the safety circuit and the epistemic circuit (head-overlap % and repair test: can the safety circuit’s components restore abstention behavior on epistemic prompts, à la Merullo’s 49.6%→93.7% repair <sup>55</sup>).

5.  **Knockout.** Component knockout of localized gate candidates; measure the cross-ablation matrix again — an H2 gate knockout should move *all* routed constructs; a construct-specific component knockout should move only its construct.

### 8.6 Protection arm (the user’s r_edit question, treated as a variable)

Construct the protected set S_protected = S_uncertainty ∪ S_caution ∪ S_negative-verdict ∪ S_tool-call ∪ S_tool-selection ∪ S_tool-abstention as **subspaces** (rank-k, not directions) and compare protection operators: (a) hard orthogonal projection (I − P_S)r_refusal — the baseline the literature shows is theoretically inadequate (orthogonality ≠ independence <sup>2</sup> <sup>50</sup>); (b) ridge-residualized protection r̃ = r − A_S·ŵ across λ, with λ→0 recovering (a) <sup>17</sup>; (c) LEACE-style distributional erasure of refusal with S_protected constrained <sup>47</sup>; (d) DAS-discovered protected subspaces <sup>78</sup>. Handle collinearity explicitly (ridge λ selection by stability; report the collinearity spectrum of S_protected) and over-protection (refusal-rate recovery vs protection strength tradeoff curve). Success metric = the full 8.5(1) matrix, not refusal rate alone.

### 8.7 Training-stage ladder

Repeat extraction and the key cross-ablation cells on -Base, -SFT, -Midtrain, and the RL checkpoint. Predictions under H2 + the default-abstention model <sup>41</sup> <sup>7</sup> <sup>62</sup>: base model shows abstention-default features and weak routing; SFT installs the commit policy (and the affirmative bias, per Gekhman); RL sharpens it. This converts a one-checkpoint study into a developmental account of where the shared routing comes from — and where verdict bias comes from.

### 8.8 Behavioral metrics and statistics

Primary behavioral metrics per construct as in 8.5(1); plus uncertainty-word density per 100 words <sup>10</sup>; CoT–verdict consistency score (does the verdict match the model’s own stated reasoning — the verdict-bias instrument <sup>11</sup>); calibration splits (logit vs verbalized vs behavioral — channels measured separately since they move independently <sup>35</sup> <sup>10</sup>). Statistics: preregistered analysis plan; bootstrap CIs; multiple-comparison correction across the matrix; effect sizes with the family-difference caveat (sign of *expression* effects may reverse across families — the disposition shift is the invariant <sup>10</sup>); power analysis targeting the C4/C6 cells. **Ablations:** extraction position (P1/P2/P3), layer band, rank-k, template variant, seed, and checkpoint stage.

### 8.9 Measurement warning (binding)

Perplexity / MMLU / GSM8K / KL / BFCL stability is reported for completeness and is explicitly **not** evidence that capabilities or decision mechanisms survived: syntax survives while skepticism dies (insight 6) — tool-call validity stays \>93% post-abliteration while call judgment is unmeasured <sup>59</sup>; capability covariates stay flat while disposition shifts <sup>10</sup>; BFCL scores irrelevance at 10% and never what the model does instead <sup>15</sup>. Any “no damage” claim must come from the disposition-first battery of 8.5, not from standard benchmarks.

## 9. Minimum viable experiment (falsify H1)

**Goal:** falsify or bound *strong* H1 (direct geometric overlap r_refusal ≈ α·r_caution + β·r_refusal-specific) with the smallest sufficient design. One checkpoint (MiniCPM5-2B), two dataset families (A and D-mini/B-mini), geometry only, no circuit work. ~Days, one GPU.

1.  Extract r_refusal from dataset A (topic-matched harmful/harmless pairs) at P2, full layer sweep <sup>5</sup> <sup>6</sup>.

2.  Extract r_caution and r_uncertainty from matched caution/uncertainty pairs (families D and B) at the same positions and layers.

3.  Measure: cosine trajectories across layers; principal angles between rank-k subspaces; projection fractions — each against Cai–Fan–Jiang and Absil–Edelman–Koev nulls, with max-over-comparisons correction <sup>91</sup> <sup>82</sup> <sup>83</sup>.

4.  **The decisive step:** regress the shared commit component out of both direction sets (control subtraction per <sup>19</sup>’s recipe) and re-measure. Strong H1 predicts residual overlap survives; H2 predicts collapse to null.

5.  One behavioral cell only: ablate r_refusal, measure abstention-rate shift on family B — a single L3 check that the geometry (if present) has behavioral consequence.

**Outcomes:** residual overlap survives → strong H1 alive, proceed to causal tests; residual overlap collapses while raw overlap was significant → strong H1 falsified, weak-H1/H2 pattern confirmed, the interesting question becomes routing (§10); raw overlap at null from the start → extraction confound (H5) dominates, redesign pairs before any further claims. Any of the three is a publishable negative/positive result — falsifying H1 is a success condition.

## 10. Strong experiment (distinguish direct overlap from shared downstream routing)

**Goal:** separate H1 from H2 causally, at L4–L5. Builds on §8 and the §9 outcome.

1.  **Cross-ablation matrix (8.5(1)) in full** — the H2 signature is graded, projection-proportional disposition shifts across all routed constructs from a refusal-only edit; the H1 signature is movement confined to constructs whose *purified* directions overlap r_refusal.

2.  **Cross-construct interchange (the decisive test).** Patch safety-commit activations (P2, commit band) into epistemic-decision contexts and vice versa <sup>94</sup> <sup>77</sup> <sup>78</sup>. H2 predicts partial disposition transfer in *both* directions (shared stage); H1 predicts transfer only where raw geometry overlaps, and symmetric with the geometry. Dose-response mapping (REFUSAL→EVASION→FACTUAL analog for the epistemic axis: ANSWER→HEDGE→ABSTAIN) following Frank’s gate-manipulation design <sup>8</sup>.

3.  **Circuit localization of the epistemic commit stage, de novo on MiniCPM5.** Head attribution, MLP-mediator screening, output-head analysis at P3; then the circuit-reuse quantification: head overlap between the safety-routing circuit and the epistemic-routing circuit, and the repair test — ablate the epistemic circuit’s putative gate, patch in the safety circuit’s gate, measure recovery (Merullo template: 78% overlap, 49.6%→93.7% repair is the reference effect size <sup>55</sup>). \>50% repair = strong shared-circuit evidence (L4); failure to repair despite geometric overlap = direct-overlap account survives.

4.  **Sufficiency chain to L5.** A candidate circuit reaches L5 only when (a) knockout eliminates the disposition shift, (b) activation addition of the gate signal induces it, (c) interchange transfers it cross-construct, and (d) the account survives Makelov-style dormant-pathway controls <sup>76</sup> and causal-scrubbing-style resample tests [^95]. Expect to land at L4; claim L5 only if all four hold.

5.  **Rank structure.** Rank-k vs rank-1 interventions at equal norm (H6): if rank-1 suffices for the full side-effect phenotype, the controllable core is one-dimensional even if representation is not <sup>1</sup> <sup>2</sup>.

6.  **Preregistration** of predictions 1–5 before data collection, including the explicit statement that H2 is the favored prior (insight 1–2) and the falsification criteria for each hypothesis.

## 11. Agent extension (whether-to-call, which-tool, tool-abstention, irreversible-action confirmation)

**Why this is a discriminating test, not an add-on** (insight 4): whether-to-call is formally the same construct type as refusal and epistemic abstention — a knowledge-gated commit/abstain decision — and is already known to be a separate, steerable, knowledge-selective direction <sup>12</sup>. Under H2, refusal-direction editing should move call-rate disposition even though the edit never touched tool data; under construct-specific accounts, it should not. MiniCPM5’s native XML tool calling with single-token structural markers makes the measurement exact at the \<function opener position <sup>21</sup> <sup>12</sup>.

**Design (extends dataset family E):** - **Whether-to-call (C8):** call rate on required/optional/irrelevant splits, crossed with the model’s known/unknown knowledge state (replicating the <sup>12</sup> gap measure: does ablation collapse the known/unknown call gap on MiniCPM5, and does *refusal-direction* ablation also collapse it? — the cross-domain H2 prediction). - **Which-tool (C9):** AST accuracy and tool-identity direction geometry <sup>13</sup>; predicted *intact* under refusal editing (separate mechanism) — a built-in dissociation control: competence preserved while propensity shifts. - **Tool abstention / restraint (C10):** unavailable-tool items (does the model say “I can’t” or hallucinate a call?) <sup>31</sup>; insufficient-information items (ToolSandbox-style, scored on what the model does instead, which BFCL ignores) <sup>72</sup> <sup>15</sup>; dangerous-irreversible items with consent checkpoints (does the model ask before irreversible actions?) <sup>32</sup>. All run under the cross-ablation matrix — nobody has ever measured an abliterated model’s abstention profile. - **Chat-vs-agent boundary:** run the same decision items in chat format and in agent scaffold format; chat refusal rates do not transfer to agents and forced tool calls suppress refusal <sup>33</sup> — the routing stage’s context-dependence is itself measurable here. - **Metrics:** call-rate curves under α-steering of r_edit; abstention quality (paired act/abstain scoring à la AgentAbstain <sup>14</sup>); CoT–action consistency (does the stated plan match the emitted call?); syntactic validity reported but flagged as the <sup>59</sup> blind spot. - **Safety note:** the dangerous-irreversible arm makes this extension dual-use sensitive; design it as an evaluation, not a capability demonstration, and report overcalling rates as the primary risk metric.

## 12. Publication-level claim boundaries

What may be claimed at each evidentiary stage — the discipline this literature repeatedly fails:

**After geometry only (§9 complete).** Permitted: “Under matched minimal pairs and high-dimensional nulls, refusal and caution directions in MiniCPM5 exhibit \[measured\] alignment at \[layers\], which \[survives / collapses under\] control subtraction; geometry is consistent with \[hypotheses\] and inconsistent with \[hypotheses\].” Forbidden: any causal verb (“the direction *causes*”, “refusal *is* caution”); any claim about mechanism; any cross-model generalization. Geometry generates hypotheses <sup>91</sup> <sup>82</sup> <sup>75</sup>.

**After the cross-ablation matrix (§8.5(1), §10.1).** Permitted: “Refusal-direction ablation causally shifts disposition on constructs {list}, with effect sizes {…}, while leaving {syntax/knowledge/which-tool accuracy} intact; the footprint is \[consistent with a shared routing stage / confined to geometrically overlapping constructs\].” This is an L3 causal-behavioral claim about the *edit*, not yet about *the circuit*. Forbidden: naming components; claiming the shared stage is localized; claiming protection methods “work” (the protection arm shows tradeoffs, not safety). Note the boundary precedent: the side-effect literature reached exactly this level and stopped, explicitly disavowing mechanism <sup>10</sup> — going one level further is the contribution.

**After circuit localization (§10.2–10.5).** Permitted (only with all four sufficiency-chain conditions): “A shared commit/routing circuit in MiniCPM5, comprising {components}, is necessary and sufficient for disposition control across safety refusal and epistemic abstention, as shown by knockout, addition, cross-construct interchange, and repair.” At L4 (likely outcome): claim “circuit-level evidence for a shared routing stage,” name components as *candidates*, and state that necessity+sufficiency was established at the interchange level, not full L5. Forbidden regardless: “the mechanism of refusal” tout court (family-specificity <sup>10</sup> <sup>8</sup> and single-model scope forbid it); silent generalization from MiniCPM5 to other families (head identities are lab-specific <sup>8</sup>); causal language retrofitted onto the L1–L2 inputs (probes, cosines) used along the way. Negative results (e.g., repair fails, H1 falsified) are reported at the same prominence — falsifying H1 is a stated success condition.

## 13. Reproducibility plan

1.  **Model revision pinning.** openbmb/MiniCPM5-2B at sha cd199ce3ee67549c42ef7372f809f2c63599a3e9; ladder checkpoints (-Base, -SFT, -Midtrain) pinned by sha likewise; official openbmb/\* repos only — community abliterated derivatives (26 exist) are *objects of study*, never substrates, because their provenance is unverifiable (the quantizer-mismatch and stale-template incidents show community-checkpoint provenance inverting conclusions <sup>10</sup>). The DSpark draft model uses custom code and is excluded <sup>20</sup>.

2.  **Tokenizer and chat template as experimental artifacts.** Pin tokenizer_config.json and chat_template.jinja by content hash <sup>21</sup>; record the exact jinja rendering of every prompt family; treat template variation as a *registered intervention arm*, not an afterthought — template state is part of the causal graph of refusal <sup>10</sup>.

3.  **Precision and decoding.** bf16 weights; fixed generation config (temperature, top-p, max tokens, seed list) logged per run; greedy for all direction-extraction and matrix cells; EOS set {\</s\>, \<\|im_end\|\>}; parser-side truncation at first completed \</function\> for tool calls (natural stopping is weak: stopped_cleanly ≈ 0.15) <sup>21</sup>.

4.  **Software environment.** transformers version pinned (≥5.6 per card; if TransformerLens 2.x forces \<5, record the fork and validate activation parity against raw HF hooks, expecting ≈0.999998 cosine <sup>86</sup>); TransformerLens/nnsight/pyvene/SAELens versions pinned; full lockfile and CUDA/cuDNN versions archived.

5.  **Datasets.** Every prompt family frozen with content hashes (SHA-256 per file); generation scripts for synthetic pairs archived; dataset version numbers for external sources (QnotA, KUQP, SelfAware, NQ/TyDi snapshots) <sup>25</sup> <sup>26</sup> <sup>89</sup> <sup>90</sup>.

6.  **Hook locations and normalization.** Module paths logged exactly (model.layers\[i\] post-block residual, self_attn.o_proj input, mlp output, model.norm input); activation normalization convention (RMSNorm eps 1e-6, pre-norm) stated; position anchors (P1/P2/P3) defined by token id, not index; padding side recorded.

7.  **Statistical protocol.** Preregistration (hypotheses, predictions, falsification criteria, correction method) timestamped before data collection; seeds enumerated; bootstrap CI code released.

8.  **Release bundle.** Extraction code, eval harness, frozen datasets + hashes, extracted directions/subspaces, preregistration, and a RESULTS.md separating confirmatory from exploratory analyses. Replication target: at least one additional checkpoint of the ladder and one non-MiniCPM control family before any cross-family claim.

## 14. Final reading order

Read in this sequence. Each entry carries the exact question to hold in mind while reading.

**Essential (5):**

1.  **Arditi et al. 2024, “Refusal in Language Models Is Mediated by a Single Direction”** <sup>5</sup> — *Question: which of the selection criteria (induce\>0, KL\<0.1, layer \<0.8L) actually identify “refusal,” and which merely identify “the direction that changes behavior most cheaply”?* Read App. L.3 (post-abliteration incoherence) as carefully as the main claims.

2.  **“A Unified Mechanistic Analysis of Knowledge- and Safety-Based Refusals” (arXiv:2609.00760)** <sup>18</sup> — *Question: is the 92–95% common component a shared concept or a shared decision stage — and does the SR→KR probe-transfer asymmetry (0.80–0.86 vs 0.58–0.63) distinguish those?* This is the strongest evidence for shared structure; understand its extraction recipe before trusting it.

3.  **Aaliyan et al., “Two Refusals or One?” (ICML 2026 workshop)** <sup>19</sup> — *Question: what exactly does control subtraction remove, and could the removed component be the shared commit stage itself?* The direct contradiction of \#2; the reconciliation (CZ-1) is the crux of your H1/H2 design.

4.  **Frank, “How Alignment Routes” (arXiv:2604.04385)** <sup>8</sup> — *Question: what would the gate+amplifier motif look like for an epistemic commit decision, and which of Frank’s interchange tests (necessity p\<0.001, sufficiency 0.3%, dose-response REFUSAL→EVASION→FACTUAL) can you port to abstention?* The methodological template for §10.

5.  **Fafuła, “Abliteration Is Not a Scalpel” (arXiv:2607.17427)** <sup>10</sup> — *Question: which cells of your cross-ablation matrix does its preregistered battery already cover, and what would the same battery show if the disposition shift is mechanistically localized rather than diffuse?* The phenomenon anchor; note its explicit disavowal of mechanistic grounding — your gap.

**Second tier (5):**

6.  **Joad et al., “There Is More to Refusal Than a Single Direction” (arXiv:2602.02132)** <sup>1</sup> — *Question: if control is 1-D while representation is high-dim, what exactly does single-direction abliteration remove — the concept, or the shared knob?*

7.  **Zhao et al. (NeurIPS 2025, arXiv:2507.11878)** <sup>22</sup> — *Question: the t_inst/t_post-inst separation gives you P1/P2 for free — does the reply-inversion steering template port to epistemic caution replacing harmfulness?* The only peer-reviewed circuit-adjacent anchor.

8.  **Chen et al., “Tunable Tool-Call Rates…” (arXiv:2608.25198)** <sup>12</sup> — *Question: is the knowledge-selective whether-to-call direction the tool-domain instance of your hypothesized S_commit — and does the known/unknown call-gap collapse replicate on MiniCPM5 under refusal-direction ablation?*

9.  **SRA (arXiv:2601.08489)** <sup>17</sup> — *Question: why does the best protection method classify epistemic uncertainty as a* target*, and is “The Retreat” (cannot → do-not-know → gone) a real, replicable signature of shared routing?* Read critically: single author, no code, unreviewed.

10. **Makelov et al. + Heimersheim & Nanda** <sup>76</sup> <sup>77</sup> — *Question: which of your planned patching claims would survive dormant-pathway controls, and how do noising/denoising asymmetries map onto your necessity/sufficiency chain?* The guardrails that keep §10 honest.

**Blogs / repos (practitioner layer — cite as such):**

11. **clearbluejar, “Don’t Let Abliteration Abliterate Your Bug Hunting”** <sup>11</sup> — *Question: which exact CoT–verdict dissociations can you turn into a quantitative consistency metric?* The motivating observation; treat magnitudes as low-confidence.

12. **grimjim’s abliteration Gists (projected / biprojected / NPBA)** <sup>45</sup> — *Question: what does each variant protect, and why does partial refusal return (Hydra) suggest the direction is re-derived downstream?*

13. **Heretic (p-e-w)** <sup>46</sup> — *Question: KL-on-harmless is the only protected quantity — what would the optimizer do to your S_protected constructs if you added them to the loss?*

14. **abliteration.org M1–M8 taxonomy** <sup>52</sup> — *Question: where in the taxonomy does a decision-mechanism-protecting method sit? (Answer: nowhere yet.)*

15. **MiniCPM5-2B model card + chat_template.jinja + tokenizer_config.json (openbmb, HF)** <sup>20</sup> <sup>21</sup> — *Question: which template tokens give you exact P1/P2/P3 anchors, and what breaks if transformers\<5 loads this config?* Read the raw files, not the marketing.

*Note: bracketed superscript numbers refer to the footnoted references. Backing research artifacts: /mnt/agents/output/research/refusal_dim01.md … refusal_dim12.md, refusal_cross_verification.md, refusal_insight.md. Conflict zones CZ-1, CZ-4, CZ-5, CZ-7 are documented as genuinely unresolved in the field and are targets of the proposed experiments, not defects of this review.*

[^1]: Joad et al. (2026). There Is More to Refusal Than a Single Direction: multi-category directions, shared control knob, SAE core/tail. arXiv:2602.02132.. https://arxiv.org/abs/2602.02132

[^2]:

[^3]:

[^4]:

[^5]: Arditi, A., Obeso, O., Syed, A., Paleka, D., Panickssery, N., Gurnee, W., Nanda, N. (2024). Refusal in Language Models Is Mediated by a Single Direction. arXiv:2406.11717.. https://arxiv.org/abs/2406.11717

[^6]: Petrov (2026). Topic-matched contrast critique of refusal-direction extraction. arXiv:2603.22061.. https://arxiv.org/abs/2603.22061

[^7]: Frank (2026). Detection Is Cheap, Routing Is Learned. arXiv:2603.18280.. https://arxiv.org/abs/2603.18280

[^8]: Frank (2026). How Alignment Routes: gate+amplifier+carrier motif; interchange necessity; dose-response. arXiv:2604.04385.. https://arxiv.org/abs/2604.04385

[^9]: Chu, Sun & Weng (2026). From Detection to Refusal: detection heads → safety neurons → refusal heads; weight scaling +26.5% safety at 1.7% utility cost. arXiv:2609.00051.. https://arxiv.org/abs/2609.00051

[^10]: Fafuła (2026). Abliteration Is Not a Scalpel: preregistered 21,600-decision study of disposition side effects. arXiv:2607.17427.. https://arxiv.org/abs/2607.17427

[^11]:

[^12]: Chen et al. (2026). Tunable Tool-Call Rates: a knowledge-selective whether-to-call direction distinct from which-tool routing. arXiv:2608.25198.. https://arxiv.org/abs/2608.25198

[^13]: Wu et al. (2026). Tool Calling is Linearly Readable and Steerable (tool-identity directions; unembedding causal component). ICML 2026. arXiv:2605.07990.. https://arxiv.org/abs/2605.07990

[^14]:

[^15]:

[^16]:

[^17]: Cristofano (2026). SRA: concept-guided spectral cleaning of refusal directions; ridge residualization; Concept Atom Registry; "The Retreat". arXiv:2601.08489.. https://arxiv.org/abs/2601.08489

[^18]: A Unified Mechanistic Analysis of Knowledge- and Safety-Based Refusals (2026). Commit-then-specify; common component 0.92–0.95; asymmetric probe transfer. arXiv:2609.00760.. https://arxiv.org/abs/2609.00760

[^19]:

[^20]: OpenBMB (2026). MiniCPM5-2B model card, config.json, HF API metadata (sha cd199ce3…; LlamaForCausalLM; 42L/2048d; Apache-2.0). huggingface.co/openbmb/MiniCPM5-2B.. https://huggingface.co/openbmb/MiniCPM5-2B

[^21]: OpenBMB (2026). MiniCPM5-2B chat_template.jinja and tokenizer_config.json (ChatML; XML tool calls; structural tokens ids 2–21, 130072–130081).. https://huggingface.co/openbmb/MiniCPM5-2B/raw/main/chat_template.jinja

[^22]: Zhao et al. (2025). Harmfulness detection is not refusal: token-position separation and reply-inversion steering. NeurIPS 2025. arXiv:2507.11878.. https://arxiv.org/abs/2507.11878

[^23]:

[^24]: Geometric Structure of Correctness Representations in Language Models (2026). Probes 0.80–0.97 AUC vs outputs 0.44–0.64. arXiv:2602.08159.. https://arxiv.org/abs/2602.08159

[^25]: Yin et al. (2023). Do Large Language Models Know What They Don't Know? (SelfAware, 2,337). ACL 2023. arXiv:2305.18153.. https://arxiv.org/abs/2305.18153

[^26]:

[^27]: Ji et al. (2025). Calibrating Verbal Uncertainty as a Linear Feature (VUF). arXiv:2503.14477.. https://arxiv.org/abs/2503.14477

[^28]: Yona, Aharoni & Geva (2024). Can LLMs Faithfully Express Their Intrinsic Uncertainty in Words? EMNLP 2024. arXiv:2405.16908.. https://arxiv.org/abs/2405.16908

[^29]: Zheng et al. (2024). Large Language Models Are Not Robust Multiple Choice Selectors (option-ID token priors). ICLR 2024 spotlight. arXiv:2309.03882.. https://arxiv.org/abs/2309.03882

[^30]:

[^31]:

[^32]:

[^33]:

[^34]: OpenAI (2023). GPT-4 Technical Report: post-training reduces calibration. arXiv:2303.08774.. https://arxiv.org/abs/2303.08774

[^35]: Tian et al. (2023). Just Ask for Calibration. EMNLP 2023. arXiv:2305.14975.. https://arxiv.org/abs/2305.14975

[^36]: Xiong et al. (2024). Can LLMs Express Their Uncertainty? ICLR 2024. arXiv:2306.13063.. https://arxiv.org/abs/2306.13063

[^37]:

[^38]:

[^39]:

[^40]:

[^41]:

[^42]:

[^43]: Young (2025). KL–refusal correlation (r=0.87); GSM8K worst-case degradation −26.5%. arXiv:2512.13655.. https://arxiv.org/abs/2512.13655

[^44]:

[^45]:

[^46]:

[^47]:

[^48]:

[^49]:

[^50]:

[^51]:

[^52]:

[^53]: Redistribution as the Persistence Layer: the Heretic/TransformerLens abliteration ecosystem (2026). arXiv:2609.05241. --- \*Research artifacts backing this report: /mnt/agents/output/research/refusal_dim01.md … refusal_dim12.md, refusal_cross_verification.md, refusal_insight.md. Conflict zones CZ-1, CZ-4, CZ-5, CZ-7 are documented as genuinely unresolved in the field and are targets of the proposed experiments, not defects of this review.\*. https://arxiv.org/abs/2609.05241

[^54]: Hidden Error Awareness (2026). 0.95-AUROC error probes; steering/patching fail — "diagnostic, not causal". arXiv:2605.09502.. https://arxiv.org/abs/2605.09502

[^55]:

[^56]: ASA (2026). Agent safety alignment paper — WITHDRAWN 2026-08-28 (author dispute). arXiv:2602.04935. Not cited for findings.. https://arxiv.org/abs/2602.04935

[^57]:

[^58]:

[^59]: Willing-but-Unable (2026). Syntactic tool-call validity \>93% post-abliteration. arXiv:2606.05396.. https://arxiv.org/abs/2606.05396

[^60]:

[^61]: Zhou, Jurafsky & Hashimoto (2023). Navigating the Grey Area. EMNLP 2023. arXiv:2302.13439.. https://arxiv.org/abs/2302.13439

[^62]: Gekhman et al. (2024). Does Fine-Tuning LLMs on New Knowledge Encourage Hallucinations? EMNLP 2024. arXiv:2405.05904.. https://arxiv.org/abs/2405.05904

[^63]: Zhang et al. (2024). R-Tuning: Instructing LLMs to Say "I Don't Know". NAACL 2024 (Outstanding Paper). arXiv:2311.09677.. https://arxiv.org/abs/2311.09677

[^64]: Kadavath et al. (2022). Language Models (Mostly) Know What They Know. arXiv:2207.05221.. https://arxiv.org/abs/2207.05221

[^65]: Azaria & Mitchell (2023). The Internal State of an LLM Knows When It's Lying. Findings of EMNLP 2023. arXiv:2304.13734.. https://arxiv.org/abs/2304.13734

[^66]:

[^67]: Seo et al. (2025); Xiao et al. (2025); Chi et al. (2025). Critiques of privileged self-knowledge probes. Reviewed in arXiv:2604.12373.. https://arxiv.org/abs/2604.12373

[^68]:

[^69]:

[^70]: Sharma et al. (2024). Towards Understanding Sycophancy in Language Models. ICLR 2024. arXiv:2310.13548.. https://arxiv.org/abs/2310.13548

[^71]: Acquiescence Bias in Large Language Models (2025). Token-level "no" bias. Findings of EMNLP 2025. arXiv:2509.08480.. https://arxiv.org/abs/2509.08480

[^72]:

[^73]:

[^74]:

[^75]:

[^76]:

[^77]:

[^78]:

[^79]:

[^80]: Li et al. (2025). Knowledge Boundary of Large Language Models: A Survey. ACL 2025. arXiv:2412.12472.. https://arxiv.org/abs/2412.12472

[^81]: The Dunning-Kruger Effect in Large Language Models (2026). arXiv:2603.09985.. https://arxiv.org/abs/2603.09985

[^82]:

[^83]:

[^84]:

[^85]: MiniCPM Team (2025). MiniCPM4: Ultra-Efficient LLMs on End Devices (InfLLM v2; muP scaling — NOT in MiniCPM5). arXiv:2506.07900.. https://arxiv.org/abs/2506.07900

[^86]: Nanda & Bloom. TransformerLens; TransformerBridge (v3). Cross-backend activation parity 0.999998 documented in arXiv:2604.11050.. https://arxiv.org/abs/2604.11050

[^87]:

[^88]:

[^89]:

[^90]:

[^91]:

[^92]:

[^93]:

[^94]:

[^95]:
