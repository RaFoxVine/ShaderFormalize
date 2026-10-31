# 当前执行授权

## shader-binary-data-compute-2026-10-31 限定委托

- source: direct_user delegation，精确回答“按此范围执行 Overnight”。
- envelope: overnight-proposal-2026-10-31.md，SHA256为3511fdce37d81babb7dbe671577540cad3ac9127482c2794b5e18114160be19e；完整问题、范围与项目清单见overnight-request-2026-10-31.txt和overnight-items-2026-10-31.json。
- A沿用binary-control-grant-002；B/C是PLAN_AND_CODE上限，每个具体切片完成独立P、记录精确grant与Approved状态后才修改代码。D仅PLAN_ONLY。
- session: planning/overnight/current.md，由Smart脚本维护；沿用已有planning项目根，不创建新Project。
- 共用checkout保持一个产品/Lean workspace writer；允许并行只读调查和独立审阅。依赖、全局配置、默认入口、Unity/C++、合并及节点归档不在委托内；非强制push沿用既有授权。

## binary-control-grant-002

- status: active
- source: direct_user
- node_frame: delta.md与control-design.md修订1，检查点6f460a4d8dc89e8ba1afa358a321bb0bef8c47d5
- target_slices: binary-control-002@r1（二进制分支与局部赋值）
- authorization_message_exact: 按此实施
- unique_referent_evidence: 用户回复唯一待批异步问题，明确列出纯if/else、嵌套分支、main/helper提前return、struct汇合及八种uint复合赋值、公共分支骨架、三组HLSL及完整旧核心/IEEE验收。
- allowed_actions: 方案内共享骨架与IEEE源码、测试/实际DXC及Lean验证、兼容检查、文档和证据、独立Q、提交；沿用既有非强制push授权。
- exclusions: 切换默认执行语义、循环/资源/Compute功能扩张、数值cast、依赖或全局环境更新、Unity/C++、整体节点归档。
- stop_conditions: 新profile/IR、公理或弱化目标/审计，无法保持旧效果/返回语义，或须扩张未批准能力；旧目标差异先诊断说明，不能静默降低兼容保证。
- acceptance_boundary: 完整门禁、旧目标比较及独立Q后交付，仅完成本片。
- delegated_session: none
- recorded_at_local_date: 2026-10-31 America/Tijuana

## binary-bits-grant-001

- status: completed
- source: direct_user
- node_frame: delta.md与design.md修订1，检查点b7f6762734fed1dda4e0102a45f15ff22b5d5cd2
- target_slices: binary-bits-001@r1（二进制标量位运算接入）
- authorization_message_exact: 按此实施首批
- unique_referent_evidence: 用户回复的异步问题完整列出uint32环/位运算/低5位移位/比较三元/hex、打包/hash/位往返全称证明、现有绑定审计、依赖与Unity不变及旧实数主入口暂不切换；只有这一首片在等待批准。
- authorization_basis: 用户先要求开始二进制，独立实施前审阅通过后明确批准具体首片；不把旧方向确认冒称此前已有代码grant。
- allowed_actions: 计划内源码与测试、真实DXC/Lean验证、证据和能力说明更新、独立实施审阅、提交；沿用本仓库既有非强制push授权。
- exclusions: 修改依赖或全局环境、Unity/C++、完整HDRP、未就绪的规格/计算图/Compute或默认实数入口迁移；不声称本片完成全局二进制切换。
- stop_conditions: 新数值profile、新公理、弱化完整存储位相等、布局或错误政策变化，或目标超出本首片。
- acceptance_boundary: 实测与独立实施审阅、真实证据后报告；未执行其它切片，不归档整个节点。
- delegated_session: none
- recorded_at_local: 2026-10-31T07:16:56.942500-07:00
- completion_evidence: planning/evidence/binary-bits-2026-10-31.json；全门禁及独立Q通过，功能提交1f7c57a7dd6c1bb220de9c61ed9e1b058f665eb9已非强制推送并核对远程精确SHA。只完成本首片，不授权或归档其余迁移切片。
