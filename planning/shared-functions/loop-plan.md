# 可静态确定次数的普通for循环（修订2，P2 Ready，隔离实施可授权）

这份后续规划服务language组合Shader；主目录整合和形式验收依赖矩阵/数组切片闭合，隔离实现的确切前置见文末修订2安排。首个循环范围选择常见的固定次数for，而非一次实现全部循环：`for(uint i = start; i < end; ++i)`，start/end为固定DXC能表示的纯uint常量表达式，实际次数在导入时确定。此前aggregate-loop-notes讨论的uniform符号次数Nat迭代保留Outlined；未将它写成已完成能力。varying/uniform符号边界、一般while/do、break/continue/循环体return或terminal discard、<=及非单位步长暂拒绝，调用的void helper自身正常return不等于外层循环return。

2026-10-26修订1独立P1 Ready，无关键阻断；核对真实DXC结构、终止与预算、完整字段/域、逐叶初始化、计数器身份保护和实际组合oracle。修订1保存在1d0b227；修订2仅将开发写入隔离到独立副本，不降低主目录整合的前置或最终验收，须独立P2及精确grant后才实施。

DXC仍负责解析、作用域、类型、重载，导入器检查确切计数器声明身份、起点、严格上界及++目标。运行次数是自然数max(end-start,0)，最多64次，每个frame嵌套总展开步数最多4096且沿用4096 binding/65536总helper binding预算。超过静态预算直接UNSUPPORTED；不运行到任意fuel后把截断结果当原Shader。每步i<end<=2^32-1，因此增加1不回绕；最后i=end后条件假。最终范围和次数应记录在可审计元数据并进入源/目标哈希。零次循环不执行任何body域或效果，但其语法、类型、调用图仍检查。

常量求值只接受准确的uint32字面量、literal int到uint的固定IntegralCast、括号以及已有纯uint取反/负号/加减乘/位运算/移位；所有结果按uint32取模，常量移位必须先检查count<32。拒绝一般变量、uniform、调用、浮点转换和有副作用表达式，不把局部或helper参数猜成常量。标准循环必须有一个DeclStmt uint计数器初始化、一个Null槽、该计数器直接读值<常量上界、同一身份的前/后缀++、一个语句body。常量上界是表达式的uint32结果，例如UINT_MAX+1为0而非自然数2^32。记录start/end/count只使用实际求值结果。

共享helper体仍只编译一次，其中有限循环展开为顺序的现有typed运算/调用/效果事件。每次计数器拥有确切uint常量值；用现有uint→real转换供材质计算，常量下标经过aggregate同一地址/域规则。循环body进入独立局部作用域，外层变量修改带回，每次声明局部值重新初始化，计数器只在for内可见。禁止body直接、经字段/下标或out/inout调用修改本循环计数器；静态访问身份检查覆盖嵌套控制和默认调用。未知/带副作用的边界不尝试猜测常量。

实现使用新shader_loops.py的LoopProgram继承本片前置的AggregateProgram；在validation/ControlProgram增加默认不接受/不执行的语句扩展钩子，LoopProgram负责for结构、计数器保护、静态次数和有限顺序执行。进入循环复制作用域symbol表，保留外层可写symbol的修改；每轮body局部表重新创建。嵌套循环共享当前frame的展开步数预算；每个helper/main分别计数。初始化值和最后值不作为任意位置输入，不改输入接口/范围。元数据只辅助审计，数学运算本身仍是现有事件，不靠元数据假定循环输出正确。

if/三元/短路、纯helper、clip、纹理/导数可以出现在body；每次沿用当前完整字段和实际执行guard/alive，不把字段按分支入口清零。clip后实际已丢弃位置不新增域义务，Ops上下文仍记录完整实际mask。不同迭代正常字段按顺序更新；数组/struct/vector部分初始化沿用逐叶规则，零次或漏写不能自动补零。零次body仍检查未知语法/重载/调用及计数器保护；初始化读取由实际展开步检查，不能把被跳过body误记为实际执行。未调用helper仍编译它自己的所有实际循环步骤。嵌套for按各自已确定次数处理并核对总预算。支持DXC确切的[unroll]属性包装作为编译提示：AttributedStmt中的无children HLSLUnrollAttr带单个非负整数，另一个child是标准ForStmt；参数不改变数学次数；未知属性受控拒绝。

