# Unlit 材质执行记录

2026-10-24，授权/设计快照提交 197651f。当前使用方式以根 README 为准，本文件保留实际执行、修复和验收记录。

## 设计检查与实际范围

独立 P 第一轮指出手动绘制球体无法保证保存场景能正常被 HDRP 相机调度；补入保存并重载场景、实际 Camera 经 StandardRequest 渲染回读要求，第二轮通过。td doc-pending 仍报告未注册 TreeDive，不创建新分区。用户本轮目标和人工方案审阅豁免已经记录在 execution-authority.md。

实现将前端职责拆成 shader_ast / shader_frontend / shader_lean，原 shader_model 保留兼容入口。局部变量和每次赋值生成不可变绑定，变量依赖声明身份而非名字。cbuffer、参数、类型与 semantic 精确匹配；源数字文字、路径/换行等原有严格检查保留。schema 2 支持向量区间和明确 nonzero_vectors；执行过的 normalize 即使返回未使用/值被覆盖也检查。

新增 examples/unlit 原始/改写/错误版本：底色环境项、方向光 Lambert 和平方边缘光。原始写法将底色乘整个光照项，改写展开分配律、复用结果；错误版本把漫反射项加号改为减号。颜色、光照方向、环境和边缘光强度来自 UnityPerMaterial；法线和观察方向来自顶点到片元的插值。

Lean 的 normalize 定义使用 Real.sqrt，并明确 noncomputable；这是实数数学定义而非待运行的数值实现。生成定义加入 noncomputable section，向量构造 lambda 明确 Fin 维度；证明保留独立目标绑定与传递公理审计。已锁定的 mathlib 版本不变，FetchCache 新增 Real.Sqrt、Ring、FinCases 模块。额外 673 个缓存文件下载后，总计 1387 个模块解压成功；最后少量网络请求停滞，仅重试缺失项，进程本地 curl 配置增加单请求 120s 上限，无全局设置变更。

## 初验与实际修复

- 39 项标准库 unittest/DXC 源码回归通过。涵盖赋值顺序、同名 uniform 被局部变量遮蔽、构造/分量顺序、未初始化读取、分支拒绝、uniform 不可写、cbuffer 顺序不匹配、归一化别名/缺失前提/全零矛盾、死赋值仍需前提，以及上一轮全部路径/词法/报告/写锁用例。
- 新材质实际 Lean PROVED 初验完成：build 211.344s（包含 Model 首次 96s、生成定义 38s、证明 50s），独立检查 32.078s。仅允许的三个标准公理，无 sorry/自定义公理。原始字节 SHA256 为 1bd9a452d7bc0a0ccabf71fd1c02542a2c194ab87b3d6894566634313fe0200f，改写版为 862d940125df9b38a80fddf502377a912b4ad1fa1e25388d464e35ca42c596a4。
- 首次 Unity 数值检查失败，实际原因是 ShaderLab Color 属性在 Linear 色彩空间绑定时从 sRGB 转换，而 CPU 最初使用原始 UI 值。CPU oracle 现按真正进入 HLSL 的颜色值计算，条件和证明仍对应 HLSL 输入。此修复没有把两侧相同当成唯一正确性证据，仍与独立 CPU 公式比较。
- 实际场景相机最初白屏；使用 HDRP 内建红色 Unlit 材质做对照仍白，排除仅自定义材质公式导致。对专用相机关闭 Postprocess / ExposureControl / AtmosphericScattering 后可见；这是保存相机的局部设置，不改项目全局配置。
- 随后场景输出橙色条带。检查图片发现 NumericProbe pass 缺少 LightMode，被 HDRP 按 SRPDefaultUnlit 调度，球体 UV 被用于测试全屏顶点。现明确标为 ShaderFormalizeNumeric，仅 Graphics.Blit 按索引调用，正常场景只选 ForwardOnly。固定 b0 与 HDRP global cbuffer 的疑点经本地宏核查排除：raster 的 GLOBAL_CBUFFER_START 不固定寄存器，RayTracing 才使用 reg/space1。
- Unity 初验 PASSED：144 组输入、2304 个回读像素，GPU/CPU 最大误差 2.6244463757763015e-07，容差 1e-4；错误 shader 最大差异 0.9415104389190674。保存并重载的场景通过实际 HDRP Camera StandardRequest 渲染，两球各 18232 个有色像素；同一球体/相机仅切换材质，对齐图像最大差异 0。截图已实际检查是两个带漫反射/边缘光的球，不是数值 pass 条带或空背景。

## 统一验收与复审状态

tools/run_demo.ps1 已接入旧/新两个例子：全部前端回归，旧错误优化/范围/自定义公理/sorry/伪造目标/正例，以及新增缺失方向条件/错误材质/正确材质，然后两套 Unity GPU 检查。完整运行命令为 pwsh -NoProfile -File tools/run_demo.ps1 -UnityProject '<本机 HDRP 工程>'，进程退出码 0，末尾 Demo passed。39 项回归、9 项控制全部符合预期；两套 Unity 检查 PASSED。完整日志位于 ignored artifacts/unlit-full.log，精简机器证据提交在 planning/evidence/unlit-material-2026-10-24.json。

最终新材质 Lean PROVED，build 65.141s、独立检查 27.438s，三个允许公理；最终 Unity 数值误差、错误版本差异、18232/18232 像素计数及对齐图像误差与初验一致。最终图片已复制到受版本管理的 planning/evidence/unlit-preview-2026-10-24.png。源码/约束/证明/语义/依赖哈希保存在精简证据中。

独立 Q 首轮只读检查当前前端/输入域/Lean 发射未发现已知误译，并要求补齐新材质正负例、场景实测和单命令验收联动；补齐后，第二轮核对统一结果与实际图片，结论通过，无阻断性问题。README 已改成当前材质的使用说明。Q 后无实现语义变更，只整理证据、文档与 shader_ast.py 末尾空白；git diff --check 通过。

本次提交保存实现与证据，不 push，不修改全局配置，不宣称人工 H-X 已接受或已正式归档。临时报告和本地工具/构建缓存继续由 Git 忽略；Unity 资产由脚本重建，不复制 Library。未删除用户资料。
