# ShaderFormalize

将两份 HLSL 经 DXC 已定类型的语法树转成理想实数模型，提供 agent 编写、迭代并独立检查 Lean 等价证明的本地环境。核心依赖固定版本 DXC、Lean 和 mathlib，安装、转换、证明和默认验收均不依赖 Unity。它不是任意 Shader 的自动等价判定器。

最新 [原版分支材质](examples/branched/original.hlsl) 使用结构体、bool helper、提前返回、纹理开关、三种着色模式、嵌套条件裁剪和 ddx/ddy；[等价改写版](examples/branched/optimized.hlsl) 调整条件组织、使用三元选择并展开颜色计算。两边直接接受正常源码，不要求先拍平。原有 lerp、Unlit、structured、textured 示例和证明保留。

使用者从 [agent 证明工作流](docs/agent-workflow.md) 开始：生成完整命题，编写证明，运行检查器，根据诊断继续尝试。前一阶段的 [纹理材质机器证据](planning/evidence/textured-material-2026-10-25.json) 与 [历史执行记录](planning/fragment-effects/implementation-evidence.md) 保留供追溯。

2026-10-25完整默认核心验收通过：在PATH无法发现unity、未提供Unity工程的环境中，102项回归和27项证明正负控制均符合预期，10个完整目标PROVED。显式可选Unity五例均PASSED；新分支材质120组/245760像素与独立CPU公式的最大误差约2.38×10⁻⁸，裁剪mask一致，错误开关/阈值均有GPU反例。[机器证据](planning/evidence/control-flow-2026-10-25.json)，[本轮执行记录](planning/control-flow/implementation-evidence.md)。

![原始与等价改写分支材质的实际HDRP相机输出](planning/evidence/branched-preview-2026-10-25.png)

## 本机运行

Windows x64、PowerShell 7、Python 3.9+标准库、Git、curl。本地 Lean4.24/DXC 及锁定 mathlib 安装到仓库内，不依赖 VS Code 的 elan 配置；固定下载地址、版本与哈希在依赖锁中。

```powershell
# 首次安装固定本地工具及当前所需编译缓存。
pwsh -File tools/bootstrap.ps1

# 默认完整核心验收：全部回归和证明正负控制，无需 Unity。
pwsh -File tools/run_demo.ps1

# 开发迭代时只检查分支示例及控制流回归。
pwsh -File tools/run_demo.ps1 -Example branched

# 仅检查纹理材质数学等价。
python tools/shaderformalize.py check --original examples/textured/original.hlsl --optimized examples/textured/optimized.hlsl --constraints examples/textured/constraints.json --agent-proof proof/TexturedProof.lean --output artifacts/textured/proof

# 显式启用可选 Unity 开发验证：五套 GPU/已保存 HDRP 场景，不重复核心验收。
pwsh -File tools/run_unity_suite.ps1 -UnityProject '你的 Unity 工程绝对路径'
```

可选GPU检查需要已打开且unity CLI可连接的Editor；本机开发环境为Unity6000.5.9f1、HDRP17.5.0、Direct3D12。打开 `Assets/ShaderFormalizeBranched/BranchedComparison.unity` 查看分支材质；纹理例场景为 `Assets/ShaderFormalizeTextured/TexturedComparison.unity`。材质与受控纹理均持久化，可在Inspector调整参数。预览与报告位于 artifacts/<example>/unity/。脚本复制被证明HLSL的精确字节并校验哈希；数学报告位于指定 --output，完整核心摘要在 artifacts/acceptance/result.json。原 `run_demo.ps1 -UnityProject ...` 命令仍可在核心成功后追加可选GPU验证。

仍保留 --example lerp / unlit / structured：对应基础lerp、手写方向光/环境项/平方边缘光、正常结构化同效果。旧例及其证明继续参与完整验收；旧记录见[结构化材质证据](planning/evidence/structured-material-2026-10-25.json)。

Unity运行器保存并重新载入演示场景，再用其中实际Camera的HDRP StandardRequest回读，并在相同几何/相机上切换材质比较。相机只在自身关闭雾/曝光控制/后处理，未改项目全局设置。若目标场景已打开，另存 *.Validation.unity（必要时唯一化），保留用户场景。回读时分配本次场景独立剔除掩码，隐藏自有两球后必须只剩背景。验证临时状态在finally恢复，不保存到用户场景。

纹理例的数值pass使用64×32规则UV平面和16×16受控点采样纹理。UVCalibration校验包装层插值坐标，CPU独立计算texel、mip、梯度footprint、颜色和保留条件；每次绘制前清成负alpha背景，单独比较裁剪mask，包含clip零边界。测试并非只比较两份GPU结果。预览是实际保存场景的HDRP相机输出。

