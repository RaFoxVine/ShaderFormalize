# 默认参数与out/inout调用（修订2，Planning Ready；依赖待闭合）

## 目标、位置与依赖

属于overnight language；依赖共享helper切片完成全量验收与独立Q后才可写代码。DXC继续负责声明身份、重载和类型，新增调用层负责默认实参以及HLSL按值复制进/复制出的局部变量效果。消费者仍是显式shared/schema6；auto继续拒绝新语法，旧证明不迁移。矩阵/数组/循环保持后续Outlined，本片不代表完整语言目标完成。

修订1在9e2aab0保存，独立P1 Ready。修订2补足一种正常组合：数值返回函数调用纯计算的void/out辅助函数。不能沿用旧“一律禁止void调用”的近似判断，而应逐函数传播clip/discard效果，继续禁止数值函数改变裁剪状态。P中特别落实两个边界回归：`F(out x, x)`允许读取调用前输入副本；`F(inout x, G(out x))`因实参初始化顺序相关而拒绝。前置共享定义仍在全量验收，不凭本规划写代码。

2026-10-26独立P2 Ready，无阻断；声明后效果分析不依赖稍后才初始化的helper运行缓存。精确代码授权仍待前置完成。

目标是正常按值参数、尾部默认参数、out/inout的float/向量/bool/uint/嵌套struct与if/三元/短路/早返回组合。输出地址先支持现有整变量及struct字段；向量swizzle、矩阵/数组下标输出地址显式拒绝，待aggregate地址层统一扩展。位载体跨边界仍拒绝。

## 数学职责与执行

参数元数据从DXC的HLSLOutAttr/HLSLInOutAttr及默认初始化AST获取；引用类型仅按这些属性规范化，不能把任意C++引用当HLSL参数。CXXDefaultArgExpr必须绑定至本次已解析callee的对应声明默认AST，验证类型、全局作用域和纯输入默认限制；不解析源字符串、不按调用者同名局部变量寻找默认。默认表达式每次实际调用重新计算，域在该调用的结论内；未使用的默认不加到入口义务。所有默认仍做语法/初始化/非递归检查，默认调用边也参与图检查。

helper仍只有一份body model。in/inout接收完整字段；out从未初始化局部开始，不能读取调用者旧值。每条正常返回路径必须完整写出所有out；inout可保持原值。ControlProgram可提供参数符号构造、返回捕获和结果合成钩子，默认实现保持现有结果；shared将普通return和out/inout末值一起按函数局部返回mask选取。void自然结束同样捕获输出，早返回按当时状态捕获。含out/inout的helper及其可达调用暂拒绝terminal discard，保留全字段返回的明确含义；clip非终止且后续完整写出的情况可组合。

在声明收齐后、逐体验证前，shared按确切callee图计算may_clip/may_discard：直接clip与discard分别标记，沿所有普通/默认调用边保守传播；未知callee不能按纯函数处理，递归仍由非递归规则拒绝。数值/record返回函数可调用无clip/discard的void计算helper，禁止直接或间接裁剪。void函数的copy-out由访问集合检查控制，不能把“void”和“改变裁剪”混为一谈。out/inout函数对may_discard另行拒绝。默认auto保留原验证边界。

helper模型新增显式outputs叶字段，结果structure在普通返回字段之后追加copy-out字段，再保留alive/defined；旧schema6无outputs按空列表解释。SharedEmitter、坏引用验证与递归有限求值器使用同一个叶布局函数。全局和stage接口没有out参数，本片不改入口float4 main约定。

调用点先识别全部静态输出地址并检查可写、源类型一致、两两不重叠（同一root且字段路径前缀重叠则拒绝）；读取in/inout完整值，out不读旧值。所有实参求值与默认域先于call事件。返回后同时以调用结果快照写回；不按caller入口清零，if分支合流仍由局部条件选择。各参数自身是独立副本，不能直接让callee写caller字典。输出地址重叠的调用拒绝，不能选择未经规范保证的写回顺序。

## 表达式顺序与作用域

HLSL参数初始化顺序未指定：[规范草案§5.6](https://microsoft.github.io/hlsl-specs/specs/5-Expr.html#function-calls)。当前无表达式写入时顺序无影响，新out/inout不能沿用该前提。

新增基于DXC声明身份和struct字段路径的静态读/写集合检查。一个调用在实参全部求值后才产生自身copy-out写集合；out地址不读取旧值，inout同时读取。针对没有指定顺序的兄弟实参、普通二元操作、构造/初始化分量和采样参数，若一侧写与另一侧读/写地址重叠则受控UNSUPPORTED。检查嵌套调用、默认表达式及未调用函数体。不同字段可证明不重叠，支持独立多个out调用；不靠选择左/右求值顺序避开冲突。普通赋值在RHS后写入；复合赋值若RHS写到旧LHS则拒绝。

if条件先执行；条件式及&&/||按既有HV2021标量短路含义，条件先于被选分支。涉及copy-out的分支在独立符号副本上解释，最终以局部条件合并可写变量；覆盖嵌套struct和提前返回，不能先跑两边再保留最后一次写回。裁剪alive/域仍用实际执行guard，普通字段继续完整。

## 文件、失败与验证

预计shader_frontend.py声明解析/调用校验与全声明后的效果分析提取小钩子；shader_validation.py默认AST、调用图边和允许纯void调用的策略钩子；shader_control.py通用frame钩子；新shader_copyback.py/访问依赖工具由SharedProgram接入；shared_lean/eval的outputs布局与检查；CLI仍shared，不新增依赖/公理/输入假设。新语法由shared显式开启，auto拒绝策略保留。

真实DXC有限测试覆盖默认常数/全局值/纯helper、显式覆盖默认、重复调用；out未初始化读/漏写/分支漏写拒绝、inout保持与修改、嵌套struct独立字段和按值不别名；void自然结束/早返回、数值函数调用纯void/out helper、void内clip且写全输出、无调用坏定义拒绝；if/三元/&&/||变量写回及域。静态负例包括两个copy-out地址重叠、兄弟读写冲突（调用/二元/构造/采样/复合赋值）、未知引用/错输出叶/载体/直接及间接discard、数值函数经多层void调用到clip。独立字段兄弟调用必须接受。向量swizzle输出地址明确UNSUPPORTED。

正式例使用正常helper写法（构建normal/view/光照权重、默认系数、out结构及inout累积），与手工数学等价改写经真实DXC→Lean得到PROVED；错误数值UNPROVED。再以分支copy-out后导数与内联对任意共享Ops证明完整字段/上下文相同，实际执行非法域同源负例UNPROVED。所有旧控制及新控制统一runner通过，独立Q检查真实源码、定义域结论、目标绑定/公理/哈希，文档与本地提交。

若需改变实数模型/域保证/完整字段、允许无法定序的相互影响、扩到新入口或aggregate地址，停止受影响部分重新Ready。无Unity写入/依赖升级/push/merge/archive。剩余language工作保留，不以本片冒充Forward证明。
