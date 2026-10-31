# uint Buffer单pass Compute：binary-compute-004，修订1草案

本片处于Overnight C的PLAN_AND_CODE上限内；具体设计尚待B交付后对齐及独立P，不是现有能力或精确代码grant。范围依据overnight-proposal-2026-10-31.md及该提案的已批准授权包。默认入口、旧Compute schema1/2和既有实数数值含义保持不变。

## 结果与代表用例

提供显式schema3的纯uint单pass Compute入口，两份真实HLSL经同一套uint表达式/分支与内存语义生成Lean目标。结论同时包含全部线程访问合法、不同线程无写写/写读冲突、完整外部最终内存相同；未写地址保留初始内容。它不是整个二进制迁移或多pass交付。

首例为逐元素uint hash，另一例为四路byte打包、写入再读回并解包。长度在固定launch允许的契约范围内全称量化，包含0、尾线程和全部中间长度；不是只检查几个具体Count。uint加减乘模2^32，位运算、比较、移位低5位均复用ShaderIeee.Model。

## 契约草案

constraints严格包含schema、dispatch_groups、count_range、bindings，schema为精确整数3。每个源码资源都有显式identity和capacity；拒绝缺失/多余binding及未知字段。资源只有StructuredBuffer<uint>与RWStructuredBuffer<uint>，显式合法寄存器无重复；仅下标读写，不开放.Load(int)、signed int或隐含数值转换。

一个b0 cbuffer中只有一个uint Count；一个void main(uint3 : SV_DispatchThreadID)，numthreads(n,1,1)，1≤n≤1024；固定dispatch_groups为1..65535，总线程T小于2^32。count_range=[L,U]满足0≤L≤U≤min(T,2^32−1)，描述此固定launch覆盖的长度子集。uint地址先做模运算再转Nat，不能将无界Nat地址冒充uint计算。

capacity允许0..2^32，不强制U≤所有资源容量；每次真实访问的边界由完整safe目标验证，允许死资源或受更强guard保护的小资源。相同identity必须同capacity、同uint元素和起点/stride4；不同identity是任务明确声明的独立物理资源。不接受offset/stride/格式/部分重叠view字段。相同identity的只读/可写声明允许，正确性由有序overlay和安全目标决定，不能悄悄假定不别名。

入口的DispatchThreadID仅支持x/y/z分量读取，y/z固定零，不借此开放一般bool向量。纯helper按值uint/bool参数与局部计算可用，但不允许helper直接访问全局资源。一般循环、资源循环、float值/资源、纹理、groupshared、barrier、atomics、多uniform、多pass和符号dispatch均不在本片内；具体文件应与B实际抽取的共用机制对齐。

## 前端与执行责任

现有ComputeProgram自己拥有execute与实数float4表达式，不能改个资源类型就当作二进制。新增UintComputeProgram组合IeeeSemantics与GuardedProgram，拥有Compute声明、Count/dispatch输入、资源节点和访问事件；共享层继续拥有uint表达式、SSA、作用域、分支、helper和提前返回，不再复制第三个语句执行器。

Program构造中Resources与function_declaration硬编码需提成默认保持旧行为的make_resources/read_function钩子。新入口自行建立Count/dispatch符号并调用共享invoke，不复制整个Program.__init__。必要main属性读取保持与普通helper解析职责分开。

Store通过validate_statement/execute_statement接入；读取通过资源表达式/地址扩展接入。每次访问捕获当时guard、物理identity、uint地址和值。相同线程按源码顺序更新overlay，后续Load包括不同声明别名视图都读取此时overlay；最后一次写入决定该线程该地址结果。

纯IEEE解释目前可eager处理&&/||/?:，有资源后必须增加明确的operand-evaluation hook：先捕获左值/条件，&&右侧使用原guard∧左值，||右侧使用原guard∧非左值，三元两臂分别使用条件及其反。try/finally恢复guard，嵌套表达式与helper调用不能泄漏执行条件。旧纯表达式默认行为和目标字节保持；资源未选侧不生成有效访问义务。

