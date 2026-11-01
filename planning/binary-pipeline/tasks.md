# 二进制与多pass规格验证：规划状态

当前入口为[目标与实施框架](delta.md)。位运算、纯计算分支及本次Overnight的局部向量/数组/固定循环、uint单pass Compute均已完成真实验收和独立审阅。自定义规格首片已规划就绪，多pass仍逐片细化；二者尚未实施。精确授权见execution-authority.md，整体二进制迁移尚未完成，完整HDRP不作本轮门禁。

| 工作 | 规划 | 授权 | 执行 | 进入实施前必须解决的问题 |
|---|---|---|---|---|
| 二进制标量位运算接入（binary-bits-001@r1） | Execution Ready，独立实施前审阅通过 | Completed：binary-bits-grant-001 | Completed：312单元、21正式控制、原型19、实数回切及独立Q通过，功能提交1f7c57a已推送并核对 | 无本片遗留；后续迁移见下列切片 |
| 二进制分支与局部赋值（binary-control-002@r1） | 独立P第1轮通过 | Completed：binary-control-grant-002 | Completed：319全单元/83核心、29IEEE单元/27控制、实数回切、原型19、独立Q第2轮均通过 | 无本片遗留；104旧目标/状态一致，证据见binary-control-2026-10-31.json |
| Overnight B：binary-data-003@r1 | Execution Ready，data-design.md独立P第1轮通过 | Completed：binary-data-grant-003，先提交13ea195 | Completed：完整门禁及独立Q2 PASS | 无本片遗留；327/83、37/35、实数回切、原型19及110旧目标比较符合预期 |
| Overnight C：binary-compute-004@r2 | 独立P第2轮通过，A/B依赖完成 | Completed：binary-compute-grant-004，先提交c3157e0后代码 | Completed：完整五阶段及独立Q3 PASS | 无本片遗留；347/83、37/35、实数回切、原型19、16uint控制、118旧目标比较及232生成快照均核实，机器证据PASSED |
| Overnight D：规格与计算图下一批方案 | 首片spec-single-005@r2为Execution Ready，独立P2 PASS；图/符号循环Candidate | PLAN_ONLY委托，无代码grant | READY_FOR_APPROVAL：C完成，冻结接口核对保持，无规划阻断 | 下一步需批准首规格片实施；图和符号循环继续逐片细化 |
| 固定规格与二进制执行的公共接口 | 首片具体设计见spec-single-design.md修订2 | 目标保留，尚无代码grant | 未实施 | 以单候选P/R、固定任务身份、安全及Frame开始，后续扩展图与浮点误差 |
| 二进制资源与循环组合、后续语言迁移 | Candidate | 仅调查/拟稿 | 未实施 | 组合已交付的局部静态循环与uint资源，细化符号有界循环、更多资源类型及默认入口迁移 |
| 手写计算图及多pass内存组合 | Candidate | 仅调查/拟稿 | 未实施 | 数据格式、符号尺寸计算及uint32转换/溢出、尾块guard、初始化/别名/同步、VerCors访问事件与Lean执行语义的对应合同 |
| uint32两图前缀和综合验收 | Outlined | 方向确认 | 未实施 | 依赖上述接口；任意合法N、真实HLSL、安全及规格证明、正负控制、独立实施审阅 |
| 确定性采样与BRDF/LUT误差 | Outlined | 方向确认 | 未实施 | 固定格式/采样精度profile、具体GPU关联边界、误差引理与资产绑定 |
| 主路径二进制迁移闭合 | Outlined | 方向确认 | 未实施 | 既有案例逐项重新验收、实数作为规格层、退出旧执行入口的具体兼容合同 |

独立框架审阅已完成，未发现方向阻塞。审阅指出的成功/失败/终止结果类型、安全模型间访问行为对应、符号N尺寸算术已列为切片细化事项；文件哈希绑定不能代替两个模型之间的语义对应。该审阅不自动把Candidate标为Execution Ready。位运算首片未改实数/Compute公共源，使用122个保护路径及回切证据；分支片提取了共享骨架，已实际重跑全部83核心、核对104旧目标/状态并完成独立Q。已有TreeDive CLI当前找不到_TreeDiveCode；继续在本仓库planning保存本节点，不新建其它Project。
