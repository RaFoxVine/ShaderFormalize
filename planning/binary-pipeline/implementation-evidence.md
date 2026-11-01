# 二进制迁移实施与实测记录

## binary-bits-001

基线9b68e9d；规划检查点b7f6762，精确grant提交1e7cfe6，用户回复“按此实施首批”。root为唯一writer，使用D盘主目录和既有本地4.35，不创建C盘worktree、不改依赖或Unity。

- 独立实施前审阅通过后，固定DXC动态shift探针实际编译成功，左右移均先and i32 count,31，证据artifacts/binary-pipeline/shift-probe。Lean4.35 UInt32.shiftLeft/Right定义也显式模32。
- 首次针对性Python回归22项实际通过（10.550秒），日志artifacts/binary-pipeline/units-initial.log。后续删去一个无必要的字符串断言，并按独立审阅增加直接float/uint数值cast和混合运算拒绝子例；最终全回归尚待执行，不能用首次22项冒称最终源码已验证。
- 初始四字段pack的SAT位向量证明在Lean编译成功，但完整公理审计实际拒绝：proof含bv_decide默认产生的_native.bv_decide.ax_*。失败输入、提交证明、目标和审计日志完整保留artifacts/binary-pipeline/packing-initial。固定Lean源码Lean/Meta/Tactic/BVDecide/Prover/Bitblast.lean使用nativeEqTrue，是这项额外依赖的来源；没有放宽审计或把额外公理加入白名单。
- Pack证明改为32位逐bit引理，使用UInt32→BitVec等式及核心移位/掩码定理。实际check exit0、IEEE_PROVED，最终目标只依赖propext/Classical.choice/Quot.sound，证据artifacts/binary-pipeline/packing-kernel。Model同时编译通过任意UInt32的asuint(asfloat(u))=u逆定理。
- 其余五个新正例由root串行运行，session65785已exit0，汇总artifacts/binary-pipeline/positive-smoke/result.json为PASSED；hash/shift/wrap/unsigned/roundtrip均为IEEE_PROVED，各自最终公理均只有原三项。日志artifacts/binary-pipeline/positive-smoke-command.log。wrap证明另含13项内核归约边界断言。
- 最终全Python回归312项实际通过（61.612秒），日志artifacts/binary-pipeline/all-units-final.log；IEEE suite自身22项单元再次通过（10.294秒）。session83680串行最终exit0，正式21控制（9 IEEE_PROVED、12 UNPROVED）及默认实数回切全部通过，IEEE suite耗时2465.953秒；19项原型检查通过，耗时31.656秒。阶段记录artifacts/binary-pipeline/final-validation.json，持久机器证据planning/evidence/binary-bits-2026-10-31.json。
- 对基线9b68e9d的122个受保护实数/Compute、公共工具、证明和依赖配置路径执行git diff --quiet，均未改变；完整当前源SHA256保存在artifacts/binary-pipeline/protected-sources.json。没有用此指纹核对冒称本批重跑旧83项长门禁。
- 独立实施审阅Q最终通过，无阻塞、issues=[]。reviewer为/root/binary_pipeline_frame_review，只读独立核对21正式报告与全部当前HLSL/SubmittedProof快照、9正例目标/Model/验证日志/源指纹、10个validated_sources和122保护路径，并实际执行对基线git diff --quiet；确认完整目标、原三公理、312/22单元、原型19和实数回切证据一致，没有运行Lean或修改文件。收尾仅更新状态和交付记录。
- 正式新负控中，packing-wrong在SubmittedProof留下input.z的bit7目标；hash-wrong在SubmittedProof的rfl达到maximum recursion depth。两者均为UNPROVED且符合控制合同，不能把后者描述为工具已经证明两函数不等价。最终机器证据保存负例真实错误行与日志哈希。
- 首次直接GitHub fetch及HTTP/1.1重试连接重置；读取系统既有代理后，使用单次git -c http.proxy=http://127.0.0.1:10808成功ls-remote/fetch，远程当时仍9b68e9d，没有改全局Git或系统配置。
- 功能提交1f7c57a7dd6c1bb220de9c61ed9e1b058f665eb9已非强制push至origin/codex/shader-equivalence-planning；随后ls-remote精确匹配该SHA，工作区干净。收尾仅将本片状态与grant标为Completed并记录交付；其它切片保留原规划状态，未归档整体节点，未开始整体实数/Compute迁移。

## binary-control-002