Unity包装目前仅指定shader target，未固定HLSL2021语言模式。GPU证据覆盖有限颜色和裁剪结果；当前材质不依赖未选分支中的非法运算。HLSL2021短路语义由固定 `-HV 2021` 的DXC和核心回归覆盖，未由Unity GPU测试验证。

## 证明保证

float解释为实数，向量为实数分量。普通数值程序保留schema2；旧纹理/简单裁剪用schema3；一般控制流用schema4。片元模型中varying为任意位置集合 E 上的完整函数，uniform为常量；输出为 E→Option Vec4，None表示丢弃，Some表示颜色。证明比较完整输出函数，包含裁剪结果；schema4目标另外要求所有实际执行的normalize有合法定义域。

纹理/导数由定理全称量化的共享 `Fragment.Ops E` 提供。这是双方使用的同一组任意操作参数，不是新增公理：

- 采样保留纹理、Sampler、三种模式，以及完整UV、LOD或显式梯度函数；不假定过滤公式。
- 导数保留ddx/ddy及fine/coarse模式，作用于完整输入函数，向量逐分量；没有链式/乘积等微积分规则。
- schema3操作接收之前裁剪条件的有序序列；schema4统一接收一个完整执行条件函数，包含分支、此前裁剪和函数return。混合配对时旧前缀按合取提升为同一表示。输入函数与执行上下文相同，则同一共享操作结果相同。不模拟quad邻居/helper lane，也不默许把导数或隐式采样跨条件执行移动。
- clip(v)当且仅当每个分量≥0时保留，含0；discard无条件丢弃；if(p) discard保留¬p。裁剪条件引用执行当时的不可变快照，后续变量写入不改变它。

采样参数与裁剪边界依据官方定义：[Sample](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-sample)、[SampleLevel](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-samplelevel)、[SampleGrad](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-to-samplegrad)、[clip](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-clip)。共享操作模型只要求同一操作对同一完整输入给出相同输出。

因此Lean保证的是接受子集的理想实数/共享操作模型等价，不是GPU浮点逐位相同、过滤器实现或整条HDRP管线正确。两版采用相同顶点/插值/包装；顶点变换、光栅化和实际硬件行为由有限GPU测试覆盖，未形式证明。DXC、源码适配器和语义定义仍在可信边界内，转换器自身尚未形式证明。

工具生成定义及完整待证命题，proof/TexturedProof.lean等为手写证明。检查器另建模块绑定本次完整目标，并审计传递公理，仅允许propext、Classical.choice、Quot.sound。sorry、自定义公理、伪造同名目标均拒绝。报告保存源码、生成定义、证明、所用语义模块与依赖锁哈希。Lean证明是本地可信开发输入，不作为陌生代码沙箱。

## 输入范围

约束继续用schema2：ranges的键为输入完整名称，值为精确十进制字符串闭区间；向量逐分量、varying逐位置施加，未列输入不限区间。例如：

```json
{"schema":2,"ranges":{"_Tint":{"min":"0","max":"1"},"_Cutoff":{"min":"0","max":"1"}},"nonzero_vectors":[]}
```

结构体叶用 input.geometry.normalWS 等完整路径。normalize解释为 v/sqrt(dot(v,v))。schema2/3独立配对仍要求每个normalize有匹配的 nonzero_vectors 输入/swizzle前提，表示dot(v,v)>0，缺失返回INVALID_INPUT。schema4配对则生成每个运算的“执行条件→dot(arg,arg)>0”作为待证结论，可处理计算表达式及分支保证；显式nonzero_vectors仍只是用户提供的前提，工具不会偷偷添加假设。无法证明定义域返回UNPROVED。所有执行绑定和实参都检查，即使结果未使用；未调用函数检查语法、初始化和展开上限，不增加数学域义务。[HLSL normalize定义](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-normalize)

## 支持的源码

- 一个返回float4、SV_Target的像素main；numeric值参数或叶字段带semantic的嵌套结构体输入；可选一个register(b0) cbuffer，float/float2/float3/float4字段。
- 具名嵌套结构体、字段读写、整记录按值复制/返回；默认按值非递归辅助函数及重载、读取uniform。入口参数/uniform不可写，helper参数可修改自己的副本。单字段读取只需该字段初始化；整记录复制/实参/返回须全部初始化。
- 局部声明/初始化/嵌套块、完整变量或字段的=、+=、-=、*=；精确十进制、括号、加减乘、负号、向量构造、swizzle、标量广播、dot/normalize/lerp/saturate。
- 标量bool局部、内部结构体字段及helper参数/返回；比较、!、&&、||、bool相等；一般if/else、嵌套分支、数值/记录/布尔赋值合并、标量条件?:、main与helper提前return。固定 `-HV 2021`，标量&&/||/?:短路；未进入的normalize不要求合法，已执行的必须证明合法。函数return仅结束当前调用，discard结束对应位置的整个Shader。普通别名/算术保留完整输入函数，guard外不会一律清零。
- 全局Texture2D<float4>（含默认Texture2D）和SamplerState，显式register(tN)/register(sN)，无重复槽位/别名。Sample(sampler,float2)、SampleLevel(sampler,float2,float)、SampleGrad(sampler,float2,float2,float2)。不接受offset/status/clamp等附加重载。
- ddx/ddy及各自fine/coarse的float1..4；clip(float1..4)、discard、if(两个float标量的< <= > >= == !=比较) discard，可有只含discard的花括号，无else。
- void辅助函数可包含上述裁剪/void调用，可无return或末尾return;。裁剪只能位于main/void helper语句；numeric/record helper不可改变裁剪状态，避免表达式求值顺序产生效果歧义。void调用只能是语句。

