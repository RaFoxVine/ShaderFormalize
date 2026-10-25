# 可静态确定次数的普通for循环（Candidate，尚未独立P或授权）

这份后续规划服务language组合Shader；实施依赖矩阵/数组切片闭合。首个循环范围选择常见的固定次数for，而非一次实现全部循环：`for(uint i = start; i < end; ++i)`，start/end为固定DXC能表示的纯uint常量表达式，实际次数在导入时确定。此前aggregate-loop-notes讨论的uniform符号次数Nat迭代保留Outlined；未将它写成已完成能力。varying循环、一般while/do、break/continue/循环体return或terminal discard、<=及非单位步长暂拒绝，void helper中的普通return不等于外层循环return。

DXC仍负责解析、作用域、类型、重载，导入器检查确切计数器声明身份、起点、严格上界及++目标。运行次数是自然数max(end-start,0)，最多64次，每个frame嵌套总展开步数最多4096且沿用4096 binding/65536总helper binding预算。超过静态预算直接UNSUPPORTED；不运行到任意fuel后把截断结果当原Shader。每步i<end<=2^32-1，因此增加1不回绕；最后i=end后条件假。最终范围和次数应记录在可审计元数据并进入源/目标哈希。零次循环不执行任何body域或效果，但其语法、类型、调用图仍检查。

共享helper体仍只编译一次，其中有限循环展开为顺序的现有typed运算/调用/效果事件。每次计数器拥有确切uint常量值；用现有uint→real转换供材质计算，常量下标经过aggregate同一地址/域规则。循环body进入独立局部作用域，外层变量修改带回，每次声明局部值重新初始化，计数器只在for内可见。禁止body直接、经字段/下标或out/inout调用修改本循环计数器；静态访问身份检查覆盖嵌套控制和默认调用。未知/带副作用的边界不尝试猜测常量。

if/三元/短路、纯helper、clip、纹理/导数可以出现在body；每次沿用当前完整字段和实际执行guard/alive，不把字段按分支入口清零。clip后实际已丢弃位置不新增域义务，Ops上下文仍记录完整实际mask。不同迭代正常字段按顺序更新；数组/struct/vector部分初始化沿用逐叶规则，零次或漏写不能自动补零。嵌套for按各自已确定次数处理并核对总预算。支持DXC确切的[unroll]属性包装作为编译提示，不由此改变数学次数；未知属性受控拒绝。

预计改动：validation按program扩展语句/for结构与调用图遍历；shared aggregate派生层执行有界静态迭代/计数器保护；accesschecker明确循环初始化、条件、body、++的顺序；类型/源常量求值复用uint检查，不引入signed int或新的数学Ops；runner/examples/实际证明/说明。旧auto后端仍拒绝for，旧模型生成文本保持。

实际oracle：真实DXC测试0/1/多次、非零start、start>end、uint最大附近不回绕、纯常量边界、错误计数器/步长/动态边界/修改计数器拒绝、局部重声明/作用域、嵌套/预算、逐次数组填充和缺初始化、helper/out/default组合、clip后的实际域及导数完整场。至少正常含纹理采样/裁剪/导数/矩阵/数组/循环/struct/out/default的Shader与手工等价版本PROVED；错误次数或系数UNPROVED；零次非法域PROVED与实际执行非法域UNPROVED；原所有正式控制和回归通过，独立Q核对真实哈希/目标/公理。

本Candidate需在aggregate实际接口完成后重新核查可实施性、补充确切文件/证明控制并独立P，才能成为Execution Ready和派生grant。普通静态for是已确定可终止子集；用户未来若需要uniform符号次数或更广循环，按已列职责扩展，不能以本片宣称全部HLSL循环已实现。
