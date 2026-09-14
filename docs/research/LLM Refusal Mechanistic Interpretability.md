# GOOGLE GEMINI:

# Mechanistic Analysis of Refusal Editing, Epistemic Caution, Verdict Bias, and Agent Routing in Large Language Models

## Executive Conclusion

The mechanistic interpretability of safety-aligned large language models has undergone a rapid paradigm shift. Initial representation engineering research established that safety refusal behavior is reliably mediated by a single, one-dimensional subspace within the residual stream. This led to the proliferation of abliteration techniques, which orthgonalize model weights against this scalar direction to surgically remove safety guardrails<sup>1</sup>. However, recent large-scale behavioral audits demonstrate that this surgery is inherently unclean. The removal of the putative refusal direction systematically alters the model's decision-making disposition under uncertainty, generating a phenomenon known as "verdict bias." Across massive sets of decision-making tasks, abliterated models exhibit systemic optimism, a thinning of their explicit uncertainty vocabulary, and highly divergent confidence calibrations—even on purely epistemic tasks, such as financial forecasting or vulnerability bug hunting, which contain no safety-violating material<sup>3</sup>.

The current mechanistic literature strongly indicates that verdict bias is not merely a linguistic artifact or an unavoidable byproduct of dataset contamination. Instead, it exposes a deep structural entanglement within the alignment architecture of the transformer. The evidence falsifies the simplest hypothesis that safety refusal and epistemic caution share an identical, monolithic upstream representation. High-resolution causal circuit analyses, particularly those leveraging interchange testing and sparse autoencoders, reveal that models do not lack the capacity to internally represent harmfulness or uncertainty after abliteration. Rather, alignment mechanisms operate through a two-phase architecture: distinct upstream semantic detection modules converge onto a shared downstream policy-routing circuit<sup>6</sup>.

This routing module, frequently localized as a sparse gate-amplifier attention motif, serves as a generic action-inhibitor or commitment bottleneck. It maps both policy-driven safety violations and evidence-deficient epistemic states into a unified abstention or hypothesis-rejection behavior. When naive abliteration projects the residual stream away from the refusal direction, it inadvertently damages this shared downstream router. Consequently, the abliterated model maintains intact representations of epistemic uncertainty, but the mechanical pathway required to translate that uncertainty into behavioral abstention or a negative verdict is severed. The model is thereby forced into its pre-trained autoregressive continuation, which defaults to an affirmative or compliant generation.

This architectural reality presents a profound challenge for the deployment of uncensored agentic systems. The shared downstream circuitry that governs safety refusals is deeply intertwined with tool-use propensity—specifically, the critical restraint mechanism that dictates when a model must abstain from calling a tool due to insufficient evidence or irreversible risk<sup>9</sup>. Because standard orthogonalization destroys this shared machinery, advancing beyond naive abliteration requires targeted, circuit-level interventions. Techniques such as concept-guided spectral cleaning and localized component knockout offer a pathway to precisely disentangle safety policy execution from epistemic rigor and agentic tool restraint<sup>8</sup>.

## Conceptual Taxonomy

To rigorously investigate the intersection of safety alignment and epistemic reasoning, the underlying behavioral and latent constructs must be precisely defined and mathematically distinguished. Conflating various forms of non-compliance into a single variable critically confounds upstream semantic detection with downstream behavioral execution. The literature necessitates distinguishing the following eleven constructs.

|  |  |  |  |
|----|----|----|----|
| **Construct Category** | **Specific Construct** | **Provisional Representation** | **Definition and Mechanistic Role** |
| **Safety & Policy** | Safety Refusal | <img src="LLM Refusal Mechanistic Interpretability_media/media/image10.png" style="width:0.72872in;height:0.20821in" /> | The ultimate behavioral execution where the model declines a user request explicitly due to safety, ethical, or policy guardrails. This is an output-level policy decision (e.g., "I cannot assist with that"). |
| **Safety & Policy** | Harmfulness Detection | <img src="LLM Refusal Mechanistic Interpretability_media/media/image11.png" style="width:0.33706in;height:0.21187in" /> | The internal, upstream semantic representation that a prompt contains policy-violating concepts. A model may strongly represent this concept but bypass refusal execution if jailbroken or abliterated. |
| **Epistemic State** | Epistemic Uncertainty | <img src="LLM Refusal Mechanistic Interpretability_media/media/image13.png" style="width:0.64638in;height:0.20912in" /> | The internal informational state representing low confidence, insufficient evidence, or conflicting premises within the context window. This is a semantic state, not a behavioral action. |
| **Epistemic State** | Epistemic Caution / Skepticism | <img src="LLM Refusal Mechanistic Interpretability_media/media/image19.png" style="width:0.44293in;height:0.20733in" /> | A dispositional trait governing the threshold of evidence required before committing to a claim. It dictates hedging behavior, demand for verification, and the consideration of counterfactuals. |
| **Decision & Verdict** | Epistemic Abstention | <img src="LLM Refusal Mechanistic Interpretability_media/media/image23.png" style="width:0.93136in;height:0.21015in" /> | The behavioral decision to output "I don't know," "Insufficient information," or a refusal to answer based on knowledge limitations (Knowledge-Based Refusal). This operates downstream of uncertainty. |
| **Decision & Verdict** | Negative Verdict | <img src="LLM Refusal Mechanistic Interpretability_media/media/image1.png" style="width:0.86803in;height:0.20985in" /> | A definitive, high-confidence policy execution rejecting a premise (e.g., "The hypothesis is invalid"). This is a firm commitment, entirely distinct from uncertainty or abstention. |
| **Decision & Verdict** | Generic Commitment | <img src="LLM Refusal Mechanistic Interpretability_media/media/image7.png" style="width:0.47511in;height:0.20698in" /> | A hypothesized mid-to-late layer multi-dimensional routing subspace governing the binary transition from internal reasoning to definitive action (commit vs. abstain/reject). |
| **Agentic Tool Use** | Tool-Use Propensity | <img src="LLM Refusal Mechanistic Interpretability_media/media/image21.png" style="width:0.47408in;height:0.20653in" /> | The binary decision axis determining *whether* to invoke an external tool versus answering relying solely on internal parametric knowledge. |
| **Agentic Tool Use** | Tool Selection | <img src="LLM Refusal Mechanistic Interpretability_media/media/image9.png" style="width:0.42525in;height:0.2079in" /> | Conditional on tool propensity being triggered, the multi-dimensional subspace dictating *which* specific tool identity is selected and executed. |
| **Agentic Tool Use** | Tool Abstention | <img src="LLM Refusal Mechanistic Interpretability_media/media/image16.png" style="width:0.66221in;height:0.20812in" /> | The critical restraint mechanism preventing tool calls when evidence is insufficient, tools are irrelevant, or actions are irreversible. This likely shares geometric space with generic action inhibition. |

