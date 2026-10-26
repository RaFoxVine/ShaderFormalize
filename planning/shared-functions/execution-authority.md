# Grant function-entry-001

- status: completed
- source: delegated_session
- node_frame: planning/shared-functions/plan.md修订1，完整字段与实际执行分离Ready切片，独立P第一轮通过。
- target_slices: 修复ControlProgram的frame/guard/branch/return/invoke及必要测试/证明/文档，保留现有完整字段、实际执行域和失败保证。
- authorization_message_exact: “接下来我们要执行 overnight 了”；“OK，继续吧。反正我们是需要把它跑通的，把它跑通吧，补齐暂时还没有的能力。”
- unique_referent_evidence: sealed language条目覆盖通用函数扩展；本项是已证实违反原完整输入函数约定的前置缺陷修复，非任意模型变化；用户持续免重复完整方案人工审阅。
- authorization_basis: 当前running Session的PLAN_AND_CODE language ceiling内，经Ready规划与独立P派生。
- recorded_at_local: 2026-10-26
- allowed_actions: 本切片核心修复、真实DXC有限回归、三项新增形式正负控制及完整核心验收、独立Q、当前文档/证据、本地提交。
- exclusions: Outlined新后端实现、新公理、依赖升级、浮点编码、隐藏输入假设、改变Ops上下文语义、Unity写入、push（由publish统一）、merge/archive。
- stop_conditions: 需要放宽未知语义策略或改变定义域/上下文保证；无法执行关键oracle；独立Q三轮仍有关键问题。
- acceptance_boundary: 独立Q及任意共享Ops的helper内联正例/实际域正负控制与完整回归；后续language切片仍继续，不以本项冒充全B目标。
- delegated_session: planning/overnight/current.md；shader-forward-2026-10-26；item language；envelope sha256 afcc1f80b2eb30be69411cd4633dc9d8ac79b0b918eaaf4302fc76ae66188206；frame rev1/P1 passed。
- state_reason: P1 Ready、Q2 Verified；132回归/35控制通过，证据封存于planning/evidence/function-frame-2026-10-26.json。
- superseded_by: none

## Grant shared-definition-001@revision-2

- status: completed
- source: delegated_session
- node_frame: shared-definitions-plan.md修订2，独立P2 Ready；前置function-entry-001已于71f307f以Q2/132回归/35控制闭合。
- target_slices: 显式shared后端/schema6、共享typed helper定义/调用事件、全字段与实际域/裁剪组合、有限求值器/CLI/模型分派、组合正反例/扩张规模检查、现有全回归、独立Q、文档/证据/本地提交。
- delegated_session: planning/overnight/current.md；shader-forward-2026-10-26；item language；sealed sha256 afcc1f80b2eb30be69411cd4633dc9d8ac79b0b918eaaf4302fc76ae66188206。
- authorization_message_exact: “接下来我们要执行 overnight 了”；“补齐暂时还没有的能力”；持续免反复完整人工方案审阅。
- allowed_actions: 当前Ready切片产品/测试/证明/文档修改与本地提交；保留默认后端和旧证明。
- exclusions: 默认参数/out/inout/矩阵/数组/循环新语法（后续单独Ready）；新公理/隐藏域假设/浮点位编码/Unity写入/新依赖/push/merge/archive。
- stop_conditions: 实际需要改变完整字段/实际执行域或共享Ops保证；关键oracle不可用且无等价；Q三轮仍有关键问题。
- acceptance_boundary: 计划的正式正负控制、旧全部控制、真实DXC规模对照及独立Q；不代表language总目标完成。
- recorded_at_local: 2026-10-26
- result: b074163（含2fc87bb/5961f8e）完成共享后端；独立P2 Ready、最终Q Verified；146最终单元与41控制全部符合预期，证据见../evidence/shared-functions-2026-10-26.json。后续copyback仍须另派生grant。

## Grant copyback-001@revision-2

- status: completed
- source: delegated_session；sealed running overnight language条目。
- frame: copyback-plan.md修订2，独立P2 Ready；前置shared-definition已于4cfa77a以146单元/41控制/最终Q闭合并推送。
- target: 显式shared下默认参数与out/inout复制进出、每个正常返回的完整输出、静态地址重叠/兄弟读写检查、if/三元/短路状态合并、普通/默认调用图的裁剪/terminal discard传播、纯void/out组合、outputs模型/发射/有限求值/引用检查、组合正反例/回归/当前说明/独立Q/本地提交。
- authority: 用户“补齐暂时还没有的能力”及overnight委派、持续免反复完整人工方案审阅；session shader-forward-2026-10-26，sealed sha256 afcc1f80b2eb30be69411cd4633dc9d8ac79b0b918eaaf4302fc76ae66188206；item language。
- allowed: 计划列出的核心/测试/证明/文档修改与本地提交；新语法仅shared，auto旧保证保留。
- exclusions: aggregate/向量swizzle输出地址、循环、新入口/外部写入/并发、浮点编码/新公理/隐藏域前提、新依赖/Unity改动/push/merge/archive。
- stop: 需要修改完整字段/实际执行/输入域保证、对有顺序依赖的表达式任意选次序、关键oracle不可用或Q三轮仍有关键问题。
- acceptance: 真实DXC组合与范围/别名/未初始化负例；正常材质与导数完整场正例及错误数值/实际非法域负例；旧全部控制和新增控制的统一runner、独立Q、证据及本地提交。不以本片冒充全部language或Forward。
- recorded_at: 2026-10-26；依赖已闭合，具体代码实施权在此派生，不凭前置grant。
- result: 64992ea，19新/165全单元及47控制全部符合预期，21 PROVED/24 UNPROVED/2 INVALID_INPUT；独立Q2最终Verified，含额度中断恢复后的全21正例目标/哈希/公理与两新负例复核。独立Windows副本三正例及事实审阅通过。见../evidence/copyback-2026-10-26.json。

