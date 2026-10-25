# 纹理/裁剪/导数执行证据

授权规划提交780c448，基线04b26e8。DXC探针artifacts/fragment-investigation/probe.hlsl确认为VarDecl纹理、CXXMemberCallExpr采样、CallExpr clip/导数、四槽IfStmt含NULL、DiscardStmt以及void helper。独立P第一轮通过：数学边界、语句效果限制、events交错和有区分力的验收可行；特别要求全称E/共享Ops、资源模式身份、void局部返回和旧schema2兼容。由根agent唯一写入。

初验：既有65回归通过；新增13项DXC/有限全函数回归通过。新TexturedProof初验PROVED，build102.328s、独立verify26.359s，仅允许的三个公理。Fragment.Ops是定理任意参数，非新增axiom；输出函数含Option裁剪结果，uniform是常数，varying是完整函数。新语义文件加入lake roots；Lean finish用classical提供裁剪Prop的可判定实例，依赖版本未变。

Unity初验PASSED：24组参数、49152像素，独立CPU公式最大误差5.789122503596644e-8，keep23592/discard25560，恰好alpha-cutoff=0仍保留8604。UVCalibration仅检查同一wrapper插值的规则坐标网格，误差0；CPU纹理texel/点采样/导数footprint公式独立，controlled mip资产持久化，隐式/Grad的最大texel footprint=1保证mip0。五负例真实差异：裁剪mask8604、UVmask11652、错误导数颜色0.0043029、LOD颜色0.0270193、Samplermask9252。真实HDRP保存重载，左右10865/10899有色像素，对齐误差0，隐藏自有两球后污染0。源文件哈希匹配；预览人工查看为两颗有纹理透明裁剪的球。

已知边界：纹理/导数按共享任意操作建模，不证明GPU滤波或硬件导数实现；clip上下文序列保守保留，不证明跨裁剪/一般分支移动。一般bool局部/分支、其它采样重载和资源参数不在本轮。有限oracle不是数学证明；UNPROVED也不是不等价判定，实际有限反例另存。

独立Q和完整统一验收尚未完成，不把初验当最终结果。当前真实结果位于artifacts/textured/proof、artifacts/textured/unity；完整验收将由run_demo默认全部四例串行运行，18项证明控制。

独立Q第一轮报告一项P2：未调用递归函数仅被检查调用签名，递归防护在实际invoke中，故unused void/numeric递归可被接受，与既定不支持递归边界不一致。新增全函数调用图cycle检查（在全部语法检查后、实际展开前），保留动态depth防护；新增两种unused递归真实DXC回归。属于原约定的fail-closed修复，数学语义/示例/Unity未变。修复后全79项回归通过，独立Q第二轮检查该修复及最后统一证据。

发布字节一致性修正：PowerShell写入的两份正例仅末尾CRLF与其余LF混用，现于完整命令仍在旧例证明阶段、尚未读取新纹理正式输入之前统一末尾LF；.gitattributes本来要求*.hlsl LF，避免Git保存后与证据字节不同。无表达式或工具代码变化，重新执行新14项真实DXC回归通过。最终57源快照只更新这两个输入，另外55哈希不变。后续纹理正式证明及四例GPU将读取最终LF字节，最终证据检查其哈希；先前初验作为历史保留。

补充普通写法修复：实际DXC将texture.Sample(...).rgb等rvalue selector打印为type引号后的rgb，旧规则只识别lvalue的vectorcomponent rgb。新增共享component_mask只识别两种精确HLSLVectorElementExpr形式，静态/动态共用，非放宽未知节点。采样与导数在参数全部解释后立即写入一个SSA绑定，子操作在父操作前，context取当时效果数；这使支持嵌套采样后不会重复内联全函数表达式。新增rvalue采样/导数分量、未调用helper静态支持、10层嵌套线性大小和未消费opaque实参normalize域检查。实际82项总回归通过。

为避免混合版本，已核对并停止本轮完整runner PID17396及其子树（未碰VSCode Lean服务或Unity），旧日志保留fragment-full-before-rvalue-fix.log。此前已执行至纹理负例，不能当最终完整验收。57文件快照只更新上述4个修复/测试文件，另外53不变；将用最终LF输入和最终实现从头跑默认全套。独立Q第二轮正在覆盖受影响修订。

独立Q第二轮已确认上述受影响修订：17项fragment测试通过；额外真实DXC验证Sample(...).xyxy、ddx(Sample(...)).rgba、clip(Sample(...).a)后的Grad与导数上下文；40层嵌套生成41个绑定、两程序82次采样、13675字符Lean文本，线性发射。未调用递归问题已关闭，无新增阻断项。现已从头重新运行最终默认全套，代码冻结，等待最终证据复核。

## 最终完整验收

第二次最终默认命令已完整结束exit0，日志fragment-full.log末尾Demo passed。82项回归、18项证明控制、lerp/Unlit/structured/textured四套Unity全部通过。新纹理正例PROVED（build39.25s、verify24.156s），仅propext/Classical.choice/Quot.sound；五负例均UNPROVED且有独立具体/GPU反例，不以未证明单独断言不等价。

新GPU24组/49152像素，最大误差5.789122503596644e-8，kept23592/discarded25560，零边界保留8604，对齐图像0，场景隔离污染0；五种错误仍检出。新原版/改写版LF字节与正式proof/GPU哈希一致；57个最终源文件逐一匹配冻结快照。精简证据及实际预览已保存planning/evidence/textured-material-2026-10-25.json、textured-preview-2026-10-25.png。独立Q第二轮正在核对最后证据，当前只更新README/状态/证据元数据，不再改实现。

独立Q第二轮最终通过，无未关闭发现。复核者实际重算57冻结文件、正式生成模型/手写证明/语义模块哈希并核对所有原始JSON与精简证据；82/18控制、四Unity、最终LF源字节均一致。Q后只更新文档状态、授权结束和证据review字段；实现未再变化。git diff --check通过。用户资料/编辑器环境未清理或改动，实验与完整日志留在ignored artifacts；依赖版本及全局配置不变。本地提交交付，未push、未正式归档，等待用户体验与H-X。