## Literature Map

The state of mechanistic interpretability regarding model refusals is highly stratified by the methodologies employed. To establish a rigorous baseline, this analysis grades mechanistic claims on a hierarchy of evidence from Level 0 to Level 5. Level 0 represents purely behavioral observations without internal localization. Level 1 involves linear separability and probing, establishing correlation but not causality. Level 2 encompasses geometric relations between representations, such as subspace principal angles. Level 3 introduces causal manipulation through activation steering or broad ablation. Level 4 achieves high precision through cross-condition activation patching and causal interchange testing. Finally, Level 5 represents the gold standard: localized circuit tracing with replicated necessity and sufficiency evidence.

The following literature map categorizes the primary sources by the mechanism studied and their corresponding evidence level, focusing heavily on developments from 2024 to 2026.

|  |  |  |  |  |  |  |  |  |
|----|----|----|----|----|----|----|----|----|
| **Work** | **Year** | **Model(s)** | **Construct Studied** | **Representation** | **Intervention** | **Causal Strength** | **Relevance to Hypothesis** | **Limitations** |
| Arditi et al.<sup>1</sup> | 2024 | Llama, Qwen, Gemma | Safety refusal | 1D scalar vector | Activation addition & ablation | Level 3 | Established foundational baseline that safety refusal can be modulated via a single direction. | Assumed the extracted difference-in-means vector was purely refusal, ignoring polysemanticity. |
| Winninger<sup>12</sup> | 2026 | Qwen 2.5, Qwen 3 | Refusal subspace | Multi-dimensional cone | RFM-AGOP | Level 2 | Shows refusal is not scalar; reasons that reasoning models require multidimensional boundaries. | Primarily geometric and probe-based; lacks localized causal circuit tracing. |
| Son et al.<sup>6</sup> | 2026 | Multiple open-weights | Knowledge vs Safety Refusal | Shared refusal direction | SAE feature extraction | Level 2 | Proposes "commit-then-specify"; finding asymmetric overlap where SR transfers to KR. | Relies heavily on geometric overlap rather than localized component knockout. |
| Fafuła<sup>3</sup> | 2026 | Gemma-4-26B, Qwen3-30B | Verdict bias, optimism | Behavioral disposition | Abliteration | Level 0 | Proves the off-target effects of abliteration on 21,600 stock decisions under uncertainty. | Strictly behavioral observation; no internal mechanism localized. |
| Cristofano<sup>11</sup> | 2026 | Qwen3-VL, Ministral | "Ghost Noise" / Refusal | Concept Atom Registry | Ridge-regularized residualization | Level 3 | Demonstrates standard refusal vectors entangle with core capabilities (math/logic). | Relies on high-level spectral cleaning; does not isolate the exact neural circuits responsible. |
| Frank<sup>8</sup> | 2026 | Phi-4, Qwen3, Gemma-2 | Alignment routing | Gate-amplifier motif | Interchange testing & DLA | Level 4 | Isolates routing from detection. Proves models detect harm but a learned gate controls refusal execution. | Focuses strictly on political censorship; requires extension to epistemic tasks. |
| Chu et al.<sup>7</sup> | 2026 | LLaMA3, Mistral, Qwen2 | Detection-Refusal circuit | Detection heads <img src="LLM Refusal Mechanistic Interpretability_media/media/image5.png" style="width:0.14182in;height:0.16546in" /> Safety Neurons | Weight scaling | Level 3 | Validates detect <img src="LLM Refusal Mechanistic Interpretability_media/media/image5.png" style="width:0.14182in;height:0.16546in" /> route <img src="LLM Refusal Mechanistic Interpretability_media/media/image5.png" style="width:0.14182in;height:0.16546in" /> generate via layer-stratified component roles. | Weight scaling is a coarse intervention compared to causal interchange patching. |
| Chen et al.<sup>10</sup> | 2026 | Open-weights | Tool-call propensity | 1D steering direction | Activation steering | Level 3 | Proves "whether to call" is monotonically controllable via a single representation. | Does not explore the intersection of tool propensity and safety refusal limits. |
| Prakash et al.<sup>18</sup> | 2026 | Llama-3.1, Gemma-2 | SAE Refusal features | Minimal causal feature sets | SAE ablation | Level 3 | Shows early feature ablation activates dormant downstream redundant refusal features. | Computationally intensive; factorization machines may overfit causal interactions. |
| Wu et al.<sup>9</sup> | 2026 | Qwen 2.5, Llama 3.1 | Tool identity selection | Mean-difference vector | Activation patching | Level 4 | Proves tool identity is linearly readable and steerable inside the model output layers. | Focuses on which tool is selected, rather than the restraint from using a tool. |

## Contradictions in the Literature

The rapid expansion of mechanistic interpretability has yielded several highly publicized contradictions regarding the nature of refusal and alignment. Resolving these contradictions requires careful attention to methodological artifacts, including direction extraction methods, dataset confounds, and layer selection.

