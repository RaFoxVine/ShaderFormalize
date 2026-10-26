# 当前工作

- 函数局部路径与调用执行前缀分离（plan.md修订1）：Completed；P1 Ready/Q2 Verified；132回归及35控制全部符合预期。证据见../evidence/function-frame-2026-10-26.json。
- 共享函数定义后端（shared-definitions-plan.md修订2）：Completed；b074163，P2 Ready/最终Q Verified；146最终单元/41控制通过，证据见../evidence/shared-functions-2026-10-26.json。
- 默认参数与out/inout（copyback-plan.md修订2）：Completed；源码64992ea，19新/165全部单元与47控制全部符合预期，21 PROVED/24 UNPROVED/2 INVALID_INPUT，独立Q2 Verified；证据见../evidence/copyback-2026-10-26.json及独立Windows追加复现。
- 矩阵/数组（aggregate-plan.md修订1）：Completed；9bec4aa，25新/190全部单元与53控制PASSED（25 PROVED/26 UNPROVED/2 INVALID_INPUT），独立Q2最终Verified；精简证据../evidence/aggregate-2026-10-26.json；独立Windows三正例复现通过。
- 静态有限for（loop-plan.md修订2）：Completed；d348566，23新/213全部单元、57正式控制PASSED（27 PROVED/28 UNPROVED/2 INVALID_INPUT），独立Q2最终Verified；旧25目标兼容，独立Windows两个最新正例复现通过。符号次数/while/do等仍不支持。证据../evidence/static-loops-2026-10-26.json。
- 下一步：当前普通材质语言目标已闭合；完整HDRP/Lit Forward的剩余工作与实数语义边界见../hdrp-forward/real-boundary.md，等待固定配置/异常恢复契约选择。最终发布由publish条目处理，不自动归档。