新emitter复用IeeeEmitter的uint表达式，仅补count/thread/load叶、有序事件与内存解释和完整目标，不能再写uint运算映射表。

## 内存语义与完整命题

从现有ShaderFormalize.Compute提取不依赖Color数值的泛型memory核心：Memory α、Access、ThreadResult α及store/touched/finish/valid/independent/safe和对应通用定理。旧Compute模块保留原名称的Color特化及包装，原Compute/Texture消费者保持接口和目标可比较。新uint Model特化为UInt32。

每个线程从同一个任意initial memory开始，线程内Store更新overlay，Load读取当前值。safe包含全部实际Load/Store bounds和任意不同线程的WW/WR同址排除。最终finish只在这些安全结论下与执行对应；无写者地址保持initial。非法访问即使总内存函数仍有值，也不能绕过safe。

完整expected量化任意initial及UInt32 Count，在固定输入契约下同时要求原版safe、改写版safe以及全部物理identity/地址的最终memory相等。无需假定初始uint正常/非NaN，也不能仅比较声明输出资源的一部分。此片初始memory每个地址都是任意UInt32，不提供scratch初始化位或跨pass可见性模型；用户局部未初始化仍由前端拒绝。

新模型标识compute-uint-1，只区分入口/IR，不改变现有uint规则或引入新的浮点/GPU profile。成功报告使用完整Compute的PROVED，并显式记录uint32语义、模型标识及gpu_profile_matched=false；不能用同一个词隐藏real与uint的适用前提。

## 绑定、错误与集成

computeformalize仅对显式schema3选择新路径；旧schema1/2与默认保持原行为。新路径的最外层覆盖锁获取、prepare/check、timeout及审计，原子写最终result，不能异常后遗留IN_PROGRESS或旧成功。区分INVALID_INPUT、UNSUPPORTED、UNPROVED、ENVIRONMENT_ERROR、INCONCLUSIVE与内部错误；磁盘不可写则明确stderr/nonzero，不能声称已落盘。

绑定实际HLSL/约束快照、DXC AST、IR、生成目标、全部自有语义依赖、提交证明、固定锁和独立Verify。证明结束再次核对源/目标指纹，cache key覆盖新泛型memory及所有传递语义模块。expected使用原三公理白名单；伪造True目标、sorry、额外公理和中途篡改均拒绝。旧schema异常遗留问题记录为后续问题，不顺带扩张本片修改。

预计新增shader_compute_uint.py、shader_compute_uint_lean.py、单元及专用suite、泛型ComputeMemory与uint Model、examples/compute-uint和实际proof；调整Program构造hook、IEEE operand hook/emitter扩展点、Compute特化包装及CLI显式路由。能力说明、coverage、tasks与证据同步。

## 真实验收与停止条件

两个正例分别覆盖hash的helper/内联、地址模运算；byte packing的多个uint输入输出、RW读回、同线程最后写入及别名overlay。独立identity的packing证明不能直接套给改变语义的alias布局；另有真实共享identity正例验证别名。

错误计算、Store越界、常量地址多线程WW、alias邻元素WR至少各一负控，必须成功导入并编译生成模型后在SubmittedProof实际失败。另测false分支、短路和三元未选侧的越界访问不产生执行义务，活动侧仍须安全。有限见证可辅助定位，不替代全称Lean证明。

单元检查Count边界0/1/组边界/尾部/U、地址0/0xFFFFFFFF和模溢出、移位0/31/32/33/最大uint、容量/identity不一致、extra字段、非法类型、终态覆盖以及目标/语义篡改。负例保留实际失败原因，UNPROVED不冒称已证伪。

B完成后先对齐实际公共接口再做独立P，记录精确grant后实施。新单元与真实正负例初测后独立Q；泛型memory和共享hook变更需比较旧目标并串行运行完整核心、IEEE、原型及新uint Compute控制。没有依赖更新或Unity行为。需要新公理/profile、跨线程通信、弱化安全/完整输出或不可用关键oracle时停止受影响项；普通实现和证明失败自主修复。