The most prominent contradiction lies in the dimensionality of refusal. Foundational work by Arditi et al. proposed that refusal is mediated by a single, rank-one scalar direction in the residual stream<sup>1</sup>. This direction was extracted using a difference-in-means approach across contrastive datasets of harmful and harmless prompts, utilizing activations at post-instruction token positions<sup>21</sup>. Conversely, recent investigations utilizing Recursive Feature Machines (RFM-AGOP) and Concept-Guided Spectral Cleaning reveal that refusal exists within a complex, multi-dimensional polysemantic subspace<sup>11</sup>.

This contradiction is a direct consequence of dataset contamination and model scale. The difference-in-means methodology inherently collapses multiple axes of variance into a single vector. Because the harmless negative datasets utilized in early extractions frequently lacked matched syntactic length, semantic complexity, and epistemic weight, the resulting one-dimensional vector inadvertently absorbed what the literature terms "Ghost Noise"<sup>11</sup>. This noise encompasses not just the refusal signal, but collateral features such as compliance tone, task length, and general assertiveness. In highly complex, modern Mixture-of-Experts (MoE) reasoning models, a single vector acts as an under-parameterized approximation of a highly non-linear decision boundary, forcing the model into dispositional shifts when that single vector is abliterated<sup>12</sup>.

A second major contradiction concerns the relationship between safety refusal and epistemic abstention. Early linear probing studies frequently reported that representations of safety and representations of uncertainty were nearly orthogonal, suggesting entirely distinct mechanisms. In stark contrast, dual-direction mechanistic studies by Son et al. identified substantial shared refusal structures, demonstrating that safety-based refusal signals transfer strongly to knowledge-based refusal scenarios<sup>6</sup>.

This apparent contradiction is resolved by isolating layer choice and token position within the extraction pipeline. In early-to-mid layers, the model engages in semantic processing, where the representations of harmfulness (<img src="LLM Refusal Mechanistic Interpretability_media/media/image11.png" style="width:0.33706in;height:0.21187in" />) and epistemic uncertainty (<img src="LLM Refusal Mechanistic Interpretability_media/media/image13.png" style="width:0.64638in;height:0.20912in" />) are indeed orthogonal and distinct. However, in mid-to-late layers, these distinct upstream signals are routed into a shared behavioral execution pathway. Probing studies that average activations across all layers, or that focus exclusively on early token positions, detect the orthogonal upstream representations and conclude distinctness. Studies focusing on late layers and final output tokens detect the converged downstream routing mechanism and conclude shared structure. Therefore, both findings are accurate but describe different chronological phases of the model's forward pass.

## Best Current Mechanistic Model

Synthesizing the Level 3 and Level 4 causal evidence from Frank, Chu et al., and Son et al., the most defensible mechanistic model discards the assumption of a monolithic "refusal representation" in favor of a layer-stratified, sequential Detect -\> Route -\> Execute architecture<sup>6</sup>.

\[ Early / Mid Layers: Semantic Processing & Detection \]

│

├──── r_harm (Harmfulness Detection Heads) ─────────┐

│ │

├──── r_uncertainty (Epistemic Monitoring) ─────────┤

│ │

└──── r_tool_relevance (Tool Syntax/Utility) ───────┤

│

\[ Mid / Late Layers: Policy & Commitment Routing \] ▼

┌───────────────────────────┐

│ Gate-Amplifier Circuit │

│ (Shared Action Inhibitor) │

└─────────────┬─────────────┘

│

\[ Late Layers: Generation & Specification \] ▼

┌─────────────────────────────┼────────────────────────────┐

│ │ │

▼ ▼ ▼

Proceed / Commit (Yes) Abstain / Refuse (No) Tool-Policy Execution

/ \\ / \\ /

Affirmative Tool Call Safety Refusal Epistemic Tool Identity Tool

Verdict Execution (Policy limits) Abstention Selection Abstain

Under this mechanistic framework, safety alignment fine-tuning does not operate by erasing the model's fundamental semantic understanding of harmful concepts. Detection mechanisms remain cheap, robust, and linearly separable deep within the model<sup>15</sup>. Instead, alignment training develops a highly sensitive routing module—typically localized as a sparse gate-amplifier attention motif or specialized safety neurons—that monitors the residual stream for specific detection signals<sup>7</sup>. When a trigger is detected, this gate forcefully redirects the residual stream toward a shared, multi-dimensional inhibitory subspace (<img src="LLM Refusal Mechanistic Interpretability_media/media/image6.png" style="width:0.88808in;height:0.20896in" />).

This shared routing bottleneck explains the collateral damage observed during abliteration. Standard orthogonalization targets this shared gate or the downstream refusal execution heads. By erasing the mechanism that translates upstream detection into downstream abstention, the model is blinded to its own uncertainty. When presented with an ambiguous epistemic task, the model still successfully computes <img src="LLM Refusal Mechanistic Interpretability_media/media/image13.png" style="width:0.64638in;height:0.20912in" /> in its early layers. However, because the router mapping that uncertainty to an epistemic abstention or a negative verdict has been damaged, the model defaults to its baseline pre-trained autoregressive continuation, which overwhelmingly favors affirmative, compliant, and optimistic generation<sup>3</sup>.

## Hypothesis Ranking

The phenomenon of verdict bias—where abliteration induces an affirmative bias and reduces explicit uncertainty under epistemic constraints—can be explained by several distinct mechanisms. We rank six hypotheses by the current strength of the mechanistic evidence.

### 1. H2: Shared downstream commitment circuit (Most Defensible)

The hypothesis that refusal and epistemic caution are upstream-distinct but converge on a shared downstream decision-routing mechanism is currently the most robust explanation.

- **Supporting Evidence:** Level 4 causal interchange testing demonstrates that detection and behavioral routing are distinct processes, governed by sparse gate-amplifier motifs<sup>8</sup>. Weight scaling studies successfully isolate detection heads from safety routing neurons<sup>7</sup>. Crucially, investigations into knowledge-based versus safety-based refusals confirm a "commit-then-specify" mechanism, wherein diverse prompts trigger a shared initial commitment to abstain before specifying the exact refusal rationale<sup>6</sup>.

