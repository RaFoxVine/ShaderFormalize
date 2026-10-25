# 官方 HDRP/Lit 固定输入调查

这是下一阶段选材的开发记录，不属于核心运行依赖，也不是完整Lit验证结果。目标是取得一份确定配置的官方Shader，让后续能力缺口有真实输入依据。

## 输入与复现

本机HDRP17.5.0，包缓存目录 `com.unity.render-pipelines.high-definition@6461a40020a9`，入口 `Runtime/Material/Lit/Lit.shader` 的共享HLSLINCLUDE和Forward Pass，片元函数Frag。工具只读取外部工程，将include镜像和报告写入ignored artifacts。

```powershell
python tools/inventory_hdrp.py --project '外部Unity工程绝对路径'
```

配置选择D3D11片元、DXC、target4.5、alpha test、关闭decal、FPTL灯列表、关闭屏幕空间阴影，固定三种阴影质量宏。DEFINES常量及result.json完整记录每个值；未选关键字保持未定义。Unity专用include_with_pragmas被转换为普通include，pragma原文保留为来源信息；这是一份明确的独立编译配置，未宣称复现Unity内部所有自动注入设置。

146份include已记录原始SHA256，预处理约620KB，DXC以ps_6_0、Frag、-HV2021成功生成约8.9MB typed AST。源与输出确切哈希由调查报告提供；包含关系同时扫到的非目标平台缺失include均在本配置下未生效。多份同名包缓存会明确拒绝，避免随机选版本。

## 已确认的转换缺口

独立DXC已经完成语法、类型和重载解析。当前适配器尚不能消费这棵树，直接导入的首个错误是 `Unrecognized AST source header`：生成的sampler1D赋值方法含嵌套位置区间 `<col:8, <invalid sloc>>`，见typed-ast.log约6416行。这是适配器树读取格式的缺口，不能据此说DXC解析失败。

同一完整AST还确认了下列现有子集之外的声明或操作：

- 第一份Hash函数使用uint、异或与右移；它们需要整数/位运算语义，不能当作实数加减乘处理。
- Frag入口为void并用out float4参数输出，当前核心只接受返回float4的main；这需要入口/输出契约适配。
- sampler内建类型含隐式C++方法，源码关联跨include文件；当前只支持单份普通源码及受控Texture2D/SamplerState声明。

这些是完整已解析源码中实际出现的内容，尚未完成从Frag出发的可达函数分析，不能把每个声明都称为该配置的运行时必需能力。矩阵、数组、其它资源与intrinsic的具体支持量也应在下阶段按实际可达代码调查。此轮没有临时忽略未知节点或改写数学语义来“导入成功”。

## 调查过程中的修正

初版导出没有SHADER_TARGET，Common.hlsl中FastLog2受 `SHADER_TARGET>=45` 保护而未定义。Lit自身声明target4.5，补充SHADER_TARGET=45后预处理和完整typed AST均成功。错误日志留在早期artifacts中供追溯；当前工具包含该宏，不能继续把FastLog2当现有阻塞。

下一阶段应先明确官方入口与源码来源映射，再按可达程序选择要增加的语言语义。仅解决树文本格式不足以验证完整Lit。