两份入口参数名/顺序/类型/完整名义布局/semantic、cbuffer字段布局及资源名/类型/顺序/槽位、输出semantic均须完全一致，错误直接拒绝，不靠反射猜配。内部结构体/函数名可不同。

仍不支持bool stage输入/bool cbuffer、向量条件、循环、out/inout、原型/递归、结构体聚合初始化/方法、资源参数/别名、向量分量左值、矩阵/数组、原始除法、任意pow、其它纹理/Buffer/compute操作以及预处理。所有函数体检查具体语句/表达式/调用和初始化，不能把未知代码藏在未调用helper中。未知类型/节点/重载明确拒绝。[HLSL2021短路定义](https://github.com/microsoft/DirectXShaderCompiler/wiki/HLSL-2021)

上限：64结构体/每结构64字段、16嵌套层、每记录4096叶、128函数、32调用层、4096次展开调用、64输入叶、4096绑定、128裁剪事件、每种资源16个；控制流另限32层分支/每帧128返回分支，布尔共享图限4096节点/256深度。SSA与裁剪事件交错记录，完整条件以共享布尔图发射，避免重复展开。采样/导数结果可直接取分量，如 _BaseMap.Sample(...).rgb。数字使用原始源码文字，拒绝八/十六进制/整数后缀；接受LF/CRLF，不接受预处理/拼行及其它物理换行字符（含注释）。

| 状态 | 含义 |
|---|---|
| PREPARED | 已导入并生成命题，尚未检查证明 |
| PROVED | 本次完整目标及证明通过Lean与公理审计 |
| UNPROVED | 当前证明未通过，不能据此断言两份源码不等价 |
| UNSUPPORTED / INVALID_INPUT | 超出支持范围或输入/约束错误 |
| ENVIRONMENT_ERROR / INCONCLUSIVE | 工具缺失/变化、超时或目录占用 |

运行使用Windows文件锁；持锁者写IN_PROGRESS及最终报告；并发检查返回INCONCLUSIVE，不覆盖运行者报告。旧schema1/默认lerp命令保留。

## 文件与依赖

shader_ast.py读取固定DXC树和精确数字；shader_types.py解释声明/记录；shader_effects.py统一资源/方法/裁剪语法规则；shader_validation.py按位置静态检查全部函数；shader_frontend.py解释成SSA与效果事件；shader_lean.py检查域并生成旧数值模型，shader_fragment.py提升完整函数及效果；shaderformalize.py负责配对、快照、锁、目标绑定和审计。shader_eval.py与shader_fragment_eval.py只用于有限回归/具体反例，不生成形式证明。

shader_control.py拥有条件执行帧、Shader存活状态、分支合并及函数返回；shader_control_values.py提供不可变条件值；shader_boolean.py共享并化简命题图；shader_control_lean.py发射schema4及定义域结论。Control.lean复用既有数学定义，无新公理。shader_control_eval.py为独立有限求值器。

proof/ShaderFormalize/Model.lean和Fragment.lean定义数学语义。dependencies.lock.json固定官方工具与二进制SHA256；proof/lake-manifest.json固定mathlib/传递Git revision，无额外submodule；FetchCache复用锁定mathlib的缓存实现。进程局部配置不修改全局PATH/elan/Git/curl。

.tools/、.cache/、proof/.lake/、artifacts/、生成Lean模块由Git忽略；提交源码/锁/手写证明/模板/必要说明与精简证据。Unity资产由脚本重建，不把Library复制入仓库。实验和完整日志留artifacts便于诊断，正式材料见planning/evidence；用户资料不清理。

## 可选官方 HDRP/Lit 调查

`python tools/inventory_hdrp.py --project '外部Unity工程绝对路径'` 仅供开发调查。当前固定HDRP17.5.0的Lit Forward宏配置，镜像并记录146份相关源码，固定配置的预处理和完整DXC typed AST解析均成功。转换器仍拒绝该输入，尚无Lit等价证明，也不把Unity包写入核心依赖。[具体缺口与复现](docs/hdrp-investigation.md)；宏、源哈希、诊断和完整输出在artifacts/hdrp/。
