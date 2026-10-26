# 独立 binary32 接入原型

这个原型用实际 FloatLib 运算和 Lean 定理验证浮点库可以被本项目调用。它与当前实数 Shader 证明环境分开，尚未把 HLSL 自动转换到浮点模型，也没有改变核心 `shaderformalize.py` 的 `PROVED` 含义。

## 运行

在仓库根目录使用 Windows x64、PowerShell7、Python3.9+、Git 和 curl：

```powershell
pwsh -File prototypes/ieee/bootstrap.ps1
pwsh -File prototypes/ieee/run.ps1
```

工具安装在本仓库 `.tools/lean-4.35.0-windows`，下载和 Mathlib 缓存在 `.cache/ieee`，固定 Git 依赖在本目录 `.lake/packages`。全部可重新获取，不依赖 Unity、全局 elan 或编辑器环境。现有核心 Lean4.24 与其依赖锁不变。bootstrap 通过独立进程环境清除外部 `LEAN_*` 与 `FLOATLIB_BUILD_DIR` 设置，避免构建输出写入其他工作目录。

首次需要约860MiB的 Lean4.35 下载以及对应的源码、编译和 Mathlib 缓存空间。下载固定官方 URL 并验证官方 SHA256；网络慢时分块并发，超时保存已验证范围，可重跑 bootstrap 续传。它只抓实际导入模块所需的 Mathlib 缓存，没有要求重建或审计整个上游库。

## 检查什么

`Main.lean` 窄导入 binary32 配置和运算规格定理。普通运算使用 FloatLib 的 binary32、round-to-nearest-ties-to-even；位解释使用其完整存储位构造与提取接口，不把整数转浮点的数值转换当作 `asfloat`。

检查包括加减乘除、sqrt、除零无穷、负数 sqrt 的 NaN、NaN 比较、正负零的数值/位相等区别、包含次正规数和 NaN 编码的几个位往返，以及浮点重结合得到0与1的具体反例。

Lean 部分直接应用上游定理，证明一个由乘、除、加组成的可执行表达式等于同一运算顺序的规格表达式，并使用完整存储值往返定理。不会借实数结合律证明错误的浮点重结合；也不会把有限运行例子报告为任意 HLSL 的全称等价证明。

结果写入 `artifacts/ieee/result.json` 和 `probe.log`。每次运行先记录 `IN_PROGRESS`，全部成功后替换为 `EXTERNAL_LIBRARY_PROTOTYPE_PASSED`；工具启动、依赖读取或检查失败均记录 `FAILED` 并非零退出。成功报告保存工具链版本、例子/依赖锁/manifest/日志哈希和实际成功断言数。

## 来源与边界

2026-10-27，固定依赖的2396项构建成功；19项运行检查和两条定理通过，定理仅依赖Lean的三项标准公理。环境搬回仓库主目录后已再次实际运行成功，独立接入审阅通过。[机器证据](../../planning/evidence/ieee-integration-2026-10-27.json)。

- [FloatLib](https://github.com/lean-dojo/FloatLib)，固定提交在 `lakefile.lean` 与 `dependencies.lock.json` 中；其主代码为 MIT。
- Lean4.35 官方 Windows ZIP 的大小、URL 和官方发布摘要在 `dependencies.lock.json`。
- `lake-manifest.json` 固定 FloatLib、mathlib 与辅助依赖的提交，不追踪可变分支。

现阶段接受上游库对自身能力的声明，通过构建和代表例确认接入。我们没有声称独立复核了全部上游证明、全部浮点格式或全部32位输入。HLSL/D3D 的融合、次正规数处理、近似函数和硬件配置仍需后续连接；此原型的成功不自动成为实际 GPU 逐位相等保证。