## Grant aggregate-001@revision-1

- status: completed
- source: running sealed overnight language条目PLAN_AND_CODE内派生；用户持续免重复人工方案审阅，2026-10-26重置额度后明确“接下来继续工作”。
- frame: aggregate-plan.md修订1，独立P1 Ready；前置copyback已由64992ea、165单元/47控制/Q2及独立Windows追加验证闭合。
- target: shared/schema6的float矩阵与固定数组、统一typed元素地址、静态/动态读写和copy-out、逐叶初始化、矩阵运算/mul/transpose/零转换、复合float uniform布局与范围组、bounded_index域结论及发射/有限/模型消费者、真实组合正负例、全部回归、独立Q、当前文档和本地提交。
- authority: shader-forward-2026-10-26；planning/overnight/current.md；item language；sealed sha256 afcc1f80b2eb30be69411cd4633dc9d8ac79b0b918eaaf4302fc76ae66188206；旧P覆盖本修订且中断前后无产品或合同漂移。
- allowed: 当前Ready计划列明的核心/测试/手写证明/文档/证据变更、真实本地验证和提交；旧auto保持。
- exclusions: 循环（下一片单独grant）、新stage/uint或bool uniform、浮点编码/新公理/隐藏域前提、外部写入/并发、新依赖/Unity写入、push/merge/archive。
- stop: 需改变实数/完整字段/实际域/接口布局保证、接受未定序读写、关键oracle不可用或三轮Q仍有关键问题。
- acceptance: 计划至少六正式控制（正常材质/错误系数/完整场导数/合法与实际越界/非实际越界），全部旧47控制和真实DXC回归、旧生成文字不变、独立Q/目标绑定及公理审计/文档/证据。不以本片代表循环或完整Forward完成。
- recorded_at: 2026-10-26；代码权限须随Approved状态先提交，再写产品代码。


- result: 9bec4aa完整190单元/53控制PASSED，25 PROVED/26 UNPROVED/2 INVALID_INPUT；独立Q2最终Verified，全部产物冻结acceptance53；精简证据../evidence/aggregate-2026-10-26.json。同锁独立Windows三正例及事实核验通过。

## Grant loop-001@revision-2

- status: completed
- phase: completed; isolated and conditional main implementation both verified.
- source: sealed running overnight language条目PLAN_AND_CODE内派生；持续免重复人工方案审阅及用户“接下来继续工作”。
- frame: loop-plan.md修订2，独立P2 Ready；数学语义与P1相同，静态uint for精确次数、不截断，最终四控制及全旧回归/Q不变。
- baseline: 9bec4aa有25新单元/六正式控制/Q2源码审读，完整190单元通过，主53控制进行中、完整Q尚待。不得称aggregate已Completed。
- current_target: 仅D:/2FileBuildWorkPlace/Formalize/ShaderFormalize/artifacts/loop-development独立Git clone，从9bec4aa创建。root唯一writer；创建前核对绝对路径在仓库指定artifacts内、目标不存在。
- current_allowed: 副本中的计划循环代码/测试/组合示例/手写证明/文档草稿与本地提交；.tools junction只读复用主仓库锁定工具，明确不称独立依赖安装；只运行经检查不含CLI的test_loops新集、DXC/有限oracle和内存Lean生成。主目录只更新规划/授权/证据。
- current_forbidden: 主目录产品/生成文件改动；副本bootstrap、Lean/Lake build、prepare/check、完整runner、共享proof/.lake/包构建目录写入；新依赖/全局配置/Unity/浮点编码/新公理/隐含fuel或输入前提；push/merge/rebase/archive。
- conditional_integration: 仅aggregate默认53和最终Q全部通过、基线接口无合同漂移且主产品差异已核对后，在本authority/tasks先记录条件满足，才可将副本确切循环patch应用至主目录，实施本计划剩余正式四控制/全回归/Q/说明/本地提交。禁止覆盖用户变更，禁止把隔离单元当最终形式验收。
- stop: 基线语义变化、主完整gate/Q未通过时停止整合；实数/完整字段/实际域/终止或源支持合同漂移、关键oracle不可用或第三轮关键问题未闭合时停止受影响工作并重新规划。
- session: shader-forward-2026-10-26；planning/overnight/current.md；language；sealed sha256 afcc1f80b2eb30be69411cd4633dc9d8ac79b0b918eaaf4302fc76ae66188206。
- recorded_at: 2026-10-26；P2 Ready后派生，随隔离Approved状态先提交，clone和代码随后。

- integration_condition_satisfied: 2026-10-26；aggregate190/53及Q2最终通过，主tools/proof/examples/依赖锁相对9bec4aa无差异，基线职责和接口无漂移。副本5025b6a的确切22文件patch已git apply --check通过，SHA256 4633cc4e75e5f3904c72f9104b15db8aac2d813ca4184f33a70c8df384cf1f0b。允许按原P2合同将patch应用至主目录并实际运行四新控制/完整57控制及全部回归、Q2、当前说明/本地提交；不merge/rebase，不覆盖已有HDRP调查文档修正。

- result: d348566完整213单元/57控制PASSED（27 PROVED/28 UNPROVED/2 INVALID_INPUT），独立Q2最终Verified；四新控制含真实组合材质与零次域正例、错误系数与实际非法域负例。旧25目标逐字兼容，独立Windows最新源码两正例及事实核验通过；见../evidence/static-loops-2026-10-26.json。只支持约定静态uint for，不宣称全部循环或完整Forward。
