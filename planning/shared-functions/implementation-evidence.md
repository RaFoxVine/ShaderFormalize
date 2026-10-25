# 实施证据

## 完整返回字段与实际入口分离

基线649a4ec，精确授权function-entry-001。修复前分支内Identity返回字段在入口外清零，有限导数oracle得到9；修复后与内联相同得到7。此为有限规则检查，不是GPU观测。

实际执行`tools/run_demo.ps1`的核心全套：132回归/35控制全部符合预期，14 PROVED、19 UNPROVED、2 INVALID_INPUT。完整日志artifacts/language-probes/full-core-35.log；master和新增三个control封存在artifacts/function-frame/acceptance35，跟踪的结果与哈希见../evidence/function-frame-2026-10-26.json。

新增控制包括任意共享Ops下的helper导数等价、未调用normalize(0)的正例、实际调用normalize(0)的同源负例。域仍为结论，公理白名单不变。独立P1 Ready、Q2 Verified，无遗留阻断。

## 共享定义后端（尚在最终验收）

授权3fbe6d6的shared-definition-001修订2。显式shared/schema6已实现函数体缓存、拓扑定义、调用事件、独立有限帧、CLI/目标分派及旧混配拒绝。14项shared真实DXC回归通过；全套146单元通过，最终41控制仍运行。新增6正式控制已经单独串行通过：正常光照、完整场helper导数、未调用非法域为PROVED；错误数值、实际非法helper域、被忽略但实际执行的非法实参域为UNPROVED。

Q1的坏模型结构异常和predicate类型缺口已修复并回归。参数顺序调查确认现有表达式不能改变裁剪状态，无须额外收紧纯兄弟计算；边界已补文档与回归。独立最终Q已核对旧16份schema4/5模型新旧emitter文本逐字相同、三正例哈希/审计及三负例真实未证目标，目前仅待41控制总报告。

13层双调用图实际得到13 helper体、24内部call、1入口call，JSON15991字节、生成Lean23865字节；7层为7/12/1和8989/12899字节。旧后端13层真实拒绝过量展开。记录artifacts/shared/scaling.json，不以耗时声称加速。

保留失败过程：一次误将含prepare的全单元与正式控制并发，共享写锁导致7项CLI测试失败；之后串行全单元146通过，正式控制全部串行。一次新边界测试用了DXC拒绝的缺return输入，修正为有return的discard helper后通过。日志保留于artifacts/language-probes；这些失败未作为产品结果。最终普通shape/validator显式化后shared14项重跑通过，structured目标逐字哈希不变。
