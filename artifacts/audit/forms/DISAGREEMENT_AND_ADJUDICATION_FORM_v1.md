# DISAGREEMENT_AND_ADJUDICATION_FORM_v1 — 分歧记录与裁决表（空白模板）

**原则**：分歧**先完整记录**（双方原始表均保留、不改写），**后裁决**；裁决后改动的构造须对受影响类别重新抽取新样本复审。人工签署与裁决由人类完成。

## 表头绑定（协调人预填）
- package_manifest_sha256: ____
- r1_sheet_sha256 / r2_sheet_sha256: ____ / ____
- adjudicator_id（预先指名的第三人）: ____
- adjudication_date: ____

## 分歧类型分类（固定 taxonomy）
| type_code | 含义 |
|---|---|
| GOLD_MISMATCH | 双方独立 gold 不同 |
| UNCERTAIN_ONE_SIDED | 一方 uncertain、另一方确定 |
| UNCERTAIN_BOTH | 双方均 uncertain |
| CATEGORY_MISMATCH | （S）d1 类别归属不同 |
| STORAGE_SAFETY_MISMATCH | （S）d4 保存安全判断不同（任一 not_storable 即阻止入库，无需裁决入库资格） |
| PAIRING_DEFECT | （S）d5 配对充分性分歧 |
| SURFACE_MISMATCH | （C surface-check）语义等同性判断不同 |
| EVIDENCE_CITATION_GAP | 结论同但必需证据引用不一致 |
| OTHER | 其他（须文字说明） |

## 分歧逐条记录
| item_code | type_code | R1 判断 | R2 判断 | 裁决结果 | 裁决理由（引用 prompt 内证据） | 是否触发重抽检（类别） | 备注 |
|---|---|---|---|---|---|---|---|

## 汇总
- 分歧总数 / 各类型计数：____
- Cohen's kappa（按维度，协调人计算）：____
- 裁决后需重抽检的类别与新样本范围：____
- 数据修正（如有）：仅允许修正**构造错误**（gold 标注错、渲染缺陷），修正走新版本数据文件+新 sha，**不改写**已冻结数据；修正清单：____

## 签署
- R1 ____  R2 ____  adjudicator ____  日期 ____（三方确认记录先于裁决、双方原表未改动）
