# Overnight：数学覆盖、HLSL浮点与二维Compute

2026-10-27。用户在阅读四项具体范围后回复“按上述四项继续 Overnight”。本批沿用信任成熟外部工具、代表性接入验证的方式，不全面审计FloatLib或VerCors。当前默认实数路径、Unity独立性和已发布证明保证不变。

上一批242单元/69项控制已通过，证据独立Q Verified，收尾提交d3b7f5f已推送。新Session shader-overnight-expansion-2026-10-27已封存并running，具体Grant见execution-authority.md。独立P未闭合的切片不得开始产品代码。用户已委派本范围内具体规划和实现，无需逐项重新请求人类确认。

## 目标、责任与共同边界

| 工作 | 对使用者的结果 | 唯一实现者 |
|---|---|---|
| 七项基础数学 | 正常HLSL实数路径支持HDRP实际使用的floor/ceil/frac/step/smoothstep/cross/reflect | basic_math_expansion |
| HLSL浮点证明入口 | 两份普通HLSL经DXC进入FloatLib，agent可prepare、编写证明和check | ieee_library_integration |
| 二维纹理Compute | 曝光/Bloom合成及tone mapping的两输入两输出正常Shader，完整内存和安全目标 | compute_load_store |
| HLSL同步安全入口 | 一个带groupshared和无条件屏障的实际HLSL自动交给VerCors检查访问安全 | root |

root独占主目录、公共proof_contract提取、统一runner、coverage/current docs及最终提交推送。agent不再派生agent、不提交/推送，不修改别的所有者文件。交叉P/Q为IEEE审数学、Compute审IEEE、数学审Compute及同步；共享检查提取在IEEE Frame中审阅。

不实现完整HDRP/Lit、一般动态循环、原子/Wave操作、完整GPU内存模型、同步Lean证明桥接或Unity修改。未完成证明只能报告UNPROVED，外部安全结果不冒充Lean PROVED。每项实际验证及独立Q闭合后整合、提交、推送。

## 数学：七项操作及真实执行域

复用现有shader_math目录、typed AST和schema4/6；默认float仍解释为实数。floor/ceil/frac/step/smoothstep接受float及float1..4逐分量和DXC splat；cross仅float3×float3；reflect为DXC合法的同宽float1..4。

floor/ceil为整数floor/ceil再转实数，frac=x-floor(x)。step(edge,x)在x<edge时0，否则1，包含相等边界。smoothstep为官方饱和多项式，逐分量lo<hi进入实际执行guard下的待证结论；不增加隐含前提，unused实际计算也保留义务。cross和reflect使用标准代数式，reflect不假设法线单位长度。

所有权：tools/shader_math.py、shader_fragment.py、shader_control_lean.py、shader_shared_lean.py；shader_frontend.py仅确需registry接线时修改。新增test_math_extensions.py、examples/math-extensions、MathAlgebraProof/MathQuantizeProof/MathSmoothProof。公共旧函数签名不改；新增向量分量发射接口供cross/reflect，兼容symbolic Fin索引。root负责runner/docs/coverage。

新floor imports仅出现在使用该族的新模型，旧生成目标逐字不变。已只读核实所需580个Mathlib闭包模块的olean均存在；不触发共享依赖补编。未知缺失交root串行处理。

完成标准：3PROVED/3UNPROVED完整控制（代数展开、量化、smoothstep域及错误边界/零界/反序），加负frac、整数点floor/ceil、step相等、float1..4/splat和形状拒绝单元。旧27个冻结目标及本轮已有3数学正例重生成保持一致。round、超越函数、整数/矩阵重载不在本片内。

## 浮点：独立HLSL转换与检查

新增tools/ieeeformalize.py prepare/check，使用已安装本地Lean4.35和固定FloatLib，独立生成/提交/验证目录，不写核心proof目录。成功为IEEE_PROVED，profile为binary32-rne-preserve-subnormals-separate-ops-v1：最近偶数舍入、保留次正规数、每个源码运算分别舍入、不隐式FMA、NaN策略沿用库。输出按完整存储位相等，输入量化所有binary32存储值，gpu_profile_matched=false。

首批接受空schema2约束，非空ranges/nonzero_vectors明确拒绝。除零、负sqrt按浮点特殊值解释，不沿用实数定义域义务。