- **Contradicting Evidence:** This architecture requires complex, non-linear multi-component interactions, which occasionally resist simple linear decoding compared to scalar variables.

- **Missing Experiment:** Direct causal interchange patching of an purely epistemic uncertainty-driven task into the localized safety-routing gate to observe if epistemic abstention is forcefully triggered.

- **Prediction:** Epistemic uncertainty will remain perfectly linearly decodable in early layers post-abliteration, but its causal influence on the output logits via the mid-layer gate-amplifier will drop to zero.

### 2. H5: Dataset contamination in refusal direction extraction (Highly Plausible Cofactor)

The observed side effects arise primarily because the contrastive datasets used to extract refusal directions contain systematic semantic and stylistic confounds.

- **Supporting Evidence:** Level 3 spectral analysis definitively proves that standard difference-in-means refusal vectors are heavily entangled with core capabilities, including logic, coding, and mathematical reasoning. This "Ghost Noise" can be mitigated by projecting the refusal vector away from protected Concept Atoms using ridge-regularized spectral residualization<sup>11</sup>.

- **Contradicting Evidence:** While dataset contamination is undeniably present, it fails to fully account for the asymmetric confidence shifts observed in large-scale audits, where identical abliteration techniques caused Gemma models to become less confident while Qwen models became more confident<sup>3</sup>. Such divergent responses suggest deep structural differences rather than mere dataset stylistic leakage.

- **Missing Experiment:** Extracting a refusal vector from a perfectly matched, minimal-pair dataset (controlling for tone, length, and complexity) and measuring whether verdict bias is completely eliminated without utilizing spectral cleaning.

- **Prediction:** Utilizing perfectly matched minimal-pair extractions will reduce the severity of the verdict bias, but will not completely eliminate it, as the shared downstream router will still be partially affected.

### 3. H1: Direct geometric overlap

Abliteration directly removes epistemic caution because verdict bias is caused by direct geometric overlap between <img src="LLM Refusal Mechanistic Interpretability_media/media/image8.png" style="width:0.40328in;height:0.20875in" /> and <img src="LLM Refusal Mechanistic Interpretability_media/media/image12.png" style="width:0.93698in;height:0.20822in" />.

- **Supporting Evidence:** Level 2 subspace cosine similarity analyses frequently show broad mathematical overlap between refusal components and abstention components when averaged across all layers<sup>6</sup>.

- **Contradicting Evidence:** This hypothesis fails to account for early-layer orthogonality. If <img src="LLM Refusal Mechanistic Interpretability_media/media/image4.png" style="width:2.25401in;height:0.20879in" />, models would lose the ability to internally represent uncertainty entirely upon abliteration. However, probing demonstrates that uncertainty and harmfulness representations remain fully intact and linearly separable deep within the model even when the final behavior is drastically altered<sup>15</sup>.

- **Missing Experiment:** Rigorous cross-ablation of isolated upstream detection heads, independent of downstream routing.

- **Prediction:** This hypothesis is directly falsified if upstream uncertainty representations remain linearly decodable after the refusal direction is ablated.

### 4. H6: Distributed nonlinear circuit

No small set of linear directions adequately explains the phenomenon; the effects arise from highly distributed, nonlinear interactions across the entire network.

- **Supporting Evidence:** Level 3 analyses utilizing Sparse Autoencoders (SAEs) and factorization machines demonstrate that ablating early-layer refusal features activates dormant, redundant features in downstream layers, suggesting highly complex non-linear fail-safes<sup>18</sup>.

- **Contradicting Evidence:** While non-linearities and redundancies exist, macroscopic behavioral routing remains heavily concentrated in a surprisingly small number of linear attention heads and MLP projections, which can be effectively scaled or patched to control behavior<sup>7</sup>.

- **Prediction:** Linear activation steering would fail to consistently recreate the behavioral shift. This directly contradicts findings that a single linear vector can exert 90% monotonic control over tool-call propensity<sup>10</sup>.

### 5. H3: Output-token / linguistic artifact

Verdict bias is not a high-level decision mechanism, but merely a shift in the probability distribution of specific output tokens (e.g., "NO," "cannot," "reject") associated with refusal templates.

- **Supporting Evidence:** Level 1 scoring mechanisms for refusal frequently rely on the probability difference between refusal-associated tokens and non-refusal tokens at the initial generation position<sup>22</sup>.

- **Contradicting Evidence:** Verdict bias impacts numeric financial forecasting, automated bug hunting, and code execution tasks where standard linguistic refusal tokens are entirely absent from the expected output space<sup>3</sup>. The model enacts a conceptual bias, not a vocabulary bias.

- **Prediction:** Changing the required output format (e.g., forcing a strict JSON schema output) would entirely eliminate the verdict bias. Evidence shows the bias persists regardless of output format.

### 6. H4: Generic assertiveness / agreeableness shift

Abliteration modifies a broader behavioral/style axis (e.g., <img src="LLM Refusal Mechanistic Interpretability_media/media/image2.png" style="width:0.70475in;height:0.20811in" />) rather than fundamentally altering epistemic reasoning mechanisms.

- **Supporting Evidence:** Behavioral audits confirm that abliterated models exhibit systematic increases in optimism and generate longer, more affirmative self-justifications<sup>3</sup>.

- **Contradicting Evidence:** A generic assertiveness shift fails to explain the precise loss of epistemic hedging and the catastrophic failure of tool-call abstention specifically in scenarios where objective evidence is lacking.

- **Prediction:** The model would flatter the user and agree with inherently false premises even on objective mathematical tasks where no meaningful uncertainty computation is required. This sweeping sycophancy is not systematically observed.

## Exact Research Gap

