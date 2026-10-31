# 二进制整数、位字段与 hash

本入口把受支持的 HLSL 转成 FloatLib binary32 与 UInt32 运算，再检查两份程序的完整输出存储位相等。float 和 uint 可以经 asuint/asfloat 原样解释同一组32位，不需要先转成实数或标记特殊的 float 载体。

```powershell
python tools/ieeeformalize.py check --original examples/ieee-bits/packing.original.hlsl --optimized examples/ieee-bits/packing.optimized.hlsl --constraints examples/ieee/constraints.json --agent-proof proof/ShaderIeee/BitsProof.lean --output artifacts/my-binary-packing

# IEEE 全套控制，同时检查默认实数入口能够正常回切。
python tools/run_ieee_suite.py
```

## 执行含义

浮点沿用 `binary32-rne-preserve-subnormals-separate-ops-v1`：逐操作最近偶数舍入、保留次正规数，没有隐式融合乘加。成功仍为 `IEEE_PROVED`，`gpu_profile_matched=false`，尚未关联具体 GPU。

标量 uint 支持加、减、乘、`& | ^ ~`、取负、`<< >>`、六种比较，以及 uint/bool 的三元选择。加减乘和取负按模 2^32 计算；比较使用无符号数值。十进制及十六进制 uint 常量都检查源码 token 与 DXC 解析值一致。

移位使用移位量低5位：移32位等于移0位，移33位等于移1位。固定 DXC 的动态移位输出会显式先与31相与；Lean UInt32 的定义也采用模32的移位量。这与 [Direct3D 移位指令的规则](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/ishl--sm5---asm-)一致。

`asuint(float)` 和 `asfloat(uint)` 是存储位重解释，包括 NaN payload、正负零和次正规数；`asuint(uint)` 是恒等操作。两个方向的完整位往返均有全称定理。它们不是数值 cast：`(float)uintValue` 和 `(uint)floatValue` 尚不属于这个入口。

## 示例和证明对象

- `packing`：四个8位字段装进一个32位字，经过 struct/helper 的 float 存储位往返后拆出；与直接掩码得到各字段的写法比较。
- `hash`：helper 中的 uint32 混合运算与保留同一运算顺序的展开版比较。这里证明确定的32位映射相同，不证明 hash 的统计分布。
- `shift`：任意位移量与显式掩码位移量比较。
- `wrap`：UINT_MAX 回绕、双重取负、双重按位非、异或恢复；也包含0/31/32/33/UINT_MAX位移及高位无符号比较的内核归约检查。
- `unsigned`：无符号高位比较和整数/布尔三元选择的等价改写。
- `roundtrip`：位模式经 helper 与 struct 字段保存恢复。

每组有独立错误版本。`UNPROVED` 只表示本次提交证明没有通过；具体反例或统计测试不能替代全称证明。

2026-10-31位运算首批验收：312项Python测试、21项IEEE正式控制（9项证明通过、12项未通过对应提交证明）、默认实数入口回切和19项库原型检查均符合预期。原九项IEEE控制保留；六个新正例均检查完整目标绑定和原三公理白名单。[机器证据](../planning/evidence/binary-bits-2026-10-31.json)保存输入、目标、证明和日志摘要，以及负控具体失败原因。

示例用 float4 承载原始输入/输出存储位，验证的是位字段计算核。它没有定义真实 G-buffer 的资源格式转换、纹理写入或采样行为。

## 当前范围

复用已有 struct、按值 helper 和 float 向量支持，入口仍为返回 float4 的像素 main。[纯计算分支和局部赋值](binary-control.md)支持if/else、提前返回和八种uint复合赋值。uint 向量、signed int、整数除余、循环、资源访问和数值 cast 尚未接入；未支持的写法明确拒绝。当前只接受空 schema2 输入约束。

所有检查共用仓库内的 Lean4.35、依赖及 workspace 写锁。主实数入口和 Compute 入口保持既有语义；本片完成不代表整体二进制迁移已经闭合。完整迁移目标及后续规格/计算图工作见 [迁移节点](../planning/binary-pipeline/tasks.md)。
