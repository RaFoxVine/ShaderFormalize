# 实验性 Compute 验证

此入口将两份实际 HLSL Compute Shader 经固定 DXC 的 typed AST 转成 Lean，比较其完整最终资源，并把地址合法性和跨线程冲突检查放进同一个待证目标。它复用核心本地 DXC/Lean/mathlib，不依赖 Unity。数值仍采用实数，索引采用精确 uint32；IEEE 接入是独立原型。

```powershell
python tools/computeformalize.py prepare
python tools/computeformalize.py check
python tools/run_compute_suite.py

# 显式物理别名、同线程连续写入和写后读取
python tools/computeformalize.py check --original examples/compute/alias-original.hlsl --optimized examples/compute/alias-optimized.hlsl --constraints examples/compute/alias-constraints.json --agent-proof proof/ComputeAliasProof.lean --output artifacts/compute/alias
```

prepare 生成实际两份定义与完整命题；check 绑定提供的 agent proof，并使用与核心相同的 Lean 公理白名单。默认例子从两个 StructuredBuffer 读取，向两个 RWStructuredBuffer 写平均颜色和差值；改写版交换输出顺序并分配乘法。输出位置之外的初始内存同样参与比较。

## 当前支持范围

- 固定 DXC `-T cs_6_0 -E main -HV 2021`，一个 `void main(uint3 : SV_DispatchThreadID)`，`numthreads(x,1,1)` 和一维 dispatch。总线程数不超过 2³²；`y/z` 为零。
- 一个 `register(b0)` cbuffer，包含一个 uint 字段；契约中的 count_range 约束该字段。每份源码的字段名、入口参数名、线程组大小、资源声明与寄存器必须匹配。
- 显式寄存器的 `StructuredBuffer<float4>` 与 `RWStructuredBuffer<float4>`。支持前者 `.Load(uintIndex)`/`[uintIndex]` 读取、后者 `[uintIndex] = float4` 写入。DXC 为 Load(int) 插入的 uint→int 变换在合法非负下标域内处理；物理容量上限为 2³¹ 个 float4。
- float 标量/向量基本加减乘、负号、构造、swizzle、标量广播；uint32 加减乘与按位与或异或；uint 与 float 标量比较、bool逻辑；局部变量、整值赋值、嵌套块、if/else、提前 return。每个 Load/Store 的地址、值和执行条件都捕获当时状态。
- 暂不支持 helper、循环、矩阵、纹理格式转换、RWBuffer 直接读取、跨线程中途通信、groupshared/barrier/atomics。相同物理资源通过只读与可写视图别名时，同线程写后读可用。

## 资源身份和安全目标

constraints.json 显式给出 dispatch group 数、uint 字段范围、每个资源的物理 identity 和容量。同一 identity 表示同一份起始位置相同、float4 布局相同的内存；其容量必须一致。本原型没有不同 view base offset/stride 的隐含换算，也不会根据变量名猜测资源是否别名。

内存为 `物理 identity → 元素地址 → float4`。每个线程从同一个初始内存开始，按源码访问顺序维护自己的 memory overlay。Store 立即捕获值并在其执行 guard 下更新 overlay；Load 读取该时刻 overlay。因此即使只读视图和可写视图名字不同，也能读到本线程此前最后一个同址写入。

完整目标要求双方所有执行的访问在各自资源容量内，并证明任意两个不同线程之间没有写/写或写/读的同址冲突。相同线程有序写回不被当作跨线程竞争。该目标成立时，一个地址至多由一个线程写入；最终内存取该线程全部有序 Store 后的值，未写地址保留初始值。多个竞争线程存在时，Lean 中的总函数仍有定义，但安全目标不成立，不能得到完整 PROVED。

`UNPROVED` 表示当前证明未通过，不表示工具已经形式证明不等价。有限求值器可以给出越界、冲突和错误结果的具体见证，但这些测试不代替 Lean 的全称证明。DXC、typed-AST 映射和本执行模型仍属于可信边界，本原型没有证明任意 GPU 内存模型或整个 Direct3D 执行系统。

默认结果写入 artifacts/compute/proof/result.json。检查器逐个直接编译项目模块，只读取已安装的 mathlib 编译产物，不触发共享依赖目录中的补编；依赖缓存缺失应先由本地 bootstrap/根工作流补齐。

正式控制清单在 examples/compute/controls.json，包含两正例与错误计算、越界、跨线程写写冲突、别名写读冲突四负例；所有源码、约束和 agent proof 都在仓库内。run_compute_suite.py 同时运行独立有限回归，并要求这些实际完整 Lean 检查分别返回 PROVED 或 UNPROVED。
