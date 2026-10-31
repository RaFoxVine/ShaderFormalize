# 二进制首片实施与实测记录

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
- 首次直接GitHub fetch及HTTP/1.1重试连接重置；读取系统既有代理后，使用单次git -c http.proxy=http://127.0.0.1:10808成功ls-remote/fetch，远程仍9b68e9d，没有改全局Git或系统配置。最终推送仍待回归和Q完成。
