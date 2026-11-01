# 当前执行授权

## shader-binary-data-compute-2026-10-31 限定委托

- source: direct_user delegation，精确回答“按此范围执行 Overnight”。
- envelope: overnight-proposal-2026-10-31.md，SHA256为3511fdce37d81babb7dbe671577540cad3ac9127482c2794b5e18114160be19e；完整问题、范围与项目清单见overnight-request-2026-10-31.txt和overnight-items-2026-10-31.json。
- A沿用binary-control-grant-002；B/C是PLAN_AND_CODE上限，每个具体切片完成独立P、记录精确grant与Approved状态后才修改代码。D仅PLAN_ONLY。
- session: planning/overnight/current.md，由Smart脚本维护；沿用已有planning项目根，不创建新Project。
- 共用checkout保持一个产品/Lean workspace writer；允许并行只读调查和独立审阅。依赖、全局配置、默认入口、Unity/C++、合并及节点归档不在委托内；非强制push沿用既有授权。

## binary-compute-grant-004

- status: completed
- source: delegated_session
- authorization_message_exact: 按此范围执行 Overnight
- delegated_session: shader-binary-data-compute-2026-10-31，item C，PLAN_AND_CODE；planning/overnight/current.md仍running，seal hash为2ad97543e86f3d582cbf38ba23414e24ed37b0bccb8292c9eba3c55482aedcce，脚本实际核对hash_valid=true。
- envelope: overnight-proposal-2026-10-31.md，固定SHA256为3511fdce37d81babb7dbe671577540cad3ac9127482c2794b5e18114160be19e；目标、动作、消费者均在C委托内。
- node_frame: delta.md及compute-uint-design.md修订2；当前具体规划/依赖检查点30d67525fa588bc47594e0641f1a066bd0ab5f0d。
- target_slices: binary-compute-004@r2（一维uint Buffer单pass Compute、完整内存等价与bounds/WW/WR安全）。
- readiness_evidence: 独立P第2轮PASS，复核检查点58658d9813e54b95ba2d12d69beac46ab1be4b42，结果归属P1已通过每次调用独占run目录政策关闭；DXC纯uint实际规划探针exit0。A/B均完整验收及独立Q通过；B完成30d6752已推送且ls-remote精确匹配。root实际准备83核心+35IEEE共118旧目标于artifacts/binary-compute/before/result.json，状态SNAPSHOT_COMPLETE；writer已静止。
- self_review: 已核对r2真实B接口、公共解释器/泛型内存/共享engine职责、consumer与每调用结果归属、完整安全及内存目标、正负oracle、旧入口迁移和受保护边界；没有未决产品选择或适用停止条件。
- allowed_actions: 方案内Program默认保持构造hook、IEEE默认保持operand hook、专用scalar uint/bool资源前端与复用emitter、泛型memory提取及原名称export、公共prepare/check backend化及显式uint生命周期、schema3严格契约、独立namespaced候选、真实HLSL/proof/单元/完整回归、独立Q、自主合同内修复、文档与证据、命名提交及既有非强制push。
- exclusions: float值/资源、数值cast、一般向量/数组/循环或资源helper、groupshared/barrier/atomics/跨线程通信、多pass/规格代码、依赖与全局配置、C盘worktree、Unity/C++、默认入口切换、force push、merge和节点归档。
- stop_conditions: 新profile/公理，弱化bounds/WW/WR/完整内存或任务绑定，超出envelope，owner保护/终态合同漂移，不可用关键oracle或第三轮审阅仍有关键遗留；普通编译/测试/证明及合同内缺陷自主修复。
- acceptance_boundary: hash/packing与alias真实正例；错误计算/Store越界/WW/alias WR到SubmittedProof真实失败；非冗余短路/三元安全正例；每run结果归属与旧成功拒绝控制；118旧目标/状态逐项比较、全部Python/83核心/35IEEE/实数回切/原型19及新uint控制、独立Q与真实证据后仅完成本片。D仍PLAN_ONLY，整体二进制迁移未闭合。
- recorded_at_local_date: 2026-10-31 America/Tijuana
- completion_evidence: planning/evidence/binary-compute-2026-10-31.json；产品25ff191、验收证据检查点4c9e8b1，完整五阶段实际通过。347全单元/83核心、37专项单元/35IEEE控制及实数回切、原型19、新uint16控制（6正例/10负例）均符合预期；118旧目标/状态及232生成快照一致。独立Q第3轮PASS、issues=[]，只读核实2438项hash。只完成本片，不授予D代码或整体二进制迁移完成状态。

## binary-data-grant-003

- status: completed
- source: derived_session
- authorizing_message_exact: 按此范围执行 Overnight
- parent_session: planning/overnight/current.md，shader-binary-data-compute-2026-10-31，running；seal hash为2ad97543e86f3d582cbf38ba23414e24ed37b0bccb8292c9eba3c55482aedcce，脚本实际核对hash_valid=true。
- envelope: overnight-proposal-2026-10-31.md，固定SHA256为3511fdce37d81babb7dbe671577540cad3ac9127482c2794b5e18114160be19e；B为PLAN_AND_CODE，未超过上限。
- node_frame: delta.md与data-design.md修订1，精确检查点e701125897c16bc051d8f84ca3fbf2789003af86。
- target_slices: binary-data-003@r1（uint向量、局部定长数组与固定循环，单Slice两实施阶段）。
- readiness_evidence: 独立P第1轮PASS、无阻断；实际DXC向量/数组循环探针exit0；A完整验收与独立Q第2轮通过，完成记录e701125已推送并核对远程精确SHA；迁移前83核心+27IEEE共110项prepare目标/状态已实际保存artifacts/binary-data/before/result.json。
- allowed_actions: 方案内公共类型/普通值/地址/数组/静态循环提取、IEEE frontend/emitter接入、四组实际HLSL正负例与Lean证明、针对性及完整验收、独立Q、自主合同内修复、文档与证据、命名提交和既有非强制push。
- exclusions: 动态/符号循环、break/continue/循环内提前return、资源或Compute扩张、矩阵、数值cast、bool向量、uint stage/cbuffer、依赖或全局配置、C盘worktree、Unity/C++、默认入口切换、merge或节点归档。
- stop_conditions: 新profile/执行IR语义或公理、弱化初始化/边界/绑定、超出envelope、不可用关键oracle或第三轮审阅仍有关键遗留；普通编译/测试/证明失败自主修复。
- acceptance_boundary: 四组全称完整输出位正例与实际SubmittedProof负控、全部Python/IEEE扩展suite/原型19/完整核心83、110旧目标/状态比较、独立Q与真实机器证据后完成本片，不提前授权C/D代码。
- recorded_at_local_date: 2026-10-31 America/Tijuana
- completion_evidence: planning/evidence/binary-data-2026-10-31.json；327全单元/83核心、37专项单元/35IEEE控制、实数回切、原型19及110旧目标比较全部通过，独立Q第2轮PASS、issues=[]。产品检查点fcb2cce，最终证据检查点c0af8ad；只完成本片，C仍需单独派生精确grant。

## binary-control-grant-002

- status: completed
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
- completion_evidence: planning/evidence/binary-control-2026-10-31.json；319全单元/83核心、29IEEE单元/27控制、实数回切及原型19全部实际通过，独立Q第2轮PASS、issues=[]。功能检查点64a6d7e及b6f4fb8已推送；仅完成本片，Overnight其它项目继续按限定委托推进。

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
