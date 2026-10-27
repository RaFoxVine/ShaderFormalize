# 实验性 Compute 验证

此入口将两份实际 HLSL Compute Shader 经固定 DXC 的 typed AST 转成 Lean，比较其完整最终资源，并把地址合法性和跨线程冲突检查放进同一个待证目标。它复用核心本地 DXC/Lean/mathlib，不依赖 Unity。数值仍采用实数，索引采用精确 uint32；IEEE 接入是独立原型。

```powershell
python tools/computeformalize.py prepare
python tools/computeformalize.py check
python tools/run_compute_suite.py

# 显式物理别名、同线程连续写入和写后读取
python tools/computeformalize.py check --original examples/compute/alias-original.hlsl --optimized examples/compute/alias-optimized.hlsl --constraints examples/compute/alias-constraints.json --agent-proof proof/ComputeAliasProof.lean --output artifacts/compute/alias

# 二维纹理后处理（schema 2）
python tools/computeformalize.py check --original examples/compute-texture/original.hlsl --optimized examples/compute-texture/optimized.hlsl --constraints examples/compute-texture/constraints.json --agent-proof proof/ComputeTexturePostProof.lean --output artifacts/compute-texture/post
```

prepare 生成实际两份定义与完整命题；check 绑定提供的 agent proof，并使用与核心相同的 Lean 公理白名单。默认例子从两个 StructuredBuffer 读取，向两个 RWStructuredBuffer 写平均颜色和差值；改写版交换输出顺序并分配乘法。输出位置之外的初始内存同样参与比较。

## 当前支持范围

两种契约都由 constraints.json 的 `schema` 选择；缺省仍为旧版 schema 1。两份源码的字段名、入口参数名、线程组大小、资源声明与寄存器必须匹配。

### schema 1：一维 StructuredBuffer

- 固定 DXC `-T cs_6_0 -E main -HV 2021`，一个 `void main(uint3 : SV_DispatchThreadID)`，`numthreads(x,1,1)` 和一维 dispatch。总线程数不超过 2³²；`y/z` 为零。
- 一个 `register(b0)` cbuffer，包含一个 uint 字段；契约中的 count_range 约束该字段。
- 显式寄存器的 `StructuredBuffer<float4>` 与 `RWStructuredBuffer<float4>`。支持前者 `.Load(uintIndex)`/`[uintIndex]` 读取、后者 `[uintIndex] = float4` 写入。DXC 为 Load(int) 插入的 uint→int 变换在合法非负下标域内处理；物理容量上限为 2³¹ 个 float4。
- float 标量/向量基本加减乘、负号、构造、swizzle、标量广播；uint32 加减乘与按位与或异或；uint 与 float 标量比较、bool 逻辑；局部变量、整值赋值、嵌套块、if/else、提前 return。每个 Load/Store 的地址、值和执行条件都捕获当时状态。schema 1 不支持 helper。

### schema 2：二维 Texture2D 后处理

- `numthreads(x,y,1)`、三维 dispatch 的 z 为 1，每轴 dispatch ID 不溢出 uint32。线程以 x 优先的可逆行主序编码，证明不按某个线程遍历顺序安排执行。
- cbuffer 的每个字段必须是标量 uint 或 float，并在 `uniform_ranges` 中分别给出精确范围。uint 范围为 0..2³²-1，float 界使用精确整数或十进制字符串。
- 支持 `Texture2D<float4>`、`RWTexture2D<float4>` 以及同一 schema 中的 StructuredBuffer 资源。纹理仅接受 mip0 的 `.Load(int3(x,y,0))` 和 `[uint2(x,y)] = float4`；绑定用 `identity + dimensions` 表示二维形状。相同 identity 必须具有相同物理类别、形状和 float4 布局。
- 整数标量及二三分量构造、swizzle、uint/int 位模式转换、加减和标量比较保持精确 32 位语义。float 数学白名单为 `min/max/saturate/dot` 与基本算术；按值纯 helper 支持 float1..4 参数和结果、局部计算、if/else、终结 return 与嵌套调用。递归、资源访问、out/inout 和全局写会被拒绝。
- 每次实际除法都在当时 SSA 执行 guard 下留下分母非零义务，包括未使用结果和 helper 实参；未执行分支与短路未选侧不留下执行义务。

两种 schema 都不支持一般循环、矩阵、跨线程中途通信、groupshared/barrier/atomics；schema 2 也不支持非零 mip、纹理格式转换或过滤。相同物理资源通过只读与可写视图别名时，同线程写后读可用。

## 资源身份和安全目标

constraints.json 显式给出 dispatch、typed uniform 范围以及每个资源的物理 identity 和容量或二维尺寸。同一 identity 表示同一份起始位置相同、float4 布局相同的内存；其物理类别和形状必须一致。本原型没有不同 view base offset/stride/mip/format 的隐含换算，也不会根据变量名猜测资源是否别名。

内存为 `物理 identity → 元素地址 → float4`。每个线程从同一个初始内存开始，按源码访问顺序维护自己的 memory overlay。Store 立即捕获值并在其执行 guard 下更新 overlay；Load 读取该时刻 overlay。因此即使只读视图和可写视图名字不同，也能读到本线程此前最后一个同址写入。二维纹理地址按 `y * width + x` 编码；Load 按有符号 int 坐标、Store 按 uint 坐标分别检查两个轴的界内条件。

完整目标要求双方每个派发线程都满足数学定义域与每次 Store 的独立二维边界义务，并证明任意两个不同线程之间没有写/写或写/读的同址冲突。越界纹理 Load 返回全零且不产生物理读事件；它不会被误当成越界 Store。非法 Store 即使被总内存函数掩盖，也仍使 `storeBounds` 不成立。相同线程有序写回不被当作跨线程竞争。该目标成立时，一个地址至多由一个线程写入；最终内存取该线程全部有序 Store 后的值，未写地址保留初始值。多个竞争线程存在时，Lean 中的总函数仍有定义，但安全目标不成立，不能得到完整 PROVED。

`UNPROVED` 表示当前证明未通过，不表示工具已经形式证明不等价。有限求值器可以给出越界、冲突和错误结果的具体见证，但这些测试不代替 Lean 的全称证明。DXC、typed-AST 映射和本执行模型仍属于可信边界，本原型没有证明任意 GPU 内存模型或整个 Direct3D 执行系统。

默认结果写入 artifacts/compute/proof/result.json。检查器逐个直接编译项目模块，只读取已安装的 mathlib 编译产物，不触发共享依赖目录中的补编；依赖缓存缺失应先由本地 bootstrap/根工作流补齐。

旧控制清单 examples/compute/controls.json 包含两正例与错误计算、越界、跨线程写写冲突、别名写读冲突四负例。examples/compute-texture/controls.json 增加后处理、同线程纹理 alias/最后 Store、OOB Load 三个正例，以及错误输出、越界 Store、跨线程写写、alias 邻像素写读、未守卫零分母五个负例。所有源码、约束和 agent proof 都在仓库内。run_compute_suite.py 同时运行独立有限回归，并要求这些实际完整 Lean 检查分别返回 PROVED 或 UNPROVED；负例必须失败于 SubmittedProof 的 Lean 编译，不能用 DXC 导入或环境错误代替。
