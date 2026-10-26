# 固定Forward接入：实数边界与恢复条件

本记录供下一轮实现者恢复完整HDRP/Lit Forward工作。普通材质扩展仍在进行；这份记录不代表完整Forward已转换或已证明。

## 当前输入与结果

固定输入为HDRP17.5的Forward配置，来自本机明确选择的Unity6000.5.9工程；完整预处理源码和DXC AST留在ignored `artifacts/forward-analysis/input`，未把Unity源码重新发布。可追溯的宏、版本、产物哈希与入口上界见`../evidence/hdrp-forward-analysis-2026-10-26.json`。DXC已成功解析，分析状态ANALYZED只代表调用结构分析成功。当前数学转换的首个失败仍是sampler1D结构体的DXC隐式赋值方法中嵌套invalid source location的AST格式，不是下述最小例的错误。

已独立隔离的数学边界是普通实数的asuint编码检查。以下完整源码可直接保存后用固定DXC和shared前端重现：

```hlsl
bool IsNanLike(float x){uint bits=asuint(x)&0x7fffffffu;return bits>0x7f800000u;}
float4 main(float4 a:COLOR0):SV_Target{return IsNanLike(a.x)?float4(1.0,1.0,1.0,1.0):a;}
```

```powershell
python tools/shaderformalize.py prepare --frontend shared --original real-nan.hlsl --optimized real-nan.hlsl --constraints examples/control/constraints.json --output artifacts/real-nan
```

本机已有固定DXC实际解析和导入记录：UNSUPPORTED，`asuint of an ordinary real requires unsupported float encoding`。source SHA256为ae380f75f9b35edb4b47fa2fd13c20e14423f6b1426a77c5ad88bde5002558a6，AST为d80954620ed86181163a47f7a8fdb63d43d9b782c8f15034666dce96142c55fc；原始探针/报告位于`artifacts/language-probes/real-nan-boundary.*`。源码哈希指该探针实际字节，不保证从Markdown复制后的换行字节相同。这是独立语义复现，不是GPU测试或完整Forward检查。

## 为什么不能直接跳过

静态可能路径为Frag→LightLoop→EvaluateBSDF_Env→EvaluateLight_EnvIntersection→IntersectSphereProxy→IsNaN。球形代理先求平方根，再用NaN检查恢复无交点的距离；半径1、起点(2,0,0)、方向(0,1,0)给出判别式-12。因此这里的NaN可能表示几何上的无交点，不能把IsNaN统一改成false，或私自增加判别式非负的输入前提。路径是保守静态可能路径，未证明每个绘制都会执行。

## 下一轮应执行的工作

保留核心实数和精确uint模型；先确定一份具有明确数学意义的Forward目标。首选调查固定配置能否排除这条异常恢复路径，并证明排除条件；若不能，则须另行确定如何把这段几何恢复逻辑表达为实数上的分段函数，以及两份输入源码与这个表达之间的关系。不能仅用一个黑箱谓词代替IsNaN便宣称忠实于原HLSL。

恢复实施前需要用户确定的最小问题是：是否允许将第一份官方Lit验证目标限定为已证实不执行该路径的固定配置，还是必须保留当前反射探针恢复行为？后一种要求新的异常值/源码语义合同，超出当前纯实数约定。调查配置不保证其余入口、资源、循环、数学和外部位载体缺口随之消失。

明确后再形成Ready切片：AST格式/Frag-out入口、只读Buffer及纹理模式、实际循环/数学和外部位载体分别说明消费者、失败行为与验证方式；独立P通过并派生精确grant后才实施。完整oracle必须是选定配置的两份完整源码经真实DXC产生实际Lean目标，并通过目标绑定及公理审计；已有手工材质证明、ANALYZED和有限数值采样均不能替代。若仍需浮点编码、新公理或隐藏域假设，停止受影响接入，不扩大核心语义。
