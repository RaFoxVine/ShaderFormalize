# 整数打包与实数计算

这里面向使用者和证明agent：验证包含整数位字段的两份HLSL，同时保持普通float的实数模型。核心不依赖Unity。完整HDRP/Lit Forward仍未被数学前端支持，此功能只是其所需基础之一。

## 直接运行

```powershell
pwsh -File tools/run_demo.ps1 -Example packed
python tools/shaderformalize.py check --original examples/packed/original.hlsl --optimized examples/packed/optimized.hlsl --constraints examples/packed/constraints.json --agent-proof proof/PackedProof.lean --output artifacts/packed/proof
```

原版使用结构体和辅助函数：将两个颜色通道经saturate限制到0..1，乘255后转uint，分别放进低8位和接下来的8位，通过float载体复制后再拆出来。改写版直接使用两个量化结果，省去打包往返。输出用精确的1/256缩放便于比较字节结果，不声称是标准UNorm解码。Lean目标覆盖所有实数输入，不需调用者提供颜色范围，因为程序自己执行saturate。

错误版将第二字段左移7位，造成重叠。有限求值器提供具体反例，且原证明不能通过错误目标。`domain-safe.hlsl`和两个错误定义域例子另检查短路与未使用实参；它们采用a各分量恒为0的显式输入约束。

## 三种值的含义

| HLSL用法 | 数学解释 | 允许的后续操作 |
|---|---|---|
| 普通float | 实数 | 现有计算、比较、采样、导数 |
| uint | 32位BitVec，无符号视图 | 加减乘模2³²、位运算、比较、数值转float |
| asfloat(uint) | 保存32位内容的float槽 | 局部复制、struct字段、同类别分支选择、asuint恢复 |

`(float)u`把整数数值转为实数；`asfloat(u)`保存其位内容。这两个操作含义不同。载体在Lean里仍是BitVec，不解释成某个实数，不使用任意的Real→bits函数替代真实浮点编码。[微软asfloat定义](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-asfloat)、[asuint定义](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-asuint)。

普通实数的asuint、载体加乘/比较/clip/导数/采样/颜色输出、数字和载体混合选择，明确UNSUPPORTED。载体目前不能跨辅助函数参数或返回，嵌套struct也一样；辅助函数内部完成uint→载体→uint往返可以接受。外部float位载体输入尚未开放，不能擅自把普通uniform解释成位数据。符号位操作、任意IEEE位技巧及IsNaN编码检查也尚未支持。

## 定义域和证明

float→uint对非负实数向零截断，必须证明0≤x<2³²。uint→float为toNat再嵌入实数，不引入浮点舍入。移位接受uint计数，必须证明计数<32；模型在该域外仅作有界总化，不宣称支持超宽计数的HLSL行为。定义域要求作为最终命题的结论，使用实际执行guard。即使两份程序同样越界、返回值相等，也不能PROVED。

转换和移位在求值时立即建立不可变快照，避免外层选择错误地把未选分支当作执行。helper的每个实参都执行，即使被忽略或覆盖；未调用函数仍检查受支持语法、初始化和载体误用，但不添加其未执行的数学域义务。

工具生成schema5模型，复用现有执行掩码和裁剪模型。`proof/ShaderFormalize/Packing.lean`提供BitVec语义和对任意32位值成立的两字段拆包定理；逐位证明由Lean内核检查。证明检查仍仅接受propext、Classical.choice、Quot.sound，不放行bv_decide默认引入的Lean.ofReduceBool。

## 当前范围和后续接口

支持标量uint局部、内部struct字段、按值helper参数/返回；十进制/十六进制uint字面量及u后缀；+、-、*、&、|、^、~、<<、>>、无符号比较和现有控制流。uint复合赋值尚未开放。入口及cbuffer输入仍只接受现有实数布局；int、有符号位操作、整数向量/数组/矩阵和out/inout仍会拒绝，均非永久排除项。

外部输入的位载体语义和按调用区分的helper接口，需要在下一阶段明确。完整Forward还需要共享函数表示、out/inout、矩阵/数组、只读资源、循环和更多数学操作；不能把本示例的PROVED当作官方Lit的证明。