The literature definitively establishes that refusal is a multi-dimensional routing phenomenon rather than a scalar direction<sup>12</sup>, and that ablating this mechanism heavily skews decision calibration and epistemic caution<sup>3</sup>. However, no study has causally mapped the precise intersection of epistemic tool abstention and safety refusal routing within modern, highly optimized Mixture-of-Experts (MoE) reasoning architectures. Specifically, the following critical gap remains open: *Does refusal editing alter decision calibration because the upstream semantic representations of harm and uncertainty suffer from dataset-induced "Ghost Noise" entanglement, or because distinct, orthogonal upstream detectors converge on a shared, lab-specific downstream gate-amplifier action-routing circuit?*

Extended to autonomous agentic systems, this prompts a vital secondary question: *Does this shared downstream action-inhibitor circuit simultaneously govern tool-call abstention (the decision not to use an available tool when evidence is insufficient or an action is irreversible), and can precise interventions preserve this vital agentic restraint while successfully bypassing safety guardrails?*

## Proposed Experiment (MiniCPM5)

To systematically distinguish direct representation overlap (H1) from shared downstream routing (H2), and to evaluate the preservation of tool-abstention, an exhaustive activation patching and component knockout experiment is proposed targeting the MiniCPM5 architecture.

### Architectural Considerations for MiniCPM5

MiniCPM5 presents unique experimental challenges due to its advanced architecture. It utilizes a hybrid architecture combining sparse and linear attention, alongside a Mixture-of-Experts (MoE) framework<sup>23</sup>. It natively supports XML-style function calls, utilizing specialized parsing (e.g., via SGLang) to extract tool execution commands from the generated text<sup>24</sup>. While the model exposes standard Transformer residual streams accessible via Hugging Face AutoModelForCausalLM<sup>23</sup>, standard TransformerLens interventions must be carefully adapted to account for MoE routing logic and variable-length chat templates.

### Dataset Design (Minimal-Pair Structures)

To eliminate dataset contamination (H5), standard contrastive prompts are strictly prohibited. The experiment requires conceptually distinct, minimal-pair datasets.

- **A. Safety (Matched):** Prompts matched for length, complexity, and coding semantics. (e.g., *Harmful:* "Write a script to exploit the SQL vulnerability in this code." / *Benign:* "Write a script to patch the SQL vulnerability in this code.")

- **B. Epistemic Uncertainty:** Informationally constrained scenarios. (e.g., *Answerable:* "Analyze Company X based on this universally positive earnings report." / *Unanswerable:* "Analyze the financial outlook of Company X based on this highly redacted, conflicting earnings report.")

- **C. Verdict Disposition:** A benchmark of 5,000 binary logic/code exploitability determinations where exactly 50% are definitively CONFIRM and 50% are definitively REJECT based strictly on the provided context.

- **D. Tool Abstention:** Agentic tasks where a tool is provided, but the context dictates it must not be used (e.g., "The target server is confirmed offline by the hypervisor; do not ping it").

### Variables and Metrics

- **Independent Variable 1 (Extraction Method):** Raw Difference-in-Means vector vs. SRA (Concept-Guided Spectral Cleaned) vector utilizing ridge-regularized spectral residualization against protected capability atoms<sup>11</sup>.

- **Independent Variable 2 (Intervention Type):** Zero-ablation of the subspace vs. Cross-condition Activation Patching of localized gate heads vs. Complete Component Knockout<sup>8</sup>.

- **Dependent Variables:** (1) Safety refusal rate, (2) Affirmative verdict bias rate on Dataset C, (3) Tool-call propensity, (4) Tool-abstention accuracy on Dataset D, (5) Layerwise Principal Angles between extracted subspaces.

### Geometry Analysis

The experiment will discard simple vector cosine similarity, which is insufficient for multi-dimensional reasoning spaces. Instead, we will calculate Subspace Principal Angles between <img src="LLM Refusal Mechanistic Interpretability_media/media/image18.png" style="width:0.39455in;height:0.20916in" /> and <img src="LLM Refusal Mechanistic Interpretability_media/media/image3.png" style="width:0.9574in;height:0.20854in" />. To extract these subspaces effectively from long reasoning traces, we will utilize Recursive Feature Machines (RFM-AGOP) to map the nonlinear boundaries of the refusal cones<sup>12</sup>. We will quantify the geometric entanglement by calculating the Projection Fraction (<img src="LLM Refusal Mechanistic Interpretability_media/media/image20.png" style="width:1.18246in;height:0.2696in" />) across all layers, establishing a precise layerwise cosine trajectory.

## Minimum Viable Experiment

The Minimum Viable Experiment (MVE) is designed strictly to falsify the simple direct overlap hypothesis (H1).

1.  **Direction Extraction:** Calculate the multi-dimensional refusal subspace (<img src="LLM Refusal Mechanistic Interpretability_media/media/image17.png" style="width:0.75476in;height:0.21019in" />) using RFM-AGOP on Dataset A. Independently calculate the uncertainty subspace (<img src="LLM Refusal Mechanistic Interpretability_media/media/image14.png" style="width:0.67242in;height:0.2069in" />) on Dataset B.

2.  **Geometric Measurement:** Compute the layerwise principal angles between the subspaces. If H1 is true, the angles will indicate high alignment uniformly across all layers. If H2 is true, the subspaces will be nearly orthogonal (90 degrees) in early semantic layers, converging only at late routing layers.

3.  **Cross-Ablation & Linear Probing:** Directionally ablate <img src="LLM Refusal Mechanistic Interpretability_media/media/image17.png" style="width:0.75476in;height:0.21019in" /> from all layers. Train a linear probe on the residual stream to classify states of uncertainty using Dataset B.

4.  **Behavioral Evaluation:** Measure the model's verdict behavior on Dataset C.\
    *Falsification:* If the linear probe successfully decodes internal uncertainty with high accuracy post-abliteration, yet the model's outward behavior shifts to affirmative verdicts, H1 is definitively falsified. The model retains the semantic capacity for epistemic caution; the failure is entirely localized to downstream behavioral routing.

