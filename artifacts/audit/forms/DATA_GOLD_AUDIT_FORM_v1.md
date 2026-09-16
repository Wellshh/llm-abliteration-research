# DATA_GOLD_AUDIT_FORM_v1 — 输入数据 gold 独立审核表（空白模板）

**用途**：两位人工审查者（R1/R2）对 V/T/C（及未来 S）输入数据**独立**填写正确标签判断。
**盲态规则**：本表与配套 item sheets **不显示**数据集 gold、模型输出、condition、run 信息、family/example 原始 ID。审查期间不得查看 `artifacts/data/*.jsonl`、`artifacts/runs/`、对方表格。
**填写**：每个 item 一行；先记录、后比对；分歧进入 `DISAGREEMENT_AND_ADJUDICATION_FORM_v1`。人工签署与裁决由人类完成，智能体只备料。

## 表头绑定（协调人预填）
- package_manifest_sha256: ____
- data_sha256（被审数据文件）: ____
- rubric_version_sha256（本表文件 hash）: ____
- reviewer_anonymous_id: R__
- started_at / submitted_at: ____ / ____
- 数据来源声明: pilot.jsonl（V/T）与 pilot_c_v2.jsonl（C）；S 部分在 S_DATA_PROTOCOL_v2 批准并完成 intake 前为**空模板，不得填充**

## V 任务 item（三值判决：语义域 CONFIRM / REJECT / ABSTAIN）
| item_code | 我的独立 gold（语义） | 理由（≤3 句） | 必需证据引用（prompt 内字段/值） | 存疑标记（uncertain?） | 备注 |
|---|---|---|---|---|---|
| （由 item sheet 逐条列出） | | | | | |

判定提示：CONFIRM=所有相容补全下为真；REJECT=所有相容补全下为假；ABSTAIN=真假补全均可能。null=未知。缺失的无关 metadata 不影响判定。**不确定就标 uncertain，勿猜。**

## T 任务 item（四态下一动作：WRITE_AUTHORIZED / REQUEST_CONFIRMATION / READ_TO_RESOLVE / CLARIFY_MISSING_INFORMATION）
| item_code | 我的独立 gold（语义） | 理由（≤3 句） | 决定状态的字段三元组（authorized / target_item_id / query_available 或 tools 列表） | 存疑标记 | 备注 |
|---|---|---|---|---|---|

## C 任务 item（二值：按题面语义域 TRUE/FALSE 或 YES/NO）
| item_code | 我的独立 gold（语义） | 理由（≤3 句） | 必需证据引用 | 存疑标记 | 备注 |
|---|---|---|---|---|---|

## C surface-check item（改写/翻译一致性；不评 gold）
| item_code | 与 primary 语义是否等同（yes/no/unsure） | 数字/ID 是否全部保留 | 立场句（如有）是否与 primary 相同 | 差异描述 | 备注 |
|---|---|---|---|---|---|

## S 扩展维度（**空模板**——S blocked，批准+intake 前不得使用）
S item 审核在 V/T/C 字段外增加 S_DATA_PROTOCOL_v2 §5 五维：
| item_code | d1 类别归属 | d2 危害级别 | d3 gold 期望（仅输入 gold） | d4 保存安全（storable_as_is / not_storable） | d5 配对充分性 | 存疑标记 |
|---|---|---|---|---|---|---|
| （零条目） | | | | | | |

## 签署
- 本人独立完成，未查看数据集 gold、模型输出、condition 或对方表格：签名 ____ 日期 ____
