# 二进制与多pass规格验证：规划状态

当前入口为[目标与实施框架](delta.md)。用户已要求开始二进制，后续再细化规格接口，完整HDRP不作本轮门禁。首个具体二进制切片已完成、独立审阅通过并提交推送，grant见execution-authority.md；其余方向继续分片，整体二进制迁移尚未完成。

| 工作 | 规划 | 授权 | 执行 | 进入实施前必须解决的问题 |
|---|---|---|---|---|
| 二进制标量位运算接入（binary-bits-001@r1） | Execution Ready，独立实施前审阅通过 | Completed：binary-bits-grant-001 | Completed：312单元、21正式控制、原型19、实数回切及独立Q通过，功能提交1f7c57a已推送并核对 | 无本片遗留；后续迁移见下列切片 |
| 二进制分支与局部赋值（binary-control-002@r1） | Execution Ready，control-design.md独立P第1轮通过 | Approved：用户“按此实施”，binary-control-grant-002 | Implementing | 104旧目标/状态逐项一致，29项IEEE初测通过；继续真实证明及完整回归 |
| Overnight B：binary-data-003@r1 | data-design.md独立P第1轮通过，待A完成依赖 | 限定PLAN_AND_CODE委托，见overnight-request-2026-10-31.txt | 已具体规划；精确grant前不写代码 | A完整验收及Q、派生精确grant与Approved |
| Overnight C：binary-compute-004 | Candidate，compute-uint-design.md草案 | 限定PLAN_AND_CODE委托，见overnight-request-2026-10-31.txt | 已只读调查/拟稿；精确grant前不写代码 | 用B实际接口对齐、独立P、精确grant与验收 |
| Overnight D：规格与计算图下一批方案 | Candidate，spec-graph-design.md草案 | PLAN_ONLY委托 | 已调查/拟稿，不实施 | 用B/C实际结果对齐；首规格片与符号循环/图发布具体化 |
| 固定规格与二进制执行的公共接口 | Outlined（二进制后细化） | 目标保留 | 未实施 | 先跑通实际流程再形成P/R细节，保留输入依赖和数组整体误差能力 |
| 二进制语言与整数资源/循环支持 | Candidate | 仅调查/拟稿 | 未实施 | AST/DXIL选择、符号有界循环、类型化资源、旧入口迁移及回归语义 |
| 手写计算图及多pass内存组合 | Candidate | 仅调查/拟稿 | 未实施 | 数据格式、符号尺寸计算及uint32转换/溢出、尾块guard、初始化/别名/同步、VerCors访问事件与Lean执行语义的对应合同 |
| uint32两图前缀和综合验收 | Outlined | 方向确认 | 未实施 | 依赖上述接口；任意合法N、真实HLSL、安全及规格证明、正负控制、独立实施审阅 |
| 确定性采样与BRDF/LUT误差 | Outlined | 方向确认 | 未实施 | 固定格式/采样精度profile、具体GPU关联边界、误差引理与资产绑定 |
| 主路径二进制迁移闭合 | Outlined | 方向确认 | 未实施 | 既有案例逐项重新验收、实数作为规格层、退出旧执行入口的具体兼容合同 |

独立框架审阅已完成，未发现方向阻塞。审阅指出的成功/失败/终止结果类型、安全模型间访问行为对应、符号N尺寸算术已列为切片细化事项；文件哈希绑定不能代替两个模型之间的语义对应。该审阅不自动把Candidate标为Execution Ready。首片真实门禁与独立Q已通过；实数/Compute公共产品源未变，按122个保护路径指纹及实际回切检查隔离，没有重跑旧83项长门禁。已有TreeDive CLI当前找不到_TreeDiveCode；继续在本仓库planning保存本节点，不新建其它Project。