- 用户明确回复“按此实施”，绑定control-design.md修订1及6f460a4d8dc89e8ba1afa358a321bb0bef8c47d5；grant与Approved状态先提交11f280383aa22fab87711c01ba5b1ef5a80f3e32，再修改产品源。root唯一writer，继续使用D盘主目录和原依赖。
- 用实际DXC prepare保存全部83核心和21旧IEEE案例的基线与提取后目标/状态；104项完全一致。原始命令及摘要位于artifacts/binary-control/snapshot_models.py、before/result.json、after/result.json；比较为ALL_TARGETS_AND_STATUSES_IDENTICAL，没有用旧83证明结果冒称本片已重跑完整正式验收。
- 已提取shader_flow.py，real ControlProgram保留表达式/效果；IEEE纯直线和guarded前端共享IeeeSemantics，语句钩子处理八种uint复合赋值。Program后端零值钩子只用于内部占位/返回汇合，局部未初始化值仍为None。
- 初步IEEE29项单元通过（11.634秒），全Python319项通过（53.678秒）。日志artifacts/binary-control/units-initial.log及units-all-initial.log。
- 三个新正例初次串行check为session49207：float-branches通过，branch-record留下布尔汇合目标，helper-return在无用simp步骤失败。原始记录artifacts/binary-control/initial-validation.json保留。
- 第二次session94748：RecordControlProof逐项划分两个bool，branch-record实际IEEE_PROVED；helper-return的自动展开达到200000 heartbeats，float-branches用修订脚本实际IEEE_PROVED。证据positive-repaired各目录保留，未改变生成目标或公理白名单。
- 用两个由cases/rfl证明的通用返回选择引理避免展开整数表达式，session51513中helper-return实际IEEE_PROVED；该脚本未能完成float-branches的有限向量选择目标。因此浮点例采用其此前实际通过的原脚本，逐字保存为FloatControlProof.lean。positive-checkpoint.json保存实现检查点三份HLSL/证明与实际通过报告的对应；它不将失败运行改写为成功，也不替代后续修订示例的复验。
- 完整门禁队列session29447已启动：artifacts/binary-control/run_final.py，串行默认verify_demo.py（83核心及所有Python单元）→IEEE suite27→原型19，进度/心跳artifacts/binary-control/final1/result.json，完整日志final1/{core,ieee,prototype}.log。此队列尚未完成，不能提前报全部通过。
- 独立Q源码阶段已核对共享骨架、动态分派、IEEE MRO/零值/预检查、metadata/只读/初始化、三组3×3真实HLSL及完整目标，无需修改的源码缺陷；最终Q仍等本轮完整正式证据。
- 实现检查点64a6d7e13896b6d8bee656a7570410f47786c8e3已推送，状态仍Implementing。核心完整门禁先运行319单元（49.655秒），然后运行83控制；139个编译器/证明/配置源的冻结指纹保存于frozen-sources.json。
- 复查发现helper-return的AND清bit0随后被OR设bit0抵消；改为AND清bit31、OR设bit0，三份示例同时修订。有限uint32参考计算为八种操作各找到一个省略该操作会改变输出的见证，保留compound-observability.json；这不是替代HLSL全称证明。影响的示例导入单项实际复测通过（0.462秒），未改共享源或核心83的输入。此前helper正例只适用于修订前数据；最终IEEE29单元/27控制将验证当前修订，记录fixture-revision.json明确区分这次修订与核心全单元运行时间。
- 最终队列session29447实际exit0，开始10:30:09、结束13:28:57（2026-10-31 America/Tijuana）。默认完整核心耗时5959.422秒：319单元及83控制，38 PROVED、43 UNPROVED、2 INVALID_INPUT均符合预期；IEEE suite耗时4693.234秒：29单元、27控制（12 IEEE_PROVED、15 UNPROVED）及实数回切均通过；原型19耗时80.235秒通过。没有复用旧83项证明结果来冒称实际重跑。
- 最终IEEE中的helper-return正负例使用b6f4fb8修订后的三份HLSL；正例实际IEEE_PROVED。最终专项29单元再次覆盖当前示例，区分先前319全单元运行时的数据版本。builder实际核对139冻结源、全部当前输入/提交证明/生成目标/语义Model及三公理白名单，生成planning/evidence/binary-control-2026-10-31.json，当前状态VALIDATION_PASSED_REVIEW_PENDING。
- 独立Q第2轮实际PASS、issues=[]，reviewer为/root/binary_control_plan_review。只读核对139冻结源、104旧目标比较、83/27逐案报告、27组当前输入/快照/提交证明和12正例的96个产物哈希；确认三个新负例在SubmittedProof留下真实未解决目标。reviewer明确纠正Q1过早认可操作可观察性的判断：最终b6高位AND掩码2147483647已经实际出现在helper目标并完成全称证明。未运行Lean/Lake/测试或改文件。机器证据据此收为PASSED，002与grant完成；B/C/D不包含在本次验收结论内。
- A完成证据提交e701125897c16bc051d8f84ca3fbf2789003af86已非强制推送，ls-remote精确匹配，工作区当时干净。随后才派生B具体grant。

## binary-data-003

