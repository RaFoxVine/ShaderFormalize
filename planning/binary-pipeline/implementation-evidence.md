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
- 用两个由cases/rfl证明的通用返回选择引理避免展开整数表达式，session51513中helper-return实际IEEE_PROVED；该脚本未能完成float-branches的有限向量选择目标。因此浮点例采用其此前实际通过的原脚本，逐字保存为FloatControlProof.lean。positive-current.json核对三份当前HLSL/证明字节均对应实际通过报告；它不将失败运行改写为成功。
- 完整门禁队列session29447已启动：artifacts/binary-control/run_final.py，串行默认verify_demo.py（83核心及所有Python单元）→IEEE suite27→原型19，进度/心跳artifacts/binary-control/final1/result.json，完整日志final1/{core,ieee,prototype}.log。此队列尚未完成，不能提前报全部通过。
- 独立Q源码阶段已核对共享骨架、动态分派、IEEE MRO/零值/预检查、metadata/只读/初始化、三组3×3真实HLSL及完整目标，无需修改的源码缺陷；最终Q仍等本轮完整正式证据。