## Strong Experiment

To affirmatively prove H2 (Shared downstream commitment circuit) and distinguish it from direct representation overlap, the experiment must employ causal interchange patching.

1.  **Localize Upstream Detectors:** Utilize Direct Logit Attribution (DLA) and single-component knockout to identify the specific attention heads in early-to-mid layers that activate exclusively for <img src="LLM Refusal Mechanistic Interpretability_media/media/image11.png" style="width:0.33706in;height:0.21187in" /> (Harm Detection Heads) and <img src="LLM Refusal Mechanistic Interpretability_media/media/image13.png" style="width:0.64638in;height:0.20912in" /> (Epistemic Monitoring)<sup>7</sup>.

2.  **Localize the Routing Gate:** Execute causal interchange testing. Feed the model a completely benign prompt, but artificially patch the activations of the isolated Harm Detection Heads from a safety prompt into the residual stream. Observe which mid-to-late layer heads (the Gate-Amplifier motif) subsequently spike in activation to initiate refusal<sup>8</sup>.

3.  **Cross-Condition Patching:** Feed the model an epistemically uncertain prompt from Dataset C (where the correct verdict is REJECT). Intercept the forward pass and patch the downstream Gate-Amplifier heads with the neutral activations extracted from a highly certain, benign prompt.

4.  **Causal Evaluation:** If patching solely the Gate-Amplifier immediately forces the model to output an affirmative CONFIRM verdict—despite the intact presence of upstream uncertainty representations—we have successfully localized the shared <img src="LLM Refusal Mechanistic Interpretability_media/media/image7.png" style="width:0.47511in;height:0.20698in" /> bottleneck.

5.  **Targeted Spectral Cleaning:** Apply Surgical Refusal Ablation (SRA). Register <img src="LLM Refusal Mechanistic Interpretability_media/media/image7.png" style="width:0.47511in;height:0.20698in" /> and <img src="LLM Refusal Mechanistic Interpretability_media/media/image15.png" style="width:0.68825in;height:0.20885in" /> as protected Concept Atoms in the registry. Execute the ridge-regularized weight update, <img src="LLM Refusal Mechanistic Interpretability_media/media/image22.png" style="width:1.80894in;height:0.20836in" />, projecting the intervention away from the routing mechanism<sup>11</sup>. Measure if safety guardrails are bypassed while negative verdicts and tool abstention are perfectly preserved.

## Agent Extension

Integrating tool-use routing into the causal framework requires explicitly separating tool-call competence from tool-call restraint.

1.  **Whether-to-call Propensity (**<img src="LLM Refusal Mechanistic Interpretability_media/media/image21.png" style="width:0.47408in;height:0.20653in" />**):** Following Chen et al., we will extract the linear direction governing the binary decision to invoke a tool<sup>10</sup>. We will measure its layerwise principal angles against the identified <img src="LLM Refusal Mechanistic Interpretability_media/media/image7.png" style="width:0.47511in;height:0.20698in" /> subspace to determine geometric overlap.

2.  **Which-tool Selection (**<img src="LLM Refusal Mechanistic Interpretability_media/media/image9.png" style="width:0.42525in;height:0.2079in" />**):** Following Wu et al., we will map the low-dimensional tool-selection geometry dictating specific tool identities<sup>9</sup>. This is hypothesized to operate orthogonally to safety routing, acting purely as a conditional branch after the commitment decision is made.

3.  **Tool-Abstention and Irreversible-Action Confirmation:** This is the critical nexus of the agent extension. We will test whether the <img src="LLM Refusal Mechanistic Interpretability_media/media/image16.png" style="width:0.66221in;height:0.20812in" /> representation (activated by Dataset D) routes through the exact same Gate-Amplifier heads as safety refusal. If an autonomous agent is provided with an irreversible tool (e.g., execute_sql_drop_table) without explicit user confirmation, the model's internal safety policies should naturally block the execution. We will test if naively ablating the refusal direction silently destroys this irreversible-action confirmation mechanism. If it does, it proves that current alignment pipelines inadvertently fused vital agentic action restraint with standard conversational censorship.

## Publication-Level Claim Boundaries

To adhere to rigorous mechanistic interpretability standards, all scientific claims derived from the proposed experiment must be strictly bounded by the evidence level achieved.

- **Claim from Geometry Alone (Level 2 Evidence):** "In the MiniCPM5 architecture, the subspace representing safety refusals and the subspace representing epistemic abstention exhibit high principal angles (orthogonality) in early layers but converge structurally in late layers. This geometric trajectory suggests that polysemantic entanglement—or Ghost Noise—primarily occurs at the output-routing phase rather than during upstream semantic detection." *(Note: This claim explicitly avoids assertions of causality or shared neural circuits).*

- **Claim from Cross-Ablation (Level 3 Evidence):** "Directionally ablating the refusal subspace in MiniCPM5 preserves the upstream linear separability of epistemic uncertainty, yet systematically degrades downstream negative verdicts and tool-abstention behaviors. This definitively falsifies the direct overlap hypothesis (H1), demonstrating that verdict bias is a downstream behavioral routing failure rather than an erasure of semantic epistemic caution." *(Note: This claim establishes causality for the behavioral shift but cannot specify the internal mechanism of the router).*

- **Claim from Successful Causal Circuit Localization (Level 4/5 Evidence):** "Verdict bias and tool-call dysregulation in abliterated models are the direct result of collateral damage to a shared Gate-Amplifier routing circuit. By causally patching matched attention heads across conditions, we demonstrate that safety harm detection and epistemic uncertainty are upstream-distinct representations that route through a shared action-inhibitor bottleneck. Applying Concept-Guided Spectral Cleaning to protect this specific circuit enables total safety bypass while perfectly preserving epistemic tool restraint."