文件及迁移：新shader_loops.py、shader_validation.py语句策略钩子、shader_control.py执行钩子、shader_frontend.py shared分派到最终LoopProgram、shader_access.py循环顺序/写集合策略、test_loops.py、verify_demo.py/run_demo.ps1组合控制、examples/complete与手写证明、docs/agent-workflow/shared-functions及README当前边界。类型/源常量求值复用uint检查，不引入signed int或新的数学Ops；旧auto后端仍拒绝for，旧模型生成文本保持。不替换现有DXC/Lean/依赖配置。

实际oracle：真实DXC测试0/1/多次、非零start、start>end、uint最大附近不回绕、纯常量边界及wrap、错误计数器/步长/动态边界/修改计数器拒绝、局部重声明/作用域、嵌套/预算、逐次数组填充和缺初始化、helper/out/default组合、clip后的实际域及导数完整场，并与手算结果比较。正式控制四项：正常含纹理采样/裁剪/导数/矩阵/数组/循环/struct/out/default的Shader与手工等价版本PROVED；错误次数/系数UNPROVED；零次非法normalize域PROVED与实际执行非法域UNPROVED。前一项必须保留任意E/Ops且真实使用这些操作，不使用固定有限采样或identity导数替代。原所有正式控制和回归通过，独立Q核对真实哈希/目标/公理、旧生成文本和次数/无截断检查。无Unity验证不宣称GPU一致。

目前无本片代码权限；修订2经P2后只派生下述确切隔离授权，主目录整合仍须aggregate完成并核对其地址/partial初始化/程序类接口没有合同漂移。停止条件沿用language：需实数/完整字段/实际域变化、不能证明次数或需隐式fuel、关键oracle不可用、三轮审阅有关键未闭合问题。普通静态for是已确定可终止子集；uniform符号次数或更广循环继续Outlined，不能以本片宣称全部HLSL循环已实现。固定DXC已成功解析原始loop-static/loop-unroll探针：ForStmt五槽、前/后缀++和AttributedStmt/HLSLUnrollAttr均有实际AST记录。

P要求落实的已有合同细节：正式组合正例至少两次真实迭代，并使Ops/裁剪或累积状态参与迭代关系；嵌套预算计入每次外层和内层body执行，包括空body，新增空body超预算负例；循环元数据的规范摘要实际写入新模型的生成目标（可用注释摘要使GeneratedModel字节绑定），旧无循环模型不增注释或改变文本。元数据不能替代真实顺序展开的数学定义。

## 修订2：验收期间隔离实现，主目录仍冻结

9bec4aa的aggregate已有25新单元、六个正式控制及Q2源码/冻结证据审读；默认190单元也通过，53正式控制仍在运行，Q2完整结论等待这个结果。为使root继续工作而不污染正在验收的源码，允许在仓库ignored的artifacts/loop-development创建来自9bec4aa的专用Git clone，root保持唯一writer；主目录tools/examples/proof此期间一字不改。它是开发副本，不冒充空目录依赖安装或独立Windows验收。

开发副本只复制Git源码，用目录junction将其.tools指向本仓库已锁定、只读使用的.tools。创建前核对两个绝对路径均在本仓库及指定开发目录内、目标不存在；不覆盖用户目录。没有共享proof生成目录、.lake或可写package build目录；只运行DXC新循环单元/内存Lean生成，不在副本prepare/check或运行含CLI集成的全套。工具复用公开记录，不声称该副本依赖独立安装。实际形式证明仍在主目录整合后进行。

aggregate的53控制和最终Q若失败，主目录整合停止，先处理基线；隔离工作只可修复与冻结9bec4aa合同兼容的细节，遇到基线语义变化则重新规划受影响部分。全部通过后，核对主产品文件未变或逐项审查差异，再以可审阅patch将副本的确切loop改动应用到主目录；不merge/rebase、不覆盖用户变更。整合前在authority/tasks持久化条件已满足。新增四控制、全部旧控制/回归、独立Q、当前说明和最终push仍须完成，未因隔离开发豁免。

此安排只改变代码写入位置和实施时机。循环的可接受语法、数学语义、职责、停止条件及最终完整oracle与P1相同；精确grant必须分别说清隔离阶段可做什么，以及主目录整合条件，不凭本规划直接写代码。

2026-10-26独立P2 Ready，核对冻结9bec4aa至HEAD产品和工具锁无差异、ignore边界、DXC helper只读工具行为、原始for/unroll AST及隔离/条件整合安排。新测试不得导入AggregateTests等整类到测试模块全局，防止discovery带入prepare测试；仅复用模块辅助方法/常量并运行确切新循环集。最终主目录完整oracle未豁免。
