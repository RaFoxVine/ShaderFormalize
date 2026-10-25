# 当前工作

- 函数局部路径与调用执行前缀分离（plan.md修订1）：Completed；P1 Ready/Q2 Verified；132回归及35控制全部符合预期。证据见../evidence/function-frame-2026-10-26.json。
- 共享函数定义后端（shared-definitions-plan.md修订2）：Implementing；P2 Ready，前置完整字段修复已闭合；精确grant shared-definition-001@revision-2。
- 默认参数与out/inout（copyback-plan.md修订2）：Candidate，独立P2 Planning Ready；等待共享定义完整验收/Q闭合后派生精确grant。
- 矩阵/数组、终止循环：Outlined，调查见aggregate-loop-notes.md；保留language overnight完整目标，逐项Ready后派生后续grant。
- 下一步：共享helper体只定义一次，保留实际调用的定义域、裁剪和完整字段。
