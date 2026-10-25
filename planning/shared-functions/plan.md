# 通用函数扩展：完整输入函数与共享定义（修订1）

## 目标和框架

overnight的language项要扩展共享函数表示、默认参数、out/inout、矩阵/数组及普通可证明终止循环，最终用正常写法Shader验证组合能力，再用于固定Forward。当前不新增浮点编码、不以fuel静默截断循环、不隐藏输入域、不改变原公理白名单。后续能力逐片Ready，独立P后派生精确grant；本页先将函数入口/返回的完整字段语义修复列为Ready，其余仍规划。

DXC继续拥有语法/类型/重载及引用；转换器拥有源程序到数学值/执行条件的解释；Lean只证明完整目标。旧schema2/3/4/5和默认CLI保留；共享函数后端拟新增schema6和显式--frontend shared入口，复用现有数值/位操作/采样/导数模型。函数实参是E上的完整字段函数，调用者提供实际执行条件；callee返回完整值字段、裁剪保留条件及已执行的定义域。后续out/inout将通过按值输入/结果及明确copy-out处理，不引入外部内存写入。矩阵/定长数组由显式形状与有限聚合承载；循环必须有真实终止理由，不能假装有限fuel等于原while。

共享定义应一次生成helper数学体、让调用引用它，避免4096全内联绑定无法承载Forward。所有函数体的未知语义/初始化仍拒绝，不借不可达改变现有失败承诺。未来语法能力的准确文件/接口/迁移/验证会在对应Ready切片冻结；本项不提前实现未Ready后端。

## 已确认的前置缺陷

当前ControlProgram.invoke以包含调用者执行条件的guard作为返回值选择mask。位于分支里的`Identity(a.y)`因此在分支外被填0，作为ddx完整输入时与直接a.y不同，违反现有“普通别名/算术保留完整输入字段，guard外不一律清零”的契约。ignored artifacts/language-probes/helper_field_probe.py真实DXC探针：输入点a为(0,2),(1,4),(1,8)，同一有限导数操作下原版分支输出9、内联版7；差异来自输入首点2被错误清0，不是两份shader本应不同，也不是GPU证据。现有packing定理不含这一场景，其结果仍有效。

## Ready：分开函数局部控制路径和调用执行前缀

当前Flow.mask/current_guard保留为函数内部的路径及return完成条件，不含调用者入口条件；新frame.entry保存进入此函数时的实际guard。guard()统一计算frame.entry∧当前局部路径∧shader alive。未处于frame时entry=True。表达式快照、normalize/cast/shift定义域、采样/导数上下文、clip/discard均继续使用实际guard。

invoke先在caller frame读取实际entry，callee从局部True路径执行，保存/恢复caller frame和current_guard。参数和数值计算不因入口条件而清零。if的分流/继续mask来自局部路径和条件；return保存局部路径选择值，不把caller.entry或alive并进返回值选择。纯值helper所有正常返回路径给出完整数学值；main的输出仍由全局alive生成Option。void helper return仅结束本次调用，clip/discard保留全局效果；helper外的alive仍受caller实际执行范围限制，不能杀掉未调用位置。

本项只改ControlProgram的frame/guard/branch/return/invoke，必要的初始化保存及控制流辅助；不改Ops定义、基础数学、uint定义、constraints或公理审计。schema4/5 IR仍显式记录每个实际guard，序列化结构不变，翻译结果hash变化正常重新绑定。旧straightline schema2/3解释不变。后续共享函数后端必须遵循此分工，不能把此bug照搬到摘要调用中。

## 验证、迁移及停止条件

新增真实DXC有限求值：分支下恒等helper与直接输入的ddx/dd y完整字段一致、nested helper和struct返回保留字段，void裁剪/提前返回只影响调用范围，未选分支的helper normalize/cast仍不要求合法。实际执行但被忽略的实参继续检查域。继承已通过的packing、裁剪、布尔短路等回归。

新增形式正例为`ddx(Identity(a.y))`与`ddx(a.y)`处于相同分支；输入范围不限，必须对共享任意Ops证明相等。另用a恒0约束证明未调用的normalize helper不产生非法域；将分支改成实际调用时，同一证明必须UNPROVED且失败指向定义域。将这些控制加入统一runner，全部现有回归/32控制及新增控制跑完；独立Q核对真实字段/guard和目标审计，本地提交。文档在当前Control说明处阐明局部路径与调用执行条件，不维护另一个数学规范。无Unity调用、依赖变更、push（由publish统一）、merge或归档。

若需要放宽未知语义策略、改变Opaque操作上下文/定义域保证或把未执行位置当真实GPU邻居模拟，停止受影响项另作规划。普通局部实现细节与保约定修复自主推进。
