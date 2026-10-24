# 可见的 Unlit 材质与实数等价验证

## 要交付的东西

将上一轮单 return 原型扩展到实际材质计算：两份手写 HLSL，均包含底色、环境项、Lambert 漫反射和平方边缘光。原始写法分步计算，改写版本调整局部变量、复用结果并展开分配律。输入包括插值法线/观察方向，以及 cbuffer 中的颜色、光照方向、环境和边缘光强度。两份程序输出相同 RGBA，Lean 证明覆盖明确约束内任意实数输入。

Unity 中提供可检查的 ShaderLab Shader、材质和独立演示场景，在球体上显示原始/改写效果；另用相同 HLSL 的数值 pass 检查 GPU 与 CPU 公式，并输出两侧球体预览图片。保存并重新载入专用场景，再使用该场景的实际 Camera，通过 HDRP RenderPipeline.StandardRequest 渲染回读，验证两球可见且有颜色变化；手动指定 pass 的 DrawMesh 仅作另外的对齐比较，不能代替场景相机验收。共享顶点变换、插值和 Unity 包装不在本轮形式证明范围，双方使用同一包装；证明对象明确是片元材质计算。不会把完整光栅化管线当成已证明。

Unlit 指自行计算最终颜色，不接入 HDRP 的完整 Lit/PBR/阴影/GI。此次实现上述真实材质效果，不加入纹理采样、任意 pow、分支/循环、矩阵或写 Buffer。平方边缘光对应固定指数 2，强度为材质参数。

## 职责与数据流

- 固定 DXC 仍负责 HLSL 语法/类型检查。Python 适配器消费完整带类型 AST：float/float2/float3/float4、普通局部声明/初始化、整变量顺序赋值及 +=/-=/*=、构造器、swizzle、dot/normalize/lerp/saturate、加减乘/负号。局部状态用不可变绑定序列表示，每次赋值产生新值，避免复用可变引用导致含义改变；拒绝读取未初始化值、修改 uniform、未知转换/声明/语句及用户函数冒充 intrinsic。
- 支持一个显式 cbuffer，基础字段类型，声明顺序、名字、类型、cbuffer 名和 register 必须两侧一致；入口参数也精确匹配。无反射配对、无自动推测布局。首个材质使用 UnityPerMaterial register(b0)。
- IR 与 Lean 生成不再固定三个参数，所有入口/材质输入有明确身份和类型。保留原 lerp 示例与 schema 1 约束。新增 schema 2：按名字指定标量/整向量各分量共同闭区间，十进制字符串；nonzero_vectors 明确指定输入或 swizzle 非零。未知名字/字段、不适用约束和空域拒绝。
- normalize 真实数学定义为 v / sqrt(dot(v,v))；Microsoft 文档说明零长度时结果不定。所有实际执行的 normalize（包括局部别名解析后）都必须被 nonzero_vectors 明确覆盖，缺少条件就拒绝，不偷偷假设 normalize(0)=0。非零约束与全零区间冲突也拒绝。暂不支持对任意计算表达式归一化，允许输入及 swizzle/局部别名，保证前提可清楚表达。
- Lean 语义扩展任意 2–4 维向量的 dot/normalize，新增 Real.sqrt；证明主要对相同 dot/normalize 结果使用代数分配律，不需要把它们改成经验近似。沿用独立目标绑定、公理审计、源字节快照和单写锁。新增材质的手写证明；旧示例保持可证明。
- Unity 使用同源 HLSL 字节副本和共享 ShaderLab 模板。颜色/光照/边缘光强度进入真实材质字段；网格 pass 读取球体法线、世界位置和相机位置，调用被证明的 main；数值 pass 用明确 normal/view 输入调用相同 main。原始/改写有独立材质，属性可编辑。仅创建 Assets/ShaderFormalizeUnlit 下资产/场景，不改已有场景或项目全局设置；临时资源 finally 释放、恢复 RenderTexture.active 和场景状态。

## 范围条件和验证

颜色各分量 [0,1]，环境 [0,1]，边缘光强度 [0,4]；normalWS、viewWS、_LightDirection.xyz 非零。方向允许任意非零长度，片元内 normalize。CPU 对照使用同样公式，输入中包括非单位方向、亮/暗面、正面/掠射、强度端点。规范依据：https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-normalize 。HDRP 具体包装以当前工程本地包为准并实际编译运行。

新增有意义的回归：先读后写/多次赋值/复合赋值、宽度与分量顺序、重名/遮蔽、初始化失败、uniform 不可写、cbuffer 不匹配、未知语句拒绝、intrinsic 冒名、normalize 缺失前提/全零冲突，保留之前所有词法与路径回归。明确测试同一输出数值正确而非仅两侧一致：GPU vs CPU、错误版本差异检测、非空/非有限检查；球体必须有非背景像素与颜色变化，原始/改写图像在容差内。

统一验收覆盖原 lerp 与新增材质。新增材质 Lean PROVED、故意改错 UNPROVED，既有 sorry/公理/伪造目标守卫继续执行。依赖继续在当前目录锁定，用原 mathlib 缓存 API 补 Real.Sqrt、Ring、FinCases；不引入全局安装或新包版本。独立 P 后导出本轮精确执行授权，实施/初验后独立 Q、修复、文档与本地 Git 提交；不 push。

## 文件与完成条件

主要修改 tools/shader_model.py（必要时拆分 AST/表达式/语句/Lean 生成职责）、shaderformalize.py、验证与 Unity 脚本；proof 语义/缓存入口及新增手写证明；examples/unlit；unity 材质模板/执行脚本；README 和本轮记录。可重建输出忽略，不拷贝 Unity Library。旧输入/CLI 用法兼容，失败不复用旧成功报告。

完成条件：一条完整命令通过旧/新证明和负例、GPU/CPU 数值检查、对齐球体比较及保存场景重新载入后的真实 HDRP Camera 渲染检查；交付可见预览和可在 Unity 打开的场景/材质；说明实际证明边界与当前支持范围。不存在 TreeDive 注册项目，td doc-pending 仍报告不存在 _TreeDiveCode；继续沿现有 planning 留过渡记录，不自行创建新知识分区。

独立 P 第一轮指出手动 DrawMesh 不能证明场景相机能调度此材质，以上场景重载和实际 HDRP Camera oracle 已作为必须结果补入。接口可行性已经在本地包 HDRenderPipeline.cs 的 StandardRequest 支持及完整 Render 调用查证。
