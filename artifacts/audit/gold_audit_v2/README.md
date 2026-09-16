# gold_audit_v2 — 数据池抽检包（Level A）

- **Level A（本包）**：数据池分层确定性抽检；结论限于「池质量」；**不证明最终入轮文件已审核，不解锁任何运行**。
- **Level B（未来包）**：轮数据冻结后，对该轮**全部**入轮 prompt/gold 的全量审核；冻结前必须完成。
- 分发：reviewer 得到 sheets/ + packages/；**SEALED_KEY.json 与 manifest.json 仅协调人**。
- 盲态为诚信约束：sheets/items 不含 gold/ID/输出/condition；有仓库访问权者技术上可查源数据（已记录为限制）。
- S 目录为空模板（blocked）。
