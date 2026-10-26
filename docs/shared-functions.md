# 共享函数定义后端

正常HLSL可以多次调用相同的辅助函数。`--frontend shared`让生成的Lean也只保留一份函数体；它仍是从DXC已确定类型和调用目标的AST转换出的实际计算，证明时可以展开。

```powershell
python tools/shaderformalize.py check --frontend shared --original examples/structured/original.hlsl --optimized examples/structured/optimized.hlsl --constraints examples/structured/constraints.json --agent-proof proof/SharedStructuredProof.lean --output artifacts/shared/current
```

当前支持按值float/向量、bool、uint、嵌套struct、float矩阵和定长数组、尾部默认参数及out/inout，及原有if、三元式、局部return、采样、导数、clip/discard。循环尚未接入。位载体可在函数内部原样保存/恢复，但当前禁止跨函数边界。默认`auto`沿用已有后端和证明；新参数语法及复合值只由shared接受。shared使用模型schema6，两种后端不能混配。[矩阵/数组具体契约](aggregate-values.md)。

裁剪只允许在入口和void辅助函数内；数值/struct返回函数可以调用纯计算void函数，但不能直接或间接裁剪。含out/inout的函数暂不允许到达终止式discard；void内clip并在正常返回前写全输出可以组合。HLSL不指定参数初始化及重叠输出的恢复顺序，因此工具会检查表达式的数据依赖。[规范草案§5.6](https://microsoft.github.io/hlsl-specs/specs/5-Expr.html#function-calls)

`out`从未初始化副本开始，所有正常出口必须写全；`inout`先复制调用前的值。返回后才将输出副本写到调用者的整变量、字段或元素地址，不能让函数体直接修改调用者字典。两个输出地址重叠或动态无法判定会拒绝；支持不重复分量的向量swizzle地址，下标形成时捕获一次。`F(out x, x)`可以读取调用前的输入副本；`F(inout x, G(out x))`或`G(out x)+x`依赖未规定的实参/操作数顺序，返回UNSUPPORTED。三元式和标量短路运算按选中的分支合并调用者变量状态。

默认参数使用DXC绑定的声明表达式，在省略实参且调用实际执行时检查其域；显式传参不会增加未用默认的域要求。默认表达式中的全局名字按声明环境查找，不能被调用者的同名局部变量替代。所有未调用函数与默认表达式仍做语法及初始化检查。

每个辅助函数接收完整参数字段与实际调用位置，返回完整数值字段、裁剪保留条件和有效性命题。数值不按调用位置清零，因此后续导数仍收到相同的完整输入函数。入口条件只控制实际执行的域义务、采样/导数上下文和裁剪。调用者必须证明被执行的所有计算合法，双方定义域仍在最终结论中；未调用函数的定义域不变成主程序的义务。实参即使被函数忽略，也会先计算并检查其定义域。

共享定义使用现有四个数学模块，无新增公理。函数图必须非递归，最多127个辅助函数；每个函数最多4096个数值绑定/调用点，辅助函数合计最多65536绑定，调用深度最多31层。未知语法及未初始化读取仍拒绝，包括未调用函数体。

正式对照由默认`tools/run_demo.ps1`执行；有限求值仅用作回归检查，不能取代Lean证明。核心不需要Unity。

包含默认参数、out结构体和inout颜色累积的材质位于`examples/copyback`，手写证明为`proof/CopybackStructuredProof.lean`。只跑这一组可用`pwsh -File tools/run_demo.ps1 -Example copyback`；该组还有完整场导数、clip写回和默认参数实际域的正式对照，没有Unity runner。
