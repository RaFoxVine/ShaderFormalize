# 实施证据

## 完整返回字段与实际入口分离

基线649a4ec，精确授权function-entry-001。修复前分支内Identity返回字段在入口外清零，有限导数oracle得到9；修复后与内联相同得到7。此为有限规则检查，不是GPU观测。

实际执行`tools/run_demo.ps1`的核心全套：132回归/35控制全部符合预期，14 PROVED、19 UNPROVED、2 INVALID_INPUT。完整日志artifacts/language-probes/full-core-35.log；master和新增三个control封存在artifacts/function-frame/acceptance35，跟踪的结果与哈希见../evidence/function-frame-2026-10-26.json。

新增控制包括任意共享Ops下的helper导数等价、未调用normalize(0)的正例、实际调用normalize(0)的同源负例。域仍为结论，公理白名单不变。独立P1 Ready、Q2 Verified，无遗留阻断。

## 共享定义后端（已完成）

授权3fbe6d6的shared-definition-001修订2，源码2fc87bb/5961f8e/b074163。显式shared/schema6实现函数体缓存、拓扑定义、调用事件、独立有限帧、CLI/目标分派及旧混配拒绝。完整验收146单元/41控制全部符合预期，17 PROVED、22 UNPROVED、2 INVALID_INPUT；最终补丁后再次串行146单元通过。新增6正式控制中，正常光照、完整场helper导数、未调用非法域为PROVED；错误数值、实际非法helper域、被忽略但实际执行的非法实参域为UNPROVED。

Q1的坏模型结构异常和predicate类型缺口已修复并回归；literal的数据验证最终统一到共用validator，发射和有限求值都对坏值返回ModelError，生成入口另保留兜底。参数顺序调查确认现有表达式不能改变裁剪状态，无须额外收紧纯兄弟计算；边界已补文档与回归。独立最终Q核对旧16份schema4/5模型新旧emitter文本逐字相同、三正例哈希/审计、三负例真实未证目标及146/41报告，Verified。

13层双调用图实际得到13 helper体、24内部call、1入口call，JSON15991字节、生成Lean23865字节；7层为7/12/1和8989/12899字节。旧后端13层真实拒绝过量展开。记录artifacts/shared/scaling.json，不以耗时声称加速。

保留失败过程：一次误将含prepare的全单元与正式控制并发，共享写锁导致7项CLI测试失败；之后串行全单元146通过，正式控制全部串行。一次新边界测试用了DXC拒绝的缺return输入，修正为有return的discard helper后通过。日志保留于artifacts/language-probes；这些失败未作为产品结果。最终普通shape/validator显式化后shared14项重跑通过，structured目标逐字哈希不变。

## 默认参数与复制进出（验收中）

精确授权10ac78d的copyback-001修订2先于产品代码；源码64992ea。新增参数元数据、默认声明绑定、out/inout独立副本/正常返回捕获、outputs结果布局、静态访问顺序检查，以及数值函数调用纯void/out helper的传递裁剪分析。仅shared启用，auto仍拒绝；没有数学模块/公理/依赖变化。

实际新增19项DXC单元全部通过，随后默认全套165单元通过；6项新正式控制全部符合预期（4 PROVED、2 UNPROVED）。真实材质证明包含5个原版helper和4个改写helper，涉及结构体输出、默认uniform系数和inout累积；完整场导数与clip写回也PROVED。错误数值确实失败于光照分量目标；实际执行normalize(0)默认参数的同源负例失败于定义域，不是源无法导入。默认47项全控制仍在串行运行，最终状态另行补入。

独立Q1发现默认声明验证累计预算的问题：65个helper各有64个纯默认调用，本来是分开检查，却累积在一个临时frame超4096调用。修复为每个默认声明独立临时状态，真实DXC回归确认66个helper、入口0调用，不增加未用域。Q1代码复核无剩余阻断；Q2已核验六项输入/模型/生成文字、四正例哈希与公理、两负例真实目标，以及17旧正例生成文字不变，待最终47结果闭合。

固定DXC对record输出使用__restrict S，并将调用者目标包在LValueToRValue中；这层经确切类型核对后作为地址包装处理，不能误读out旧值。raw探针artifacts/language-probes/out-record.*保留。F(out x,x)允许旧输入副本；F(inout x,G(out x))拒绝；F(out x,G(out x))按先完成内调用后外copy-out得到5。默认参数在声明全局环境查找，调用者同名变量不会捕获它。两个输出先全部快照再写回。

最新源码另在已独立安装依赖的Fresh Checkout更新至64992ea，copyback材质、完整场导数、packed三正例均实际PROVED；复用副本自己的同锁工具/缓存，不是再次从空目录安装。独立事实复核通过，精简证据见../evidence/windows-copyback-2026-10-26.json。