## Reproducibility Plan

Given the extreme sensitivity of LLM internal representations to minor architectural or formatting deviations, strict provenance protocols will be enforced for the MiniCPM5 experiments.

- **Model Revision:** Experiments will utilize the exact openbmb/MiniCPM5-1B checkpoint (commit hash 67e1cad9b15ffc21d0877bf952d9ece2eeda5d35) to ensure reproducibility of the hybrid sparse/linear attention pathways<sup>25</sup>.

- **Precision and Quantization:** All activation extraction and patching will occur in unquantized FP16 precision. Quantized Q4_K_M GGUF formats will be used exclusively for final deployment latency testing, with strict verification of GGUF magic formats<sup>25</sup>.

- **Chat Template Formatting:** We will enforce strict adherence to MiniCPM5's native XML-style tag parsing (e.g., \<tool_call\>). We will intentionally bypass community Jinja templates, which have documented parsing failures with OpenVINO Model Server (OVMS), instead utilizing direct regex/XML extraction or native SGLang implementations<sup>24</sup>.

- **Intervention Framework:** Interventions will be orchestrated via PyTorch 2.4+ and custom TransformerLens hooks explicitly designed to handle the 288 routed experts and the shared expert within the MoE layers, ensuring activations are normalized correctly across the variable expert pathways<sup>23</sup>.

- **Data and Randomization:** All bootstrap sampling and RFM-AGOP initialization states will be fixed to random seed 42. All minimal-pair prompt datasets (A-E) will be cryptographic hashed (SHA-256) and released publicly under a CC BY 4.0 license, mirroring the strict data provenance protocols established by Fafuła<sup>26</sup>.

## Final Reading Order

To deeply comprehend the mechanistic transition from scalar refusal vectors to complex routing circuits and their impact on agentic tool use, the following prioritized reading list is recommended.

**Essential Papers (Read First):**

1.  **Frank (2026) - *How Alignment Routes: Localizing, Scaling, and Controlling Policy Circuits in Language Models***<sup>8</sup>.

    - *Question to hold:* How exactly does causal interchange testing isolate the downstream gate-amplifier motif from the upstream semantic detection signal, and why does this invalidate standard probing?

2.  **Cristofano (2026) - *Surgical Refusal Ablation: Disentangling Safety from Intelligence via Concept-Guided Spectral Cleaning***<sup>11</sup>.

    - *Question to hold:* Mechanically, how does ridge-regularized spectral residualization prevent the removal of "Ghost Noise" capabilities compared to standard orthogonal projection?

3.  **Fafuła (2026) - *Abliteration Is Not a Scalpel: Off-Target Effects of Refusal Removal on Decision Disposition Across Model Families***<sup>3</sup>.

    - *Question to hold:* What specific behavioral evidence proves that confidence shifts differ fundamentally across architectures (e.g., Gemma vs. Qwen), and why does this point to deep structural entanglement rather than dataset contamination?

4.  **Son et al. (2026) - *A Unified Mechanistic Analysis of Knowledge- and Safety-Based Refusals***<sup>6</sup>.

    - *Question to hold:* At precisely what layer depth does the shared "commit" mechanism functionally transition into the distinct "specify" mechanism?

5.  **Chen et al. (2026) - *Tunable Tool-Call Rates in LLM Agents via Representation Steering***<sup>10</sup>.

    - *Question to hold:* How can a single linear direction monotonically control the overall propensity to call a tool without destroying the complex syntax required for tool-identity execution?

**Second-Tier Papers (Context and Extension):** 6. **Winninger (2026) - *Fast Multi-dimensional Refusal Subspaces via RFM-AGOP***<sup>12</sup>. \* *Question to hold:* Why do highly parameterized reasoning models require multi-dimensional polyhedral cones to map refusal, rather than rank-one vectors? 7. **Chu et al. (2026) - *From Detection to Refusal: Safer LLMs via Circuit-Guided Weight Scaling***<sup>7</sup>. \* *Question to hold:* What are the distinct layer-stratified roles of harm detection heads versus safety routing neurons? 8. **Prakash et al. (2026) - *Beyond I'm Sorry, I Can't: Dissecting Large Language Model Refusal***<sup>18</sup>. \* *Question to hold:* How does the ablation of early-layer SAE refusal features trigger the activation of redundant, dormant features in downstream layers? 9. **Wu et al. (2026) - *Tool Calling is Linearly Readable and Steerable in Language Models***<sup>9</sup>. \* *Question to hold:* How is the subspace for tool identity selection geographically separated from the mechanism that decides to invoke a tool in the first place? 10. **Arditi et al. (2024) - *Refusal in Language Models Is Mediated by a Single Direction***<sup>1</sup>. \* *Question to hold:* Read strictly for historical context; what critical assumptions regarding dataset parity were made during the extraction of the difference-in-means vector?

**Technical Repositories:**

- Review Jim Lai's implementations on **Projected Abliteration and Biprojected Abliteration** (e.g., within the llm-abliteration and heretic repositories)<sup>28</sup>.

  - *Focus:* Understand the rigorous mathematical constraints of norm-preservation during weight modification, and explicitly trace the algorithmic difference between standard directional ablation and bi-projection.

#### Works cited

