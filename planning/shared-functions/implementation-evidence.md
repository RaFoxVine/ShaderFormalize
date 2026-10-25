# 实施证据

## 完整返回字段与实际入口分离

基线649a4ec，精确授权function-entry-001。修复前分支内Identity返回字段在入口外清零，有限导数oracle得到9；修复后与内联相同得到7。此为有限规则检查，不是GPU观测。

实际执行`tools/run_demo.ps1`的核心全套：132回归/35控制全部符合预期，14 PROVED、19 UNPROVED、2 INVALID_INPUT。完整日志artifacts/language-probes/full-core-35.log；master和新增三个control封存在artifacts/function-frame/acceptance35，跟踪的结果与哈希见../evidence/function-frame-2026-10-26.json。

新增控制包括任意共享Ops下的helper导数等价、未调用normalize(0)的正例、实际调用normalize(0)的同源负例。域仍为结论，公理白名单不变。独立P1 Ready、Q2 Verified，无遗留阻断。
