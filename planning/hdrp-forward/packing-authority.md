# 整数打包精确执行授权

- status: completed
- source: direct_user
- node_frame: packing-plan.md修订1；独立P第一轮Ready，2026-10-26。
- target_slices: packing-tasks.md中的整数打包链路；不包括Outlined完整Forward扩展。
- authorization_message_exact: “OK，继续吧。反正我们是需要把它跑通的，把它跑通吧，补齐暂时还没有的能力。” 后续澄清：“对，是浮点数和延迟渲染”。
- unique_referent_evidence: 用户在固定Forward调查后要求实现缺口并明确整数打包与float位载体边界；此前明确完整方案免再次人工审阅，先跑通。
- authorization_basis: 沿用明确免重复方案人工审阅授权，独立P确认本精确实现范围Ready后持久化；不借用已经完成的入口分析Grant。
- recorded_at_local: 2026-10-26
- allowed_actions: 该切片核心代码/Lean模型/示例/证明/正负回归、当前文档及证据、独立Q、契约内修复、本地命名提交。
- exclusions: 完整IEEE浮点、隐藏定义域假设、新公理、依赖升级、全局配置、Unity写入、push/merge/归档、新TreeDive项目、Outlined切片实现。
- stop_conditions: 改变数学保证、需要浮点编码、无法执行关键oracle、超出精确切片范围。
- acceptance_boundary: 真实DXC→Lean正反例、完整核心回归与独立Q；完整Forward未完成必须明确说明，H-X/归档另行。
- delegated_session: none
- state_reason: 精确切片已实施，128回归/32正式控制通过，独立Q第二轮证据闭合，精简证据和命名提交完成；完整Forward不在本grant中。
- superseded_by: none
