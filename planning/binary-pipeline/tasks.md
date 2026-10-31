# 二进制与多pass规格验证：规划状态

当前入口为[目标与实施框架](delta.md)。位运算与纯计算分支两批已完成真实验收和独立审阅；用户已批准Overnight继续向量/局部数组/固定循环与uint单pass Compute，并仅规划自定义规格/多pass。精确授权见execution-authority.md，整体二进制迁移尚未完成，完整HDRP不作本轮门禁。

| 工作 | 规划 | 授权 | 执行 | 进入实施前必须解决的问题 |
|---|---|---|---|---|
| 二进制标量位运算接入（binary-bits-001@r1） | Execution Ready，独立实施前审阅通过 | Completed：binary-bits-grant-001 | Completed：312单元、21正式控制、原型19、实数回切及独立Q通过，功能提交1f7c57a已推送并核对 | 无本片遗留；后续迁移见下列切片 |
| 二进制分支与局部赋值（binary-control-002@r1） | 独立P第1轮通过 | Completed：binary-control-grant-002 | Completed：319全单元/83核心、29IEEE单元/27控制、实数回切、原型19、独立Q第2轮均通过 | 无本片遗留；104旧目标/状态一致，证据见binary-control-2026-10-31.json |
| Overnight B：binary-data-003@r1 | Execution Ready，data-design.md独立P第1轮通过，A依赖已完成 | Approved：binary-data-grant-003，限定委托内派生 | Approved，grant与本状态先于代码持久化 | 迁移前110目标已实际保存，按方案开始实施 |
| Overnight C：binary-compute-004 | Candidate，compute-uint-design.md草案 | 限定PLAN_AND_CODE委托，见overnight-request-2026-10-31.txt | 已只读调查/拟稿；精确grant前不写代码 | 用B实际接口对齐、独立P、精确grant与验收 |
| Overnight D：规格与计算图下一批方案 | Candidate，spec-graph-design.md草案 | PLAN_ONLY委托 | 已调查/拟稿，不实施 | 用B/C实际结果对齐；首规格片与符号循环/图发布具体化 |
| 固定规格与二进制执行的公共接口 | Outlined（二进制后细化） | 目标保留 | 未实施 | 先跑通实际流程再形成P/R细节，保留输入依赖和数组整体误差能力 |
| 二进制语言与整数资源/循环支持 | Candidate | 仅调查/拟稿 | 未实施 | AST/DXIL选择、符号有界循环、类型化资源、旧入口迁移及回归语义 |
| 手写计算图及多pass内存组合 | Candidate | 仅调查/拟稿 | 未实施 | 数据格式、符号尺寸计算及uint32转换/溢出、尾块guard、初始化/别名/同步、VerCors访问事件与Lean执行语义的对应合同 |
| uint32两图前缀和综合验收 | Outlined | 方向确认 | 未实施 | 依赖上述接口；任意合法N、真实HLSL、安全及规格证明、正负控制、独立实施审阅 |
| 确定性采样与BRDF/LUT误差 | Outlined | 方向确认 | 未实施 | 固定格式/采样精度profile、具体GPU关联边界、误差引理与资产绑定 |
| 主路径二进制迁移闭合 | Outlined | 方向确认 | 未实施 | 既有案例逐项重新验收、实数作为规格层、退出旧执行入口的具体兼容合同 |

独立框架审阅已完成，未发现方向阻塞。审阅指出的成功/失败/终止结果类型、安全模型间访问行为对应、符号N尺寸算术已列为切片细化事项；文件哈希绑定不能代替两个模型之间的语义对应。该审阅不自动把Candidate标为Execution Ready。位运算首片未改实数/Compute公共源，使用122个保护路径及回切证据；分支片提取了共享骨架，已实际重跑全部83核心、核对104旧目标/状态并完成独立Q。已有TreeDive CLI当前找不到_TreeDiveCode；继续在本仓库planning保存本节点，不新建其它Project。
