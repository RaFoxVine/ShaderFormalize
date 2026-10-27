# HLSL 同步访问安全检查

此入口把固定两线程的 Compute HLSL 经 DXC typed AST 转成 VerCors 的 PVL 权限模型，检查共享数组访问界限、跨线程读写权限和一个真实 barrier 的权限交接。结果来自外部验证器，不是 Lean 证明，也不比较数值或最终内存。

```powershell
python tools/syncformalize.py prepare
python tools/syncformalize.py check
python tools/run_sync_suite.py
```

默认输入是 `examples/synchronization-hlsl/original.hlsl`：两个线程分别写自己的 `groupshared` 槽位，执行 `GroupMemoryBarrierWithGroupSync`，再读取邻居槽位并写输出。`prepare` 保存源码、typed AST、事件模型和生成的 PVL；`check` 另外运行固定 VerCors 2.4 并保存完整日志与哈希。

## 当前支持范围

- 一个 dispatch group，`numthreads(2,1,1)`，入口参数为 `uint3 : SV_GroupThreadID`，只使用 `.x`。
- 一个 `groupshared float4[2]`、一个 `StructuredBuffer<float4>` 输入和一个 `RWStructuredBuffer<float4>` 输出，均有显式寄存器。
- 初始化的 `uint` 局部变量、整数常量及 `uint` 加减；每次加减在 PVL 中显式取模 2³²，地址不被直接当作数学整数。
- 整 `float4` 的 Buffer/共享数组读写，以及零或一个无条件 `GroupMemoryBarrierWithGroupSync`。
- 拒绝控制流、提前 return、helper、影响地址的 float 计算、其他 barrier、atomic 和 Wave 操作。

`constraints.json` 显式绑定两个 Buffer 的物理 identity 和容量；容量必须为 2，输入输出 identity 必须不同。相同 identity 返回 `UNSUPPORTED`，不会偷偷加入无别名前提。

转换器按 AST 顺序记录每次 Load、Store 和 barrier。PVL 的初始权限只来自资源契约；barrier 前后的权限变化来自实际 barrier 注解，不按期望交换模式补权限，也不 `assume` 地址合法或无竞争。

## 结果与边界

- `PREPARED`：已生成 PVL，尚未运行外部验证器。
- `EXTERNAL_SAFETY_VERIFIED`：VerCors 对本次生成的访问安全模型验证通过。
- `EXTERNAL_SAFETY_UNPROVED`：VerCors 拒绝了权限或访问安全目标；查看 `vercors.log`。
- `UNSUPPORTED / INVALID_INPUT`：超出固定子集或输入契约错误。
- `ENVIRONMENT_ERROR / INCONCLUSIVE`：工具、Java、超时或工作区锁问题，不是安全结论。

`tools/run_sync_suite.py` 运行导入单元回归及五项实际控制：正确例验证通过，删 barrier 和共享同址写入都到达真实权限错误，越界访问到达 `arrayBounds` 拒绝，别名契约被拒绝。报告位于 `artifacts/synchronization-hlsl/acceptance/result.json`。

此模型不声明共享值已初始化、数值等价、任意 GPU 调度或完整 Direct3D 内存模型正确。DXC、HLSL→PVL 转换器和 VerCors 都在可信边界内；没有新增 Lean 公理，也没有把外部报告转换成 Lean 定理。
