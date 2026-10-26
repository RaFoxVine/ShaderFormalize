# 本批精确执行授权

来源是用户2026-10-26的并行推进指示及此前“先把东西跑通”、免重复完整方案审阅的持续指示。用户本轮明确修改外部依赖验收方式：信任工具/论文声明，简单接入检验通过后继续，不提前全面审计。以下是对该委派范围的具体落实；不借旧finished Session授权。

共同依据：parallel-plan.md修订1；新Session shader-expansion-parallel-2026-10-26（planning/overnight/current.md），封存SHA256 `6632ef1efc2581bfda4ef504b0335f90c939295bad955da7cd2db7c4dfe6c884`，当前running。独立P覆盖各精确切片；修订后的数学/Compute均由原审阅者第二轮针对核对通过。授权与Approved状态在产品代码写入前提交。

## Grant math-001@revision-1

- status: active；source: delegated_session；item: math。
- target: parallel-plan数学10项及所列前端/发射/求值/证明/正负控制；根agent负责公共runner/CLI消费者与主目录集成。
- current_target: C:/Users/xc/.codex/worktrees/basic-math/ShaderFormalize；该agent唯一代码writer；主目录仅根agent整合精确补丁。
- authorization_message_exact: “接下来我们可以开多个subagent进行同时推进。我认为你提出的上面四个推进方向都是有很多可以并行的内容的。”
- allowed: 具体切片代码/测试/实际DXC与Lean验证、证据、文档、整合和本地提交。
- exclusions: 默认数值语义变化、新隐含前提/公理、全局配置、Unity写入、merge/archive；不写其他agent文件或共享生成/构建目录。
- oracle: 代表材质与域/错误输出正式正负控制、旧目标兼容、最终默认全套及独立Q。
- stop: 需降低既有实数/实际执行域保证；Q第三轮关键问题未闭合。

## Grant ieee-001@revision-1

- status: completed；source: delegated_session；item: ieee。
- target: parallel-plan的prototypes/ieee固定FloatLib/Lean4.35独立工程、bootstrap/run及代表检查与现成定理使用。
- current_target: C:/Users/xc/.codex/worktrees/ieee-prototype/ShaderFormalize；独占该checkout的.tools/.cache/原型，不升级主4.24。
- authorization_message_exact: “他们声明他们能做，那么我们可以当他们能做，进行简单检验以后觉得没问题我们就可以拉过来”。
- allowed: 固定本地依赖下载/构建、原型源码/脚本/锁/例子、代表执行、独立Q、根agent整合源码/说明并本地提交。
- exclusions: 全局安装/设置、核心锁升级/默认PROVED含义变化、把完整上游审计作为前置、merge/archive。
- oracle: 实际构建、运算/特殊值/位解释/重结合代表检查、库定理实际实例化；不要求本轮独立重证外部库。
- stop: 空间不足且需删除用户数据；需要改核心默认配置；Q第三轮关键问题未闭合。
- result: 8372a6e，固定依赖2396项构建、19运行检查及两定理通过；主目录迁移后热跑成功，独立Q2 Verified；见../evidence/ieee-integration-2026-10-27.json。HLSL IEEE导入仍未实现。

## Grant compute-001@revision-1

- status: active；source: delegated_session；item: compute。
- target: parallel-plan的1D StructuredBuffer Compute AST→Lean、独立experimental命令、两输入两输出及负控；严格包含物理identity/线程内有序overlay/完整内存/范围与跨线程WW/WR安全目标。
- current_target: C:/Users/xc/.codex/worktrees/compute-load-store/ShaderFormalize；该agent唯一代码writer；独立生成目标/构建。
- authorization_message_exact: “我认为你提出的上面四个推进方向都是有很多可以并行的内容的。”
- allowed: 指定模块/测试/证明/例子/说明、真实DXC/Lean验证、独立Q、根整合和本地提交。
- exclusions: 修改默认ps路径、跨线程竞争任意顺序化、隐含无alias假设、宣称任意Compute或同步、全局配置、merge/archive。
- oracle: 正常后处理完整等价与安全目标实际PROVED；错算、越界、冲突/alias负例不能PROVED；独立Q。
- stop: 需要弱化完整状态或安全目标；Q第三轮关键问题未闭合。

## Grant synchronization-001@revision-1

- status: completed；source: delegated_session；item: synchronization。
- target: parallel-plan的本地VerCors2.4接入、带权限并行正例与具体失败负例，尝试GPU/barrier入口。
- current_target: D:/2FileBuildWorkPlace/Formalize/ShaderFormalize；根agent唯一writer；prototypes/synchronization及独立ignored工具/输出。
- authorization_message_exact: “不要为了后期的严格而在早期给自己增加奇怪的工作量，我认为我们还是先以大框架为主”。
- allowed: 固定本地release下载、进程级Java环境、原型runner/例子、实际外部验证、证据/说明、独立Q、本地提交。
- exclusions: 全局安装/设置、把外部PASS当Lean/HLSL自动导入证明、完整验证器审计前置、merge/archive。
- oracle: 外部工具真实运行并区分通过与权限/断言失败；未运行的GPU入口如实注明。
- stop: 需要全局安装；Q第三轮关键问题未闭合。
- result: c401924，实际4控制PASSED、独立Q1 Verified；见../evidence/vercors-integration-2026-10-27.json。无HLSL同步自动导入或Lean桥接声明。

## 发布与结束

根agent沿用用户“完成了工作以后，要记得git push一下”的持续指示，仅推送本批实际完成且检查过的项目源码/锁/文档，不发布工具缓存、Unity源码或未验证能力声明。完成后按真实结果结束新Session；正式H-X和Node归档未授权、不执行。
