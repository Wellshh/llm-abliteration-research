# 批6复核与提交记录（2026-09-15）

结论：本批实现修复与三份勘误旁注已独立复核，可以提交。Phase 0构念准入仍未满足；T03数值门历史失败保持不变。T05、扩样、正式测试、干预选择和阈值调整均未启动。

权威仓库：`/home/jybai/research/MiniCPM5_Research_Plan_v1/minicpm5_research_plan`（172.16.92.211）。本地E:/minicpm和E:/minicpm-research并非最新Git工作树，本批commit在远程权威仓库执行。基线commit为`7e65e16a457f456ba830d93e0931522f3824b613`。

独立验证结果：

- 原资源摘要sha256为`fb748f9df96e51e494848c6e58a9287469a383307e5ee2d0d7a58c60af8d004f`，与旁注绑定及Git初始提交字节完全一致。
- 三个attempt逐项核验failure、admission、audit目录与账本条目，分类通过；两次pre-admission各0秒，UUID mismatch为post-admission setup failure，3.620666043832898秒。
- 从账本独立分桶：T03 128.706021592021；权威T04 58.41640244983137；superseded T 29.78392337448895；post-admission setup failure 17.522693587467074；pre-admission 0。分项、账本和原摘要总数均为234.42904100380838秒。
- 使用已核验tokenizer/template文件及现有build_token_anchor，在CPU重建两个权威T run的全部锚点。完整anchor对象与旁注完全相等，实际输入长度均为[517,517,497,427]；原TOKEN_ANCHORS文件hash未变。未加载模型权重。
- 历史review脚本复跑退出0：四个权威run的manifest、shard、gold、解析、sandbox重放、原指标和两条件结果仍可复核。其旧counterexample/恢复诊断输出保留其原始意义；修复验收另由test_review_fixes覆盖。
- 远程完整单测：**151项，150通过、1跳过**，2.285秒，退出0。三条check_hooks参数报错是拒绝路径测试的预期输出。PREREG/ALIGNMENT中的“151通过”计数在本次提交前更正，研究阈值未变。

实际命令均在上述权威仓库执行：

```text
CUDA_VISIBLE_DEVICES='' PYTHONPATH=src OMP_NUM_THREADS=4 .venv/bin/python -m unittest discover -s tests -q
  exit 0; Ran 151 tests in 2.285s; OK (skipped=1)
CUDA_VISIBLE_DEVICES='' PYTHONPATH=src OMP_NUM_THREADS=4 .venv/bin/python reports/review_20260915/verify_closeout.py
  exit 0; verification.json + historical_replay.stdout.json + historical_replay.stderr.log
.venv/bin/python reports/review_20260914/reproduce_review.py
  exit 0; invoked by verify_closeout.py, captured in historical_replay.*
git diff --check
  nonzero (SSH/PowerShell tool batch reported 1); CR-at-EOL flagged on the existing CRLF model.py
git -c core.whitespace=cr-at-eol diff --check
  exit 0; CRLF preserved, no unrelated newline normalization
```

验证期间未修改历史run、原摘要或预算账本；已有runtime代码修复由本批commit留存。纳入4个src文件、run_pilot、目标测试、两份状态文档、.gitignore、三份新增旁注、原独立评审记录及本次复核记录。两个持续追加的reservation心跳日志排除在暂存/提交外，不回滚、不改动、不操作对应进程。Git提交只在研究仓库本地创建，不push。

GPU模型实验：**未运行**。预留操作：未执行。完整Phase 0仍有S/C、人工gold审核、功效与prefill/decode资源重估等待办，以ALIGNMENT §6为准。已初始化的Git能留存本批及以后版本，但不自动还原初始commit以前缺失的历史源码。

本次run manifest见manifest.json，原始验证输出见verification.json及historical_replay.*。最终提交ID与提交后工作树状态由当前任务最终回复及本地commit-receipt.json记录；避免为了在自身文件中写入commit ID而循环修改提交。
