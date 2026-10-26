# 并行扩展：首批可运行切片（修订1）

2026-10-26，基线 b786825。用户要求四个方向并行，明确允许先信任成熟外部工具/论文的能力，经过构建与代表性接入检查后继续。这里不要求提前审计/重证整个外部项目；对我们自己的映射、实际运行结果和产品能力边界仍如实检查。本文承接 plan.md，不改变当前默认实数模式及其证明保证。

## 交付边界与写入分工

采用三个独立 Git worktree 的实现 agent，加主目录的整合者。每个 checkout 仅一个代码写入者。根 agent 独占规划、主目录整合、统一 runner、核心 CLI 的公共入口、当前说明/目录和最终提交/推送。agent 不提交/推送，不再派生子 agent；完成后提供精确文件列表、运行证据和待整合事项，根 agent 检查补丁后合入。现有工具与 mathlib 包可只读复用，禁止同时写同一套生成 proof 文件或共享构建目录。

| 方向 | 本批具体结果 | 独占文件/接口 |
|---|---|---|
| 常见数学运算 | min/max/abs/clamp、源码/、sqrt/rcp/rsqrt/length/distance 的 float1..4，完整材质正负证明，旧目标兼容 | tools/shader_math.py、相关现有数学前端/发射器/有限求值器、test_basic_math、examples/basic-math、手写数学证明；不改统一 runner/CLI |
| 浮点库接入 | 固定 FloatLib 的独立本地 Lean 工程，真实构建和代表运算/特殊值/位解释/舍入反例，实际调用上游运算与规格定理 | prototypes/ieee/*，各自 ignored .tools/.cache/artifacts；不改核心4.24/依赖锁，不声称 Shader CLI 已接入IEEE |
| Compute Load/Store | 实际 DXC cs_6_0 AST→模型→Lean，正常两输入两输出与正负检查 | tools/shader_compute.py、computeformalize.py、test_compute、proof/ShaderFormalize/Compute.lean、ComputePostProof、examples/compute、docs/compute；不改共享数学文件 |
| 并行/同步工具起步 | 本地固定 VerCors 2.4.0，跑实际带权限的并行示例和失效负例，优先采用其 GPU/barrier 示例并记录接口 | 根 agent 独占 prototypes/synchronization/*；外部检查单独报告，不冒充 Lean 或 HLSL 已自动支持barrier |

## 数学切片的固定含义

公共操作目录连接 arity/shape/domain。只接受 float 标量和1..4向量，DXC 已完成 splat 和重载选择；matrix/int重载、/= 后续支持。新数学自动进入 guarded schema4，显式 shared 保持schema6，未用新运算的旧auto生成文字不变。分母≠0、rcp参数≠0、sqrt参数≥0、rsqrt参数>0；clamp为明确区间语义先要求lo≤hi，均逐分量且作为实际执行guard下的待证结论。length/distance零输入合法。域在求值当时快照，不能因覆盖赋值或未使用结果消失；未执行分支不增加义务。有限求值的域外延拓不替代目标里的域检查。

检查覆盖全部新操作、重载/类型拒绝、条件/短路/helper实际域；正常材质与错误输出/未守卫域负例。数学 agent 可独占自己checkout的核心prepare/check；最终默认全套由根 agent 在主目录串行执行一次。

## 浮点接入切片的固定含义

FloatLib固定提交8c8871576a941a86e73dcf0882702b823139aa93，独立Lean4.35和上游固定mathlib；按Lake锁管理依赖。工具链下载约860MiB，使用本地目录与进程环境，空间不足不删既有环境。用上游公开API验证基本运算、sqrt、NaN/±0、位解释往返和重结合0/1反例；实际使用ExecFloat与Spec的现成定理。检查我们自己的例子能构建/运行即可继续，不要求全面扫描外部源码或证明所有位模式。原型与当前核心PROVED报告分开，浮点目标配置/自动HLSL导入后续另行落地。

## Compute切片的固定含义

独立 experimental 命令复用现有DXC验证、typed AST、通用表达式处理和Lean检查机制。首期是一维dispatch，numthreads(x,1,1)，void main(uint3 : SV_DispatchThreadID)，uint32参数cbuffer，StructuredBuffer<float4>与RWStructuredBuffer<float4>，局部值、if/早return、只读Load和输出Store；不接受未建模helper、循环、Texture格式转换、RW跨线程中途通信或同步。

输入contract显式给资源容量、Count范围、dispatch及资源binding身份，允许指定相同身份。内部uint保持32位，启动总线程数≤2^32。每个访问携带执行guard。目标包括双方访问有效、不同线程写写/写读无冲突、完整最终资源相等；未写位置保留初始内存。资源身份相等时仍检查冲突，不能隐含假设不别名。正例两输入两输出后处理；错计算、越界、恒地址冲突及隐藏别名均有负控。输出模型不冒充任意有状态GPU程序的完整语义。

内存统一为物理resource identity→address→float4。同线程按访问顺序维护overlay：Store捕获当时的guard/address/value并更新overlay；Load读取此前最后一个已执行同址Store，否则读取M0，包括通过不同资源变量访问同一物理身份的情况。最终全局内存选择写该地址的唯一线程，再取其最终overlay（最后已执行Store）；无writer保持M0。不同线程写写/写读冲突仍由安全目标排除，不能用模型总化时的任意选择掩盖；同线程的有序多写与别名读写可用。

Compute agent 独占其 checkout 的生成文件/构建；主目录核心CLI和统一验收接入由根 agent 在补丁汇合后完成。若通用AST复用接口发生变化，报告根 agent 统一处理，不修改数学 agent 所有文件。

## 同步工具切片与外部信任

使用官方VerCors Windows 2.4.0 release（SHA256 0b0eb981ade04017aaeb6cfa7d1ebc4561f6fce20eac5c19a1cb38803b3eaefc），复用本机Java21，通过进程JAVA_HOME启动；如需C前端且系统无clang，仅采用本地可得的portable组件或PVL入口，不做全局安装。先跑上游带权限的并行正例，再引入一个具体权限/断言错误检验拒绝路径。若包内GPU/barrier例所需前端可用，则实际运行；否则明确记录尚未跑到的层，不把普通示例冒充GPU同步验证。

此切片解决外部验证器在Windows上可调用及模型接口的可行性，不把其PASS转为本项目Lean内核证明。现阶段信任工具声明的范围，不为未来严格保证先做完整验证器审计。后续HLSL→并发模型桥接仍是我们的实现责任。

## 审阅与集成

计划交叉P：浮点agent审数学、数学agent审Compute与本同步切片、Compute agent审浮点。只查本项目接口、明显语义错误和实际能否跑，不重审外部研究成果。根据当前用户委派，P通过后在execution-authority/tasks持久化精确范围并开始实现，无需再次要求用户批准同一方向。

完成初步检查后交叉Q审实际差异及真实日志。根 agent 只整合已检查的补丁；保持默认核心旧语义和报告，必要时给新实验入口。根负责CLI semantic_modules快照名单；数学切片当前复用既有Lean语义模块、不新增BasicMath.lean，若实施确实新增模块，根必须将其纳入相应新目标的哈希绑定，不改变旧目标文字。运行受影响检查和一次最终默认全套，保存实际结果、依赖与证据。用户此前要求完成后git push，本批沿用，仅发布本项目源码/锁/说明，不发布下载工具或Unity源码，不merge/archive，不改全局环境。

交叉P结果：Compute agent审浮点通过；数学agent审同步通过，Compute要求的同线程alias与多Store顺序已按上述overlay模型明确；浮点agent审数学的语义/消费者通过，新增语义模块的报告绑定由根负责（本切片计划无新语义模块）。修订后的相关段交原审阅者针对核对。
