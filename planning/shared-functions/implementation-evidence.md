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

## 默认参数与复制进出（已完成）

精确授权10ac78d的copyback-001修订2先于产品代码；源码64992ea。新增参数元数据、默认声明绑定、out/inout独立副本/正常返回捕获、outputs结果布局、静态访问顺序检查，以及数值函数调用纯void/out helper的传递裁剪分析。仅shared启用，auto仍拒绝；没有数学模块/公理/依赖变化。

实际新增19项DXC单元全部通过，随后默认全套165单元/47控制PASSED（21 PROVED、24 UNPROVED、2 INVALID_INPUT）；6项新正式控制全部符合预期（4 PROVED、2 UNPROVED）。真实材质证明包含5个原版helper和4个改写helper，涉及结构体输出、默认uniform系数和inout累积；完整场导数与clip写回也PROVED。错误数值确实失败于光照分量目标；实际执行normalize(0)默认参数的同源负例失败于定义域，不是源无法导入。完整验收已冻结artifacts/copyback/acceptance47，精简证据见../evidence/copyback-2026-10-26.json。

独立Q1发现默认声明验证累计预算的问题：65个helper各有64个纯默认调用，本来是分开检查，却累积在一个临时frame超4096调用。修复为每个默认声明独立临时状态，真实DXC回归确认66个helper、入口0调用，不增加未用域。Q1代码复核无剩余阻断；Q2核验六项输入/模型/生成文字、四正例哈希与公理、两负例真实目标，以及17旧正例生成文字不变。额度中断期间runner继续完成，恢复后的独立只读复核确认全部21正例都能在内存逐字重生成当前目标，源/目标/证明/模块/锁/公理吻合，两新负例与冻结6控制字节一致、真实目标失败，最终Q2 Verified。原进程会话ID已过期，未将该句柄错误当测试失败或重跑全套。

固定DXC对record输出使用__restrict S，并将调用者目标包在LValueToRValue中；这层经确切类型核对后作为地址包装处理，不能误读out旧值。raw探针artifacts/language-probes/out-record.*保留。F(out x,x)允许旧输入副本；F(inout x,G(out x))拒绝；F(out x,G(out x))按先完成内调用后外copy-out得到5。默认参数在声明全局环境查找，调用者同名变量不会捕获它。两个输出先全部快照再写回。

最新源码另在已独立安装依赖的Fresh Checkout更新至64992ea，copyback材质、完整场导数、packed三正例均实际PROVED；复用副本自己的同锁工具/缓存，不是再次从空目录安装。独立事实复核通过，精简证据见../evidence/windows-copyback-2026-10-26.json。

## 矩阵、数组与typed元素地址（实施中）

授权aggregate-001修订1及Approved状态在1d0b227先提交；前置copyback165/47/Q2闭合后开始代码。矩阵/数组降为现有record数值叶，统一地址捕获下标、元素/不重复swizzle写回、逐叶初始化和别名足迹；复合float uniform保留源布局、packing和范围组；bounded_index保留原uint并生成实际执行域结论。默认auto与四个数学模块不变。

初始20项真实DXC单元、随后新增至25项全部通过；原copyback19/shared14也通过。非方阵、transpose/矩阵积、全元素splat/左上截断、float1与标量重载区别、嵌套数组顺序、out数组、矩阵返回/输出、索引只求值一次、partial初始化、动态越界和未实际越界、静态别名/索引副作用、复合输入/范围交集/物理packing拒绝及坏模型均覆盖；实际新材质另有两组合法输入的独立手算公式及错误系数有限反例，uint/bool数组叶类型也实际验证。一次readonly uniform写入负例被DXC先拒绝，回归最初只期待ModelError；修正为也接受确切CalledProcessError，不改产品拒绝行为。

正常新材质使用LightData[2]、out数组、默认系数、inout累积和颜色混合矩阵；手工展开版以行列项计算。两版实际材质目标PROVED，故意改错矩阵系数UNPROVED。组合prepare发现DXC的只读矩阵operator[]带const方法和const pointer decay，已严格按对应签名补支持并加回归。首个完整材质check在元数据完整性补丁前完成，随后统一aggregate控制中的材质正反例在补丁后再次核验。

独立Q1源码初审没有发现确定语义阻断，并将旧21正例从保存的真实DXC AST重新导入，模型与目标逐字一致。它发现说明性形状表允许未知元素/环；虽不参与数值定义，仍按完整性合同修复为完整规范类型图，检查source record字段、引用、环、深度/叶和canonical identity，发射与有限求值均受保护，已有坏模型回归通过。尚待六正式控制全部通过、全套及最终Q，不预先标Verified。