支持float4 SV_Target[0]入口、float1..4输入/cbuffer、普通struct和按值纯helper、顺序局部/字段/整值赋值及+=/-=/*=、构造/swizzle、四则/负号/sqrt、标量float比较、bool逻辑及?:。标量uint只用于常量、局部复制和asfloat/asuint位解释。拒绝一般if、循环、资源效果、其他intrinsic、数值转换、uint算术/移位、矩阵数组、out/inout和默认参数；所有函数包括未调用函数均检查白名单、初始化与调用上限。

shader_ieee_frontend.py拥有独立浮点IR，复用parse_tree、源码位置和TypeRegistry等声明处理，不能使用PackingProgram的实数/载体模型结果。shader_ieee_lean.py保持每个运算节点和舍入顺序；源码十进制用精确Rat/OfScientific一次舍入，不能先经Python float或发两个Binary32常量相除。负零保留独立一元负号。

原型Model薄封装在prototypes/ieee/ShaderIeee/Model.lean；生成模块位于prototypes/ieee/proof，独占.cache/ieee-verification.lock，忙时INCONCLUSIVE且不覆盖正在运行的报告。runner明确使用独立4.35环境，不调用硬编码4.24的运行器。持锁后IN_PROGRESS，失败覆盖旧成功。报告绑定源/AST/IR/目标/证明/语义、核心DXC锁、浮点锁、manifest及工具版本/哈希。

root提取tools/proof_contract.py：共同拥有现有Verify模块文本生成和三公理审计；旧文本/行为逐字兼容，shaderformalize继续导出原audit_axioms。该模块不拥有Lean版本、目录或环境。IEEE agent不改核心shaderformalize.py。

完成标准：正常struct/helper/cbuffer Shader任意输入等价获证；任意float→bits→float往返获证；四则/sqrt/比较/?:保持顺序的等价。重结合0/1、±0误合并、NaN自比较改true为负例并实际运行见证。sorry/额外公理/伪造目标/目标变更/工具缺失/旧成功状态覆盖控制，保持同一三公理白名单。旧4.24实数正例和共享检查回归保持；不要求枚举全部编码或重证整个FloatLib。

## Compute：二维纹理后处理

新增schema2，旧schema1六例保留原输入/生成目标及证明。typed scalar uint/float uniform表要求每个字段给精确范围。二维numthreads/dispatch的z=1，每轴ID不溢出uint32；线程内部可逆线性编码，不按遍历顺序执行线程。

Texture2D<float4>.Load(int3(x,y,0))和RWTexture2D<float4>[uint2]写入，限mip0完整float4视图。纹理binding为identity+dimensions，Buffer维持identity+capacity；同identity必须同物理kind、尺寸及布局。SRV/UAV不是不同物理kind。拒绝跨Buffer/Texture类别、不同mip/base/stride/format换算。

uint/int标量及二三分量构造、swizzle、精确32位转换、必要有符号解释/字面量/加减/比较均保留，不转换成实数。Texture Load先判断有符号二维范围，越界为零且无物理读事件，界内才读线程overlay。Store必须单独证明二维界内，不能把非法Store的guard改false来掩盖安全义务。未写内存保持M0、同线程最后Store和写后读、跨线程WW/WR规则均保留。

纯helper允许float1..4参数/结果、局部计算/赋值、if/else、终结return及嵌套调用；拒绝递归/资源访问/out/inout/全局写。固定数学白名单min/max/saturate/dot/divide加原有基本运算，共享shader_math只读，不自动接受另一agent新增intrinsic。分母非零在求值时按SSA与实际guard捕获，unused值/实参不能删除义务。

首例17×13、numthreads(8,8,1)、派发[3,2,1]，两个纹理输入/两个输出，Width/Height受尺寸范围约束，Exposure∈[0,4]、Bloom∈[0,1]。先max合成颜色与0，再乘非负Exposure，再/(1+color)；不额外假设初始纹理值非负。

独占shader_compute.py、computeformalize.py、run_compute_suite.py、test_compute.py，新shader_compute_texture.py/shader_compute_math.py，ComputeTexture.lean、ComputeTexture*Proof、examples/compute-texture、docs/compute.md。Compute.lean仅新增lemma，不改旧定义；共享前端/数学文件/核心Model/锁/默认runner只读。同步CLI schema、编译顺序/缓存key、语义模块快照、报告及有限求值器。

新Execution固定字段result、mathDomains、storeBounds；每次Store独立追加source_guard→二维inbounds到storeBounds，不能因实际overlay按guard∧inbounds更新而消失。完整目标对双方每个已派发线程要求mathDomains∧storeBounds∧safe result，再比较完整最终内存。Load只记录guard∧inbounds的物理读，OOB返回零不额外要求guard→inbounds。3个新正例：后处理、同线程纹理alias/最后Store、OOB Load为零；5类负控：错输出/二维地址、越界Store、WW、alias邻像素WR、未守卫零分母。旧六例2P4U保持；补未执行分支、unused helper实参、signed wrap及未知mip/intrinsic拒绝单元。

## 同步：HLSL到VerCors的访问安全原型

独立tools/syncformalize.py及shader_sync.py，从固定DXC cs6/HV2021 typed AST导入，不自己解析HLSL语法。限一个dispatch组、numthreads(2,1,1)、SV_GroupThreadID、一个groupshared float4[2]、一个StructuredBuffer<float4>输入和一个RWStructuredBuffer<float4>输出。合同容量为2、物理identity显式互异；相同身份返回UNSUPPORTED，不隐含无alias前提。

支持uint索引局部、常量和加减；PVL对每次uint加减结果显式模2^32，访问另证明0≤index<2，不能直接抹掉wrap。支持整float4复制、shared读写，以及0或1个无条件GroupMemoryBarrierWithGroupSync，最多两阶段。拒绝所有控制流/提前return/helper、影响地址的float计算、其他barrier/atomic/Wave。固定线程间交换例：shared[i]=Input[i]；barrier；Output[i]=shared[1u-i]。

float4作为不影响控制/地址的opaque数据；安全结果限定为访问界限、跨线程读写冲突以及该无条件barrier的权限交接，不声明值已初始化、数值等价或一般GPU模型。每个实际读写必须逐事件来自AST进入PVL。权限注解只描述线程组初始所有权及真实barrier的合法重分配，不能按期望交换模式补权限或assume地址/冲突结论。删除barrier也删除重分配。正确版通过，删屏障及共享同址写入版必须到实际权限失败，解析/环境失败不能冒充负例成功。

报告独立标识EXTERNAL_SAFETY_VERIFIED或外部安全未证，与核心Lean PROVED分开；保存源/AST/合同/PVL/工具锁/日志hash，启动IN_PROGRESS并覆盖失败状态。源码/模板/examples归root；不引入Lean同步桥接、一般GPU内存模型或验证器内部审计。

## 工作目录、依赖、集成和停止条件

复用适合的Math/IEEE临时checkout，先核对旧改动均已整合并做可恢复的本地snapshot commit，再checkout本批最终主目录基线，不删除ignored依赖。Compute旧checkout已归档，另建一个当前基线checkout并物理复制已验证本地4.24/DXC与1.55GiB包缓存；不增加指向主目录的新共享junction。

Math已有共享链接只读使用，任何共享依赖缓存缺失交root串行处理，不归档这些含链接目录。IEEE复用自己的独立4.35及FloatLib缓存；所有安装与配置均为仓库局部/进程局部，不改全局环境。

先固定公共接口和所有权、通过独立P并持久化Grant，再开始代码。root整合前校验精确文件列表/基线哈希，只接入已初步验证和独立Q通过的结果。每项最多三轮正式P/Q；关键问题不能闭合、需要改变已批准保证、需要删除用户数据/改全局配置时停止该项并记录恢复条件，继续其他独立工作。不以未经批准的公理、范围假设或隐藏顺序化换取成功。

本夜最终统一核心回归一次，IEEE及同步各运行独立实际控制；证据按实际结果发布，不要求重复安装/重建全部上游。完成项随时本地提交并非强制推送工作分支。正式H-X及TreeDive Node归档不在授权内。

## 独立P状态

数学：IEEE独立P Verified；floor缓存无已知缺失。实施注意双方全部helper的floor导入、inactive域外安全总化、symbolic Fin的整体向量发射及DXC实际reflect重载。

IEEE：Frame完成，等待Compute审阅；共享检查提取由root独占。

Compute：数学独立P Verified；物理kind、OOB Load无读事件、Store安全单独待证三项已按上述固定字段闭合。

同步：数学独立P2 Verified；显式uint32模语义和AST逐事件/真实barrier权限两项已闭合。