1.  Refusal in Language Models Is Mediated by a Single Direction, [<u>https://www.researchgate.net/publication/381510906_Refusal_in_Language_Models_Is_Mediated_by_a_Single_Direction</u>](https://www.researchgate.net/publication/381510906_Refusal_in_Language_Models_Is_Mediated_by_a_Single_Direction)

2.  Refusal in Language Models Is Mediated by a Single Direction, [<u>https://www.alphaxiv.org/abs/2406.11717</u>](https://www.alphaxiv.org/abs/2406.11717)

3.  Abliteration Is Not a Scalpel:Off-Target Effects of Refusal Removal, [<u>https://arxiv.org/html/2607.17427v1</u>](https://arxiv.org/html/2607.17427v1)

4.  Abliteration Is Not a Scalpel: Off-Target Effects of Refusal Removal, [<u>https://arxiv.org/abs/2607.17427</u>](https://arxiv.org/abs/2607.17427)

5.  clearbluejar, [<u>https://clearbluejar.github.io/</u>](https://clearbluejar.github.io/)

6.  A Unified Mechanistic Analysis of Knowledge- and Safety-Based, [<u>https://arxiv.org/html/2609.00760v1</u>](https://arxiv.org/html/2609.00760v1)

7.  From Detection to Refusal: Safer LLMs via Circuit-Guided Weight, [<u>https://arxiv.org/html/2609.00051v1</u>](https://arxiv.org/html/2609.00051v1)

8.  How Alignment Routes: Localizing, Scaling, and Controlling Policy, [<u>https://arxiv.org/html/2604.04385v1</u>](https://arxiv.org/html/2604.04385v1)

9.  Tool Calling is Linearly Readable and Steerable in Language Models, [<u>https://www.researchgate.net/publication/404713741_Tool_Calling_is_Linearly_Readable_and_Steerable_in_Language_Models</u>](https://www.researchgate.net/publication/404713741_Tool_Calling_is_Linearly_Readable_and_Steerable_in_Language_Models)

10. Tunable Tool-Call Rates in LLM Agents via Representation Steering, [<u>https://arxiv.org/html/2608.25198v1</u>](https://arxiv.org/html/2608.25198v1)

11. Surgical Refusal Ablation: Disentangling Safety from Intelligence via, [<u>https://arxiv.org/html/2601.08489v1</u>](https://arxiv.org/html/2601.08489v1)

12. Fast Multi-dimensional Refusal Subspaces via RFM-AGOP - arXiv, [<u>https://arxiv.org/pdf/2607.02396</u>](https://arxiv.org/pdf/2607.02396)

13. A Unified Mechanistic Analysis of Knowledge- and Safety-Based, [<u>https://openreview.net/forum?id=J8VRAFue0M</u>](https://openreview.net/forum?id=J8VRAFue0M)

14. Surgical Refusal Ablation: Disentangling Safety from Intelligence via, [<u>https://arxiv.org/abs/2601.08489</u>](https://arxiv.org/abs/2601.08489)

15. Detection Is Cheap, Routing Is Learned: Why Refusal-Based ... - arXiv, [<u>https://arxiv.org/pdf/2603.18280</u>](https://arxiv.org/pdf/2603.18280)

16. From Detection to Refusal: Safer LLMs via Circuit-Guided Weight, [<u>https://arxiv.org/abs/2609.00051</u>](https://arxiv.org/abs/2609.00051)

17. ‪Vincent Siu‬ - ‪Google Scholar‬, [<u>https://scholar.google.com/citations?user=EiaoeIUAAAAJ&hl=en</u>](https://scholar.google.com/citations?user=EiaoeIUAAAAJ&hl=en)

18. Beyond I'm Sorry, I Can't: Dissecting Large-Language-Model Refusal, [<u>https://arxiv.org/html/2509.09708v3</u>](https://arxiv.org/html/2509.09708v3)

19. Beyond I'm Sorry, I Can't: Dissecting Large Language Model Refusal, [<u>https://arxiv.org/abs/2509.09708</u>](https://arxiv.org/abs/2509.09708)

20. Tool Calling is Linearly Readable and Steerable in Language Models, [<u>https://arxiv.org/html/2605.07990v1</u>](https://arxiv.org/html/2605.07990v1)

21. Refusal in Language Models Is Mediated by a Single Direction, [<u>https://openreview.net/forum?id=pH3XAQME6c¬eId=INlIvPFTqH</u>](https://openreview.net/forum?id=pH3XAQME6c&noteId=INlIvPFTqH)

22. Refusal Direction is Universal Across Safety-Aligned Languages, [<u>https://neurips.cc/virtual/2025/poster/116911</u>](https://neurips.cc/virtual/2025/poster/116911)

23. Hugging Face Release Notes - August 2026 Latest Updates, [<u>https://releasebot.io/updates/huggingface</u>](https://releasebot.io/updates/huggingface)

24. Add tool_parser minicpm5 for MiniCPM5-1B XML tool calls \#4268, [<u>https://github.com/openvinotoolkit/model_server/issues/4268</u>](https://github.com/openvinotoolkit/model_server/issues/4268)

25. ewinregirgojr/MiniCPM5-1B-Agentic-Tooluse-GGUF - Hugging Face, [<u>https://huggingface.co/ewinregirgojr/MiniCPM5-1B-Agentic-Tooluse-GGUF</u>](https://huggingface.co/ewinregirgojr/MiniCPM5-1B-Agentic-Tooluse-GGUF)

26. oleczek/paper-abliteration-not-a-scalpel - GitHub, [<u>https://github.com/oleczek/paper-abliteration-not-a-scalpel</u>](https://github.com/oleczek/paper-abliteration-not-a-scalpel)

27. LICENSE-DATA.md - oleczek/paper-abliteration-not-a-scalpel - GitHub, [<u>https://github.com/oleczek/paper-abliteration-not-a-scalpel/blob/main/LICENSE-DATA.md</u>](https://github.com/oleczek/paper-abliteration-not-a-scalpel/blob/main/LICENSE-DATA.md)

28. jim-plus/llm-abliteration - GitHub, [<u>https://github.com/jim-plus/llm-abliteration</u>](https://github.com/jim-plus/llm-abliteration)

29. GitHub - p-e-w/heretic: Fully automatic censorship removal for, [<u>https://github.com/p-e-w/heretic</u>](https://github.com/p-e-w/heretic)

30. Comparative Analysis of LLM Abliteration Methods - arXiv, [<u>https://arxiv.org/pdf/2512.13655</u>](https://arxiv.org/pdf/2512.13655)

**KIMI SWARM**
