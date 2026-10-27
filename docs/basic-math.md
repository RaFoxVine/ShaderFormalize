# 基础数学运算

本批把常见的数学写法接入现有实数模型。float 仍表示实数，不包含 IEEE 舍入、NaN 或无穷；浮点库原型另见 prototypes/ieee。

支持 float 标量及 float1..float4（包括 DXC 的标量广播）：

| 源码操作 | 实数解释及实际执行时需要证明的条件 |
|---|---|
| min、max、abs | 按分量取最小、最大、绝对值 |
| clamp(x,lo,hi) | min(max(x,lo),hi)；本子集要求逐分量lo≤hi |
| a / b、rcp(b) | 普通实数除法；逐分量b≠0 |
| sqrt(x) | 实数平方根；逐分量x≥0 |
| rsqrt(x) | 1/sqrt(x)；逐分量x>0 |
| length(v) | sqrt(dot(v,v))；零向量合法 |
| distance(a,b) | length(a-b)；相同输入合法 |
| floor、ceil | 整数向下/向上取整后转回实数 |
| frac(x) | x-floor(x)，负数也按此定义 |
| step(edge,x) | x<edge 时为0，否则为1；相等时为1 |
| smoothstep(lo,hi,x) | 饱和三次多项式；实际执行时逐分量lo<hi |
| cross(a,b) | 标准三维叉积，仅接受float3×float3 |
| reflect(i,n) | i-2*n*dot(i,n)，同宽float1..4；不假设单位法线 |

首次支持不包含这些函数的 int、矩阵重载或 `/=`。未知重载继续明确拒绝。显式 shared 支持原有结构体和共享 helper 等正常写法；默认 auto 中的新数学运算进入带执行条件的模型，未使用新运算的旧目标保持兼容。

这些条件是完整待证目标的一部分，不会被偷偷加成用户输入假设。例子：

```hlsl
if (x > 0.0)
    return sqrt(x) + rcp(x);
return 0.0;
```

只需要在实际进入分支时证明条件。若把计算移到 if 前，即使最后没有使用该结果，工具仍要求证明那个实际计算的域。条件在求值时保存，之后赋值覆盖不删除义务。

这是实数抽象的适用范围。HLSL 浮点的除零、负数平方根可产生 INF/NaN，并非因此成为非法源码；这些特殊值留给浮点语义模式表达。

从仓库根目录运行：

```powershell
pwsh -File tools/run_demo.ps1 -Example basic-math
pwsh -File tools/run_demo.ps1 -Example math-extensions

python tools/shaderformalize.py check --frontend shared --original examples/basic-math/original.hlsl --optimized examples/basic-math/optimized.hlsl --constraints examples/basic-math/constraints.json --agent-proof proof/BasicMathProof.lean --output artifacts/basic-math/proof
```

正常材质包含结构体、限幅 helper、长度/距离、平方根、倒数及衰减计算。改写版展开这些操作；完整目标同时要求实际执行域成立、输出相等。验收另有带保护分支的改写、auto 路径、错误颜色、把受限计算移出分支，以及未使用但反序的 clamp 负例。`math-extensions` 再加入代数展开、floor/ceil/frac量化、smoothstep三个正例，以及错误step边界、零界和反序三个负例。`UNPROVED` 表示当前证明未通过，不代表已经构造形式反证。

实现中的 tools/shader_math.py 统一记录操作形状、域规则和发射/有限求值接口；DXC 继续负责语法、类型和重载解析。新运算复用既有 Lean 模块，无需升级当前 Lean4.24 或核心依赖。
