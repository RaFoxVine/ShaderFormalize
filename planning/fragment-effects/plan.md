# 纹理、裁剪与导数：本轮完整约定（修订1）

用户目标：在已支持结构体/辅助函数的 DXC typed AST → 理想实数 IR → Lean 流程上，验证一对正常组织、手工等价改写的片元 HLSL，并在现有 Unity/HDRP 工程实测。用户此前授权先跑通，无需另行等待完整方案人工审阅。沿用 Smart 的独立 P/Q、Git 审阅与本地依赖管理，不使用 Lavish。

## 范围与责任

DXC 负责语法、类型、重载和声明引用。适配器只解释接受的 typed AST；未知节点/重载/资源/控制流必须明确 UNSUPPORTED。保持现有 schema2 数值模型、例子、约束与证明兼容。新 schema3 面向片元函数，保留每个执行绑定和裁剪事件的顺序，不执行浮点优化。

支持 Texture2D<float4>（或默认 Texture2D）与 SamplerState 全局显式 register(tN)/register(sN)，每种至多16、无别名和重复槽位；资源声明布局在两边完全比较。支持无 offset/status/clamp 的 Sample、SampleLevel、SampleGrad，UV float2、level float、grad float2。方法由其资源声明身份和 DXC 类型检查；不接受其它成员方法/资源别名/资源参数。

支持 ddx/ddy/ddx_fine/ddy_fine/ddx_coarse/ddy_coarse 的 float1..4 重载；clip(float1..4)，discard，if(单个标量实数比较) discard（可带单语句花括号，无 else），以及普通 void 辅助函数。比较 < <= > >= == != 仅用于上述条件；不引入一般分支、循环、bool输入或bool局部变量。裁剪只允许 main 和 void helper 的语句；返回数值/结构体的 helper 必须不改变裁剪状态，也不得调用 void helper，从而不引入表达式求值顺序歧义。void helper 可无return或末尾return;。

现有 struct、默认按值函数参数、字段读写、绑定快照、normalize 域检查和所有资源上限继续生效。调用参数即使被忽略也要执行；未调用函数仍检查语法。静态语法检查和实际展开共享同一个采样/谓词/效果规则。

## 数学表示

任意位置集合 E；varying 输入是 E→ℝ/向量，uniform 保持常量。算术逐点执行。共享 FragmentOps E 作为定理的任意参数，包含导数与三个采样模式；不是新增公理。导数接收轴/模式标识、已有裁剪条件的有序列表和完整输入函数；向量逐分量。采样接收纹理与 sampler 名称、模式专属参数的完整函数，以及同样的裁剪上下文。不同资源、采样模式、LOD、grad 或导数模式不合并。不假设滤波细节、导数链式法则或乘法法则。

上下文是之前每次裁剪的保留谓词函数序列，不模拟 quad、邻居或 helper lane；相同完整输入函数和相同上下文应用同一共享操作必然相等。保守保留上下文，避免默许将导数/隐式采样跨 discard 移动。输出是 E→Option Vec4：None 表示丢弃，Some 表示保留及颜色。clip 每分量 >=0 时保留（含0），discard 无条件不保留，if(p) discard 保留 ¬p。

IR 存储有界 SSA 绑定、裁剪条件、事件顺序，opaque节点只记录已有上下文长度，避免复制整棵函数。新 shader_fragment.py 发射函数级 Lean 与效果，旧 shader_lean.py 保持数值生成入口兼容，按 schema 选择；新 Fragment.lean 定义共享操作和输出模型；报告对实际语义模块均提供哈希。

## 消费者、例子和验收

新增 examples/textured：结构化入口，UV变换/采样/颜色 helper、三种采样、显式 ddx/ddy、alpha clip 和条件 discard；原版与改写版改变代数展开/辅助函数组织，保留效果次序。Lean 手写证明完整输出函数相等；约束仍来自现有 schema2 范围文件，对 varying 逐点、uniform 常量施加。

回归覆盖三个采样模式和参数身份、六种导数模式、clip 零边界与向量 any-negative、discard 条件边界、void调用、裁剪上下文捕获、字段/参数快照、静态拒绝未知重载/资源/分支。加入错误UV、错误导数、错误采样模式/LOD、错误裁剪条件的证明负控制，UNPROVED只代表未证出；另用具体模型/Unity反例表明确有差异。

Unity 新独立资产目录和 template，直接 include 被证明 HLSL 的精确字节。受控可持久化纹理（含mip）、UV有变化的平面/球面；读回RGBAFloat并检查正例输出与裁剪mask。独立CPU公式/受控导数输入检查采样/导数/裁剪；遮罩保留/丢弃均须非空，零阈值边界另测，负例必须观察到真实颜色或mask差异。实际HDRP场景保存/重载两版可见材质，沿用独立scene culling mask和关闭自有几何的污染控制。保留现有打开场景。

统一 tools/run_demo.ps1 默认执行全部旧/新 formal + GPU 例子，输出机器证据、预览和源文件哈希；独立Q在已有初验后检查实现/证据，修复后再完整验收。README只描述已验证能力与必要限制；planning保存决策与真实命令，不把计划当成完成。

## 依赖与停止条件

无新增外部依赖、全局环境改动、push或HDRP/Lit源码提取。工具继续固定本地DXC/Lean4.24/mathlib。实现顺序：语义与导入→例子及Lean/负控制→Unity完整验证→独立Q和统一验收。若发现现有实数/共享操作模型无法表达目标，或实际GPU oracle不可用且无等效证据，停止相应步骤并报告具体障碍；不能以stub、skip或纯编译声称通过。

实现不变量补充：events 交错记录 SSA 绑定与效果；opaque.context 只记录已有效果前缀长度，发射器严格按 events 次序定义，禁止前向引用。全部裁剪条件也参加normalize域检查。独立P第一轮确认设计可执行，正式详细意见记录在implementation-evidence。
