# 当前工作

- 函数局部路径与调用执行前缀分离（plan.md修订1）：Completed；P1 Ready/Q2 Verified；132回归及35控制全部符合预期。证据见../evidence/function-frame-2026-10-26.json。
- 共享函数定义后端（shared-definitions-plan.md修订2）：Completed；b074163，P2 Ready/最终Q Verified；146最终单元/41控制通过，证据见../evidence/shared-functions-2026-10-26.json。
- 默认参数与out/inout（copyback-plan.md修订2）：Completed；源码64992ea，19新/165全部单元与47控制全部符合预期，21 PROVED/24 UNPROVED/2 INVALID_INPUT，独立Q2 Verified；证据见../evidence/copyback-2026-10-26.json及独立Windows追加复现。
- 矩阵/数组（aggregate-plan.md修订1）：Approved；独立P1通过、前置闭合，精确grant aggregate-001@revision-1。
- 静态有限for（loop-plan.md修订1）：Execution Ready/P1通过；须aggregate完成及实际接口复核后再派生grant。uniform符号次数等广义循环仍Outlined，见aggregate-loop-notes.md。
- 下一步：实施矩阵/数组与typed元素地址，保留完整字段、实际域、布局核对和未定序副作用检查。
