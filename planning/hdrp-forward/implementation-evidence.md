# Forward入口分析执行记录

基线c1de3d7，授权规划提交822f929。仅执行入口分析工具，不修改实数数学前端/Lean、不以可达剪枝绕过未知语义。继续Smart流程及Git审阅，不使用Lavish，不初始化TreeDive新项目。

独立P第一轮指出默认实参与全局初始化调用闭包未封闭、调用身份/状态/来源接口需明确。使用真实DXC的Seed默认参数、Global全局初始化探针确认调用点CXXDefaultArgExpr没有子树。修订2按callee/参数位置/完整prev链恢复默认式、将全部全局初始化设为保守根、保留重载身份并明确0/2/1退出码和旧成功覆盖；独立P第二轮通过后冻结精确grant进入实现。

实现dxc_ast_index.py与analyze_shader.py。分析只消费明示AST字节；未知潜在调用使INCOMPLETE，资源operator[]与方法按声明ID区分。inventory_hdrp.py仅新增AST哈希/字节数元数据。完整Forward在独立输出artifacts/forward-analysis/input重新调查，预处理/AST成功；分析结果artifacts/forward-analysis/final为ANALYZED，1388定义/284可达定义、1039调用点、108外部声明身份、13默认实参、51全局初始化、140全局引用。完整树91259节点含NULL。统计分主体20319、默认式18、全局初始化7570节点，无常量传播，不代表运行时必达。

实际资源引用含30声明/6只读StructuredBuffer、数组/立方/3D纹理与比较采样器；未发现Wave/Interlocked或RW声明。固定opaque Forward定义BYPASS_ALPHA_TEST，不能因_ALPHATEST_ON就声称当前片元裁剪。浮点位载体与IsNaN仍是未来数学规划问题，未私自引入全浮点或忽略其效果。

新增14项DXC/合成回归通过；修复后的全部Python116项通过（日志artifacts/forward-analysis/all-python-tests.log）。另对78份行删除/引号元数据变异运行索引/分析，均正常给出结果或受控AnalysisError，没有异常遗留。核对前轮92源快照：唯一差异是获准的inventory元数据，其余91份核心/证明/输入/锁均一致；本项不重复未改的27个Lean控制，沿用c1de3d7完整通过的历史证据，不能称这些控制本轮重跑。

独立Q第一轮发现两项P2：inventory为合法JSON但非object时AttributeError导致报告遗留IN_PROGRESS；prev链同名但签名冲突仍会ANALYZED。已显式检查inventory/描述对象形状并按ERROR退出1覆盖旧报告；prev链打印签名不能确认一致时INCOMPLETE，不跨该链恢复默认值、不自写类型别名推断。新增对应实际CLI与真实DXC变异回归通过，固定Forward重新分析仍为ANALYZED，结果不变。

独立Q第二轮确认首轮两项关闭，但指出新增签名比较在声明缺少签名时会IndexError，仍遗留IN_PROGRESS。已在构建声明索引时先验证签名，损坏声明抛受控AnalysisError；新增真实CLI回归确认ERROR/退出1。本修复只影响损坏输入，完整Forward再次分析结果不变。

独立Q第三轮通过：实际CLI确认损坏签名ERROR/退出1，相关三项回归独立通过，5产物/4工具/91基线哈希一致，重新计算全部分析字段与报告一致，116项fresh Python回归及27项历史Lean未重跑边界已核对。精简证据planning/evidence/hdrp-forward-analysis-2026-10-26.json保存这些产物/当前工具/基线哈希与实际路径。

本项以 `feat: analyze HDRP Forward entry dependencies` 本地命名提交，无push/正式归档。临时探针、完整AST/图/日志留ignored artifacts，不提交Unity源或缓存，不修改外部工程。分析结果不参与prepare/check，完整Forward→Lean与等价证明仍未完成，后续数学扩展维持Outlined。

# 整数打包后续实施（2026-10-26，已完成）

用户确认语音中的词为“浮点数”和“延迟渲染”，不排除signed整数；本项只实现uint首片，保留其余缺口。精确计划/授权/状态为packing-plan.md、packing-authority.md、packing-tasks.md；授权提交ea3bfda早于产品代码。独立P第一轮通过；指出实际cast/shift应立即快照guard，已落实。

真实examples/packed两份源码经固定DXC转换，artifacts/packed/proof/result.json已PROVED；完整目标同时证明两侧执行域和输出相等，公理仍为propext、Classical.choice、Quot.sound，4份语义模块和手写证明哈希留存。新增12项有限回归通过；统一128项Python回归通过。去掉旧测试中“10u应拒绝”的过时预期，另加精确数值转换回归。schema2/3/4保留。

独立Q第一轮代码审阅通过，无待修代码问题。Q额外运行真实DXC检查uint隐式bool、无u移位、helper内部载体往返、float NoOp载体、覆盖回数值、巨大shift未选分支；重算输入、GeneratedModel、证明和4模块哈希一致。完整核心命令`pwsh -NoProfile -File tools/run_demo.ps1`随后PASSED：128回归及32控制（12 PROVED/18 UNPROVED/2 INVALID_INPUT），日志artifacts/packed/full-core.log，摘要artifacts/acceptance/result.json。独立Q第二轮重算新5控制全部留存目标、检查真实定义域失败目标及两正例绑定/哈希/公理，最终通过。本项Completed，精简证据integer-packing-2026-10-26.json；未将其当作完整Lit验证。

开发中修复了uint函数构造的单元素InitListExpr、纯常量shift域的E类型标注及Lean证明中的过度dsimp问题。位字段定理改用现有已缓存FinCases和BitVec逐位外延，无新增依赖、无ofReduceBool。移位在域外采用有界总化，避免巨大Nat移位造成资源消耗，定义域仍严格要求count<32。独立命名空间DomainSafe.lean在ignored artifacts中已编译通过，只作提前反馈，未写共享proof生成模块，正式状态仍以统一CLI控制为准。
