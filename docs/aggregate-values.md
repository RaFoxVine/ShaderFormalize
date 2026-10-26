# 矩阵、定长数组和元素写回

显式`--frontend shared`接受普通HLSL矩阵和定长数组，继续由DXC确定类型、声明和重载，再转换成现有实数/uint数学运算。示例`examples/aggregate/original.hlsl`使用LightData数组、out数组、默认参数、inout光照累积和颜色混合矩阵；`optimized.hlsl`手工展开同一计算。首个完整材质目标已PROVED，当前完整验收结果以统一runner的实际报告为准。

```powershell
pwsh -NoProfile -File tools/run_demo.ps1 -Example aggregate
python tools/shaderformalize.py check --frontend shared --original examples/aggregate/original.hlsl --optimized examples/aggregate/optimized.hlsl --constraints examples/aggregate/constraints.json --agent-proof proof/AggregateMaterialProof.lean --output artifacts/aggregate/current
```

支持float矩阵1至4行/列，固定数组每层1至64元素、最多16层/4096数值叶。数组元素可以是已支持的float/vector、bool、uint、struct、矩阵或另一数组；它们可作为局部、struct字段、helper按值参数/结果及out/inout参数。没有动态分配或外部写入。入口仍是返回float4的像素main；矩阵/数组stage输入、资源数组、bool/uint uniform尚未开放。

矩阵按逻辑行列解释，支持完整构造、标量全元素填充、左上子矩阵截断、转置、逐分量加减乘/负号和mul。普通`a*b`对矩阵逐分量相乘，`mul(a,b)`按DXC重载作标量缩放、点积或线性代数乘法，行列维度必须匹配；float1向量参与单行/单列乘法也与标量缩放区分。数学运算不考虑浮点舍入。[mul定义](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-mul)、[转换规则](https://microsoft.github.io/hlsl-specs/specs/4-Conv.html)。

数组和矩阵支持整值复制、字段、下标和局部元素写回；向量支持不重复分量的swizzle左值，包括out。下标为uint或DXC整数字面量，按形成地址时的值捕获一次，函数返回写回时不会重新计算。两个输出必须能静态证明不重叠；不同常量元素和不同分量可以并用，无法确认的动态重叠会拒绝。调用实参、普通二元、构造和采样参数中的未定序读写冲突也拒绝，包含索引本身的副作用。

实际执行的每个下标必须满足`index.toNat < length`。这个条件是Lean最终结论的一部分，不是工具添加的输入前提，也不会取模掩盖越界。未执行分支的越界不产生实际域义务；实际越界的同源程序也不能通过定义域证明。有限求值器只为回归提供具体结果和反例，不能替代形式证明。

未初始化值逐字段/分量追踪。可以逐项填充数组、逐分量写完向量；只读取一个已写字段不要求无关字段已写。整值复制/传参/返回必须全部初始化。动态读要求所有可能选中的目标字段初始化；动态写要求所有可能保留的目标已有值。数组需要完整初始化树，不能把DXC拒绝的部分初始化自行补零；支持DXC明确给出的`(S)0`一类零转换。float位载体不能作为普通实数分量混入向量，也不能跨helper接口。

复合float uniform展开为确定的数学输入叶，如`_ColorMix[0]`是一行、`_Lights[1].color`是字段。仍只支持单个register(b0)，至多64输入叶；数组/struct中的uint或bool uniform拒绝。两份源码的完整源字段顺序、类型形状、矩阵row_major/column_major packing及展开映射必须相同。逻辑矩阵运算不依赖物理packing，但输入对应关系依赖它，不能忽略。

ranges可以选择整个矩阵/数组/struct、子组或精确输入叶。组范围展开至全部叶，与更具体范围取交集；空交集返回INVALID_INPUT，防止以矛盾前提取得空洞证明。nonzero_vectors仍只能选择真实float向量叶或其合法swizzle，整个矩阵/数组不是向量。

仍使用schema6，矩阵和数组降低为现有有序record叶；aggregate_types保存规范的类型图，uniform_layout/input_groups保存源布局和范围映射。校验器检查类型身份、引用/环、深度/叶预算、输入映射和bounded_index数据，发射与有限求值共用这些检查。元数据摘要进入GeneratedModel字节哈希，Fragment.Ops接口和公理白名单不变。旧无aggregate模型不增加这些字段或注释，旧目标保持。

默认auto继续沿用此前子集。循环、一般signed int、矩阵具名分量选择器、任意struct花括号初始化、原始除法和其它尚未列入的HLSL功能仍会明确拒绝；struct可逐字段构建或用受支持的零转换。新示例没有Unity runner。转换器及DXC仍属于可信边界，转换器自身尚未形式证明。
