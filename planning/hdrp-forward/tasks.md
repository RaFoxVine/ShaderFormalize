# 当前工作

| 工作 | 规划 | 授权 | 执行 | 依赖 |
|---|---|---|---|---|
| 入口调用上界与缺口报告工具 | Execution Ready，独立P第二轮通过 | 已执行，精确grant完成 | Completed，独立Q第三轮通过 | c1de3d7及固定Forward AST |
| 整数打包链路 | packing-plan.md修订1，独立P通过 | packing-authority.md | 实施/验收见packing-tasks.md | 精确uint32、实数域和静态载体边界 |
| 其余完整Forward所需通用语言/数学扩展 | Outlined | 待按Ready范围形成精确grant | 待实施 | 实际入口分析及已验证的基础 |
| 当前固定Forward的实数语义边界 | Blocked at decision（分析阶段） | 只读调查/失败复现，无新语义代码grant | 已保留静态路径、最小拒绝及恢复条件 | real-boundary.md；IsNaN恢复无交点行为不能由现有实数编码表达 |

后续共享函数/default/out/inout、矩阵/数组已在planning/shared-functions闭合；固定uint循环的四新正式控制已通过，完整57及最终Q进行中。这些普通材质能力不等于完整Forward已接入；本表“其余”指Frag-out入口、只读资源、尚未覆盖的循环/数学及外部位载体等缺口。当前固定配置还需要先解决[实数边界与恢复条件](real-boundary.md)中的目标选择，不能直接将IsNaN改为false或增设隐藏输入假设。

入口分析已完成索引/CLI/来源SHA、14新增回归/116项全部Python回归、固定Forward实际报告、独立Q三项修复和最终通过、当前文档/精简证据及本地命名提交。该阶段核心Lean基线91文件哈希一致，未重复当时未变的27控制。之后用户明确要求补齐能力并澄清float位载体边界，整数打包另有精确计划、授权及实施状态；不借入口分析旧grant修改数学语义。完整Forward尚未生成Lean或证明。
