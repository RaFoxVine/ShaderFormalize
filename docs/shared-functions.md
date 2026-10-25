# 共享函数定义后端

正常HLSL可以多次调用相同的辅助函数。`--frontend shared`让生成的Lean也只保留一份函数体；它仍是从DXC已确定类型和调用目标的AST转换出的实际计算，证明时可以展开。

```powershell
python tools/shaderformalize.py check --frontend shared --original examples/structured/original.hlsl --optimized examples/structured/optimized.hlsl --constraints examples/structured/constraints.json --agent-proof proof/SharedStructuredProof.lean --output artifacts/shared/current
```

当前支持按值float/向量、bool、uint和嵌套struct参数/返回值，及原有if、三元式、局部return、采样、导数、clip/discard。默认参数、out/inout、矩阵/数组和循环尚未接入。位载体可在函数内部原样保存/恢复，但当前禁止跨函数边界。默认`auto`沿用已有后端和证明；shared使用模型schema6，两种后端不能混配。

裁剪只允许在入口和void辅助函数内；数值/struct返回函数不能裁剪或调用void函数。因此当前参数及算术兄弟表达式不会改变彼此的输入或执行条件。HLSL不指定参数初始化顺序，不能在后续开放out/inout等表达式写入时直接沿用这个前提；届时必须检查跨表达式的数据依赖。[规范草案§5.6](https://microsoft.github.io/hlsl-specs/specs/5-Expr.html#function-calls)

每个辅助函数接收完整参数字段与实际调用位置，返回完整数值字段、裁剪保留条件和有效性命题。数值不按调用位置清零，因此后续导数仍收到相同的完整输入函数。入口条件只控制实际执行的域义务、采样/导数上下文和裁剪。调用者必须证明被执行的所有计算合法，双方定义域仍在最终结论中；未调用函数的定义域不变成主程序的义务。实参即使被函数忽略，也会先计算并检查其定义域。

共享定义使用现有四个数学模块，无新增公理。函数图必须非递归，最多127个辅助函数；每个函数最多4096个数值绑定/调用点，辅助函数合计最多65536绑定，调用深度最多31层。未知语法及未初始化读取仍拒绝，包括未调用函数体。

正式对照由默认`tools/run_demo.ps1`执行；有限求值仅用作回归检查，不能取代Lean证明。核心不需要Unity。