- 用户限定委托来自“按此范围执行 Overnight”，session shader-binary-data-compute-2026-10-31处于running且seal hash有效；data-design.md修订1经独立P第1轮PASS，实际DXC规划探针可解析，A依赖完成。grant与Approved状态先提交13ea195f25658a9f9d11d073e90a8f56f914f06f，再开始产品修改。
- 迁移前baseline由实际DXC prepare重新保存83核心和27IEEE共110项，artifacts/binary-data/before/result.json为SNAPSHOT_COMPLETE。脚本snapshot_models.py保存在同目录；没有覆盖A的104项历史比较。A/B源码写入和Lean workspace不并发。
- 产品writer交由/root/binary_data_plan，root仅维护规划/证据及只读调查。实现检查点eae9ff9已显式提交31个负责文件、未push；root的planning改动保持未提交。初步targeted-05串行通过IEEE36、aggregate25、loops23。formal-01四个新正例均IEEE_PROVED；vector-pack补入uint3位往返后在formal-02正例也通过，以上只是初测而非最终门禁。
- 初测targeted-02发生作者将完整IEEE单元与正式proof并行导致写锁冲突，失败记录保留，随后所有锁使用者改为串行；targeted-04新增helper-loop测试暴露frame元数据硬依赖real helper_indices，已提为后端loop_frame_name钩子，targeted-05复测通过。这些没有重写成一次无失败运行。
- 独立Q1源码阶段发现两项P2，root核实并安排作者合同内修复：新data层float_compound忽略计算类型/别名metadata，需统一回IEEE语义校验；vector-pack.optimized仍复用Packet/向量helper及uint3位往返，需换成真正标量参照并重验正负。旧有效float复合赋值原本受支持，不通过删功能解决。当前源码Q尚未通过，完整83/IEEE35/原型19及110 after比较也未执行。
- Q1修复检查点fcb2cce8cfafa37a2e1d8b37486dc2423a146d4f已显式提交：compound统一由IeeeSemantics核验所有计算类型/别名，vector-pack改为独立scalar参照，原版补uint2/uint3双向位往返。targeted-06串行IEEE37/aggregate25/loops23通过；formal-03修订后pack为IEEE_PROVED，wrong成功生成目标后在SubmittedProof第一lane留下xor1差异。另三正例formal-01通过、三wrong在formal-02均SubmittedProof失败。旧pack记录为修订前历史，不冒称当前源码结果。
- 作者已明确交回产品与Lean writer，无活跃检查；root接回后才冻结当前源码并启动最终串行队列。Q1后修订尚待最终Q2独立覆盖，当前不能标本片Completed。
- root唯一writer的最终队列为exec session30543，脚本artifacts/binary-data/run_final.py，心跳与阶段记录final1/result.json，日志final1/{compatibility,core,ieee,prototype}.log。源码检查点fcb2cce的146源及186个example输入/契约已冻结于frozen-sources.json；先after prepare比较110旧目标（已exit0、逐项一致），再默认verify_demo.py（327全单元已通过，83核心仍在运行）、完整IEEE35/专项37/实数回切、原型19。后续恢复先核对该队列/心跳与writer静止，不能并行开第二套Lean或提前修改冻结产品源。
- Q2已完成只读源码核对：Q1两项P2实质关闭，未发现新增源码阻断；reviewer独立核对146冻结源hash，formal-03当前输入/证明与真实正负结果对应。其最终PASS明确等待final1全部门禁和持久机器证据，没有把源码阶段结论当作本片验收。
- 最终session30543实际exit0：110旧目标比较85.156秒；默认完整核心7441.687秒（327全单元、83控制：38 PROVED/43 UNPROVED/2 INVALID_INPUT）；IEEE专项4577.235秒（37单元、35控制：16 IEEE_PROVED/19 UNPROVED，含实数回切）；原型19耗时60.172秒。所有控制符合预期。builder核对146源、186输入与当前完整产物，写入planning/evidence/binary-data-2026-10-31.json，状态VALIDATION_PASSED_REVIEW_PENDING。汇总器首次遇到历史case-summary为JSON数组，保留原文件并补充数组汇总读取后成功，不修改或重跑产品结果。
- 独立Q第2轮最终PASS、issues=[]，reviewer为/root/binary_data_plan_review：独立核对146源/186输入、110旧目标及前后216份生成目标、83核心逐案与35IEEE当前源/快照/证明、16正例128个产物hash及原三公理，四个新wrong均在SubmittedProof真实失败；README/docs/coverage边界准确。机器证据收为PASSED，003/grant完成。没有重跑或改写历史失败；C不在本次验收内。
- C改动前旧目标快照由root在B完整门禁结束后实际保存：exec75597 exit0，artifacts/binary-compute/before/result.json为SNAPSHOT_COMPLETE，83核心+35IEEE共118项；不覆盖B历史证据，不修改产品源。

## Overnight D（PLAN_ONLY）

- /root/spec_graph_plan_review完成只读草案审查，未发现两项规格或两图scan的数学错误；不是最终Execution Ready独立P，未运行测试、prepare或Lean。root据此澄清任意P的信任边界，首批任务提供见证而一般接口不强制非空；继续具体化固定ABI、frame、单候选和expected task_id绑定。C真实接口、task_id规范及最终目标构造仍需在下次具体实施前冻结和独立P，未获得或实施D产品代码。

## binary-compute-004

- B完成提交30d67525fa588bc47594e0641f1a066bd0ab5f0d已非强制推送并与远程精确匹配，产品/Lean writer静止；C改动前118项实际目标已保存。r2独立P第2轮PASS，session running且seal有效，root核实不越过C委托上限后派生binary-compute-grant-004及Approved状态，命名提交先于任何C产品代码。
