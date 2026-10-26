# 可复用工作调查

面向本项目的实现者；调查截至 2026-10-26。候选记录来自作者论文、官方文档和项目仓库，不表示已经复现或完成源码/许可证全面审计。先用资料筛选，再对少量候选做隔离验证，避免直接引入庞大依赖。

## 语言与数值的依据

- [微软 intrinsic 总表](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-intrinsic-functions)及 [SM6 Wave/Quad 表](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/hlsl-shader-model-6-0-features-for-direct3d-12)：coverage.csv 的两个函数名称来源。总表中 asuint 两行包含不同入口：double→两个 uint 的重载不能误计为当前已支持。
- [HLSL 工作草案](https://microsoft.github.io/hlsl-specs/)、微软运算符/类型/语句/资源文档：补充函数表之外的语言能力。草案、较新 Shader Model 和本机固定 DXC/HV2021 是不同的覆盖边界。
- [Direct3D 浮点规则](https://learn.microsoft.com/en-us/windows/win32/direct3d11/floating-point-rules)：NaN 比较、min/max、次正规数及精度等规则，说明不能把 HLSL 直接等同于一套无额外配置的 IEEE 运算。具体 D3D12/DXIL profile 仍需逐操作核实。
- [SMT-LIB FloatingPoint](https://smt-lib.org/theories-FloatingPoint.shtml)：可借鉴浮点逻辑比较与程序 fp.eq 分开的设计。抽象 FP sort 不能代替需要区分 NaN payload 的完整位模式。

## 数值库候选

| 候选 | 可复用之处 | 当前限制与决定 |
|---|---|---|
| [FloatLib](https://github.com/lean-dojo/FloatLib) | binary32/64 等格式、舍入/特殊值、可执行操作与规格关系证明；仓库主代码 MIT | README/入口及依赖文件初筛；当前 Lean/mathlib 4.35，高于项目 4.24。优先独立评估，尚未通过本项目的证明缺口/公理审计。未经检查的宿主 FPU 快路不进入证明。第三方组件许可单独核对。 |
| [FloatSpec](https://github.com/Beneficial-AI-Foundation/FloatSpec) | Flocq 路线的 Lean 浮点定义、binary/bits、除法和 sqrt；Apache-2.0 | README 指向 Lean/mathlib/CSLib 4.29；作为对照候选，语义与源库一致性需审查，不能只以无 sorry 声明决定采用。 |
| [fp-lean](https://github.com/opencompl/fp-lean) | 紧凑位表示和符号 bit-blasting 思路；Apache-2.0 | 当前完整覆盖、工具链未核实；其自动化例子的可信依赖需和本项目公理白名单核对。作为位运算证明参考。 |
| [Flocq](https://flocq.gitlabpages.inria.fr/) | 成熟的格式、舍入和运算定义；LGPL | 属于 Rocq，适合作为定义/证明依据，不能直接充当 Lean 已检查证明。 |
| [Berkeley SoftFloat](https://github.com/ucb-bar/berkeley-softfloat-3) | 软件 IEEE 运算，可作独立有限边界/随机对照；BSD-3-Clause | C 实现，不是 Lean 证明库；测试通过不等于全称等价。 |

按本项目需求初筛，FloatLib/FloatSpec 比单纯硬件 Float 包装更贴合“可证明的位与运算语义”；具体正确性、证明自动化成本和迁移成本尚未实测，因此没有作最终依赖选择。无需马上安装多个库，更无需改当前全局或项目工具链。

## GPU 程序验证

用户回忆的名称确实是 [ProofWright: Towards Agentic Formal Verification of CUDA](https://arxiv.org/abs/2511.12294)，2025-11 首发，2026-03 有 v2。论文把 VerCors 的线程/内存安全验证与 Rocq 中部分逐元素程序的结果证明结合。本文调查的具体流程以 v1 §4/§5 为依据；v2 摘要仍说明结果适用特定子集。它提供分工和权限契约范例，不表示全部 CUDA、IEEE 运算或 HLSL 前端已经解决。未确认完整可复现工具仓库，不能承诺直接下载接入。

[Proving LLM-Generated GPU Kernels Correct and Safe: Floating-Point Verification in Lean and VerCors](https://arxiv.org/abs/2610.24548)，2026-10-17，进一步展示 Lean 浮点结果证明、确定性的 CUDA 前端与 VerCors 安全检查的组合。重点阅读其 §3：超越函数作为双方共享 opaque 运算，转到实际设备仍需双方实现一致；安全成立后再按 barrier 分阶段顺序化。正文同时声明 Velvet 自动化在其设置中信任 SMT 结果，因此不能仅凭摘要或公理审计描述，就视为满足本项目所有可信边界要求。应借鉴模型与可核查证明机制，而不是导入外部成功标志。

- [VerCors](https://github.com/utwente-fmt/vercors)：MPL-2.0；可借鉴权限、共享内存与 barrier 契约。它不是 HLSL 前端/Lean 数值等价库，若接入必须处理 HLSL 翻译、后端证明可信性和 Windows 依赖。
- [GPUVerify](https://github.com/mc-imperial/gpuverify)：CUDA/OpenCL 数据竞争与 barrier 分歧检查，适合安全验证参考；不等于两份程序的功能等价判定器。采纳前另核许可、运行环境和维护状态。
- [PTX 内存一致性模型](https://docs.nvidia.com/cuda/parallel-thread-execution/#memory-consistency-model)：说明可用事件次序/可见性关系建模，而非物理缓存仿真。适用 PTX，不能直接替代 D3D 合同。
- [HLSL 0050 内存与执行模型提案](https://microsoft.github.io/hlsl-specs/proposals/0050-mem-and-exec-model/)：当前状态 Under Consideration，含多个互异候选；用于发现必须明确的问题，不当作固定 DXC 已承诺的规则。
- 已有操作文档提供较窄但可用的规则：[GroupMemoryBarrierWithGroupSync](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/groupmemorybarrierwithgroupsync)要求组内线程到达同步点，分歧分支中的调用行为未定义；[InterlockedAdd](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/interlockedadd)明确原子操作不自动提供 memory fence/barrier。实现时应从具体操作的已定义行为出发，不必等待完整统一提案定稿。

## 外部可解决与本项目必须负责的部分

DXC 解决语法/类型/重载；数值库可提供格式、舍入和运算定理；GPU 验证工作提供访问权限、同步阶段和内存关系方法。我们仍需负责 HLSL 操作到所选定义的准确映射、完整控制流与资源语义、实际执行安全义务、两份输入的对应契约，以及把最终命题绑定到输入/依赖/语义版本的可核查流程。外部项目没有这些连接，就无法直接代替本项目的完整证明。