导数正例的初始证明脚本在BitVec.toNat 0<2的闭合义务处未完成；原脚本与失败目标冻结于artifacts/aggregate/field-first-failed。补充合法索引的内核decide证明后正式PROVED，不移动域到前提、不更改数学生成。下标正例一版脚本因simp没有可化简项而失败，改为条件尝试后，合法与未执行越界正式PROVED，实际越界同源UNPROVED。六控制现全部符合预期；对应日志分别保留aggregate-controls.log、aggregate-field-domain.log、aggregate-field-domain-fixed.log及aggregate-domain-fixed.log，不将早期失败当通过。

## 静态循环：隔离实施进行中

0fe6bd6/756b0f6持久化loop-001修订2的隔离代码权限后，root在ignored artifacts/loop-development从9bec4aa创建独立Git clone；只读复用主.tools junction，没有副本.lake或共享proof写入。主产品在aggregate完整验收期间未改。只运行确切test_loops.py、新DXC/有限求值和内存Lean生成，未在副本运行bootstrap/Lean/Lake/prepare/check。

当前23项新回归通过（副本artifacts/loop-unit23.log）：静态0/1/多次、uint边界/wrap/非法shift、嵌套/空体预算、局部scope、部分初始化、out/default、分支状态、clip实际域/完整场导数、计数器/动态界限/控制拒绝、metadata目标绑定与坏metadata双消费者检查、正常helper return和未调用循环，以及完整材质手算/错误系数反例。独立Q1源码审读未发现确定语义阻断；不等于形式验收或最终Verified。

组合草稿examples/complete含纹理、clip、normalize、平方边缘光、UV矩阵、光源数组、out数组、默认系数、struct及两次真实ddx/累积循环；手工展开版在三位置有限oracle得到相同结果，错误第二次系数有数值差异。正式证明草稿和四控制接入仍须主整合后实际检查。早期新metadata测试误将spec当第三位置参数，已改显式spec=，22及随后23项均通过；有限示例首轮把uniform误作位置场输入，修正测试输入形状后通过，没有改产品接口。

## 矩阵/数组最终闭合与循环整合条件

默认完整runner实际PASSED：190单元/53控制，25 PROVED、26 UNPROVED、2 INVALID_INPUT，session48755退出0。完整53目录与摘要冻结artifacts/aggregate/acceptance53；精简证据aggregate-2026-10-26.json。独立Q2源码与六控制先前审读后，追加完整gate事实闭合最终Verified。独立安装副本9bec4aa的三正例及事实审阅也通过。

隔离循环已23单元/Q1，另从旧47控制及aggregate六控制的25正例保存AST重导入，模型与生成Lean逐字相同，日志副本artifacts/loop-old-targets.json；没有执行Lean。主代码/证明/例子/锁相对9bec4aa无差异，确切22文件patch预检查通过。整合条件已在authority/tasks持久化，代码须在本授权提交后才应用。完整57控制将先跑四新控制，再回放全部53旧控制；不重复运行未发生变化的前置190/53作为aggregate闭合条件。

## 循环整合与实际四控制

7241875持久化aggregate闭合、loop整合条件与精确patch后，e5329b7记录已核对的推送；其后才应用副本22文件patch。主目录213单元两次通过（22.643s/21.976s），组合Shader正确版本真实PROVED、错误系数UNPROVED；零次循环非法normalize不执行的目标PROVED，实际执行normalize(0)的同源目标UNPROVED。四项冻结artifacts/loops/acceptance4，明确由attempt2材质及domain-repair单项检查组成，非完整57控制结果。产品提交d348566；完整默认57控制及Q2继续。

初次完整runner在组合证明处停止：simp已把输出相等消去，脚本仍用三元组拆分后的rfl处理剩余域合取。修正为展开真实定义后norm_num完成域与相等，未改源模型/约束；早期目标/脚本冻结first-proof-failure。第二次在零次域证明停止：dsimp已经关闭True目标，后续trivial多余；改为明确True.intro，零次与实际执行负例随后串行符合预期，失败快照domain-first-proof-failure。实际完整日志full-core-57-attempt1/2与loop-domain-repair保留，均不冒充完整成功。

循环Q2源码/冻结四控制/旧25正例兼容审读通过，未发现关键问题；reviewer从当前主源码与保存AST在内存逐字重建四新与25旧模型/目标，核验两正例输入/目标/proof/四模块/锁/标准三项公理，两负例确为输出等式与实际域未证。完整57仍运行，最终Verified待同次Q2事实闭合；本次独立审查未执行DXC/CLI/Lean/测试。最终完整runner本次213单元22.932s通过。

当前唯一主目录完整验收：源d348566，tools/run_demo.ps1默认213单元/57控制，日志artifacts/language-probes/full-core-57-final.log，exec session52499；主tools/proof/examples/锁保持冻结。请先读artifacts/acceptance/result.json及日志状态，不并行运行任何主prepare/check/full单元。独立Windows refresh005已完成，24583已回收；证据windows-loops-2026-10-26.json。Q2代码/四控制/旧25已通过，57 PASSED后须在同次Q2做最终事实闭合并最终push。
