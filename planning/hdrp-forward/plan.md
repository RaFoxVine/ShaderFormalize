# HDRP/Lit Forward：入口依赖与能力缺口（修订2）

## 目标和授权范围

用户在确认核心自包含后选择官方HDRP/Lit Forward作为下一阶段真实输入，并沿用此前“完整方案不需另行人工审阅，先跑通”的执行偏好。数学基础仍是实数；DXC负责解析/重载/引用，Unity只是显式开发输入。此节点第一项只做可复现的入口分析，不能将其当作HLSL已转换或Lean等价证明。旧control-flow授权已完成，不借旧grant写新语义代码。

本次只将“固定Forward输入→从Frag追踪可能调用的定义/外部操作/全局引用→能力缺口及可复查路径”做实。临时探针表明完整AST有1388个定义，Frag语法可达284定义/20055主体节点，139个全局声明被引用；这些是未做常量传播的上界。只读资源和矩阵下标的CXXOperatorCallExpr必须包括在调用分析中。当前只读探针位于ignored artifacts/forward-analysis，不构成产品实现。

## 架构和责任

新增独立的DXC dump索引与分析CLI。它只消费明确提供的AST文本，不尝试识别HLSL源码语法，也不调用Unity或更改现有proof工作区；核心prepare/check、全部函数语法拒绝、schema2/3/4、数学Ops、定义域及公理审计均不改变。分析输出供agent规划和查证，不参与证明目标生成，不让“不可达”成为绕过核心未知语义拒绝的入口。

索引读取DXC打印的树层级/声明身份/调用目标和原始头文本；对未知语义节点可保留原文，但不能把未知调用当无调用。分析使用DXC声明ID连接函数（含重载和prev声明链），从唯一具名入口遍历，循环图终止；外部函数和资源方法分别列出，CXXOperatorCallExpr包含operator[]。每条调用保留调用点、原始目标ID、规范声明ID、调用目标类型/签名；外部重载/同名资源方法不按名字合并。函数引用/资源类型只作语法事实，不声称常量传播、数据流精确资源集合或运行时必达。

闭包同时包含隐含依赖：所有TU/namespace/cbuffer级全局变量初始化作为保守根，包含未被函数引用的初始化，防止漏掉其可能副作用；不把结构体字段默认式误当独立执行。全局初始化及其引用的全局依赖递归遍历。每个CXXDefaultArgExpr按已解析callee、参数序号和完整prev参数链恢复唯一默认初始式，递归纳入其调用/全局引用/未知节点；显式提供参数时不擅自执行默认初始式。无法恢复唯一默认值时INCOMPLETE。CXXOperatorCallExpr的隐式对象参数与正式参数序号区分。默认初始式若再次包含默认调用同样闭包，设置已访问集合防止循环展开。

文件：tools/dxc_ast_index.py拥有索引、声明、调用解析及上界统计；tools/analyze_shader.py拥有参数/输出/输入哈希与错误状态；tools/test_ast_index.py验证真实DXC及合成错误边界。可选inventory_hdrp.py为成功AST输出补SHA/字节数，便于绑定调查来源。现有shader_ast.py与转换器不改，避免让分析对未知元数据的容忍扩大数学前端。

## 第一项：可复现入口分析（Execution Ready）

- 输入：`--ast <DXC dump>`、`--entry Frag`、`--output <目录>`，可选`--inventory <inventory_hdrp result.json>`；无Unity工程参数、无外部包发现、无Lean执行。
- 输出：JSON报告保留输入SHA/字节数、唯一入口签名/定位、全部定义数、上界可达定义与边、短调用路径、外部操作/全局引用、节点/运算/类型统计以及缺口例证；默认实参绑定和全局初始化根另显式列出。定位使用dump行号及原始头文本，不伪造多文件源码位置。
- 来源绑定：未给inventory时明确“仅绑定AST字节，Unity来源未验证”。若给inventory，要求status=INVESTIGATED、preprocess_status=PREPROCESSED、ast_probe_status=PARSED、ast_sha256/字节数匹配；按其相邻产物文件验证预处理SHA。报告引用inventory哈希和固定宏/包版本；不据manifest中绝对源路径自动打开/发现Unity工程，不重新声称验证了当前外部源。所有外部Unity关联仅来自显式输入文件，不成为核心依赖。
- 分析状态与核心证明状态分开：ANALYZED退出0表示调用结构闭合的语法上界；INCOMPLETE退出2表示可定位的未知调用/构造、未知且可能隐含调用的Expr/Stmt、无法唯一绑定默认值/声明链。已知纯节点只遍历显式子树；未知Expr/Stmt保守标为INCOMPLETE，不能因没有CallExpr子节点就判无调用。未识别的元数据头可原样保存，不伪造源位置。损坏树、入口缺失/重名、预算超限、来源不符等ERROR退出1；开始即写IN_PROGRESS，任何可写输出目录下的失败覆盖旧成功，并在stderr给出错误。输出目录本身不可写则退出1并明确报告无法保存，不宣称旧报告已覆盖。即便ANALYZED，也不宣称支持该代码或证明完成。外部已解析无体声明/未打印intrinsic按明示external edge列出，不称未知callee；外部调用的语义仍未被验证。
- AST索引预算：32MiB、500000节点、128层、8192函数定义、100000调用边。按顺序验证树，不静默跳过未知非节点输出；NULL槽保留。callee只剥离已知透明包装再读取直接DeclRef/MemberExpr，禁止从任意子树猜一个名字。声明ID重复冲突、prev链歧义/循环明确拒绝或INCOMPLETE。
- 迁移：不替代旧核心AST解析，不改旧测试预期；临时探针不进入Git。docs/hdrp-investigation.md更新成唯一当前调查指南，planning/evidence新增精简实际证据；README只增加指针。无依赖升级、全局环境修改、Unity写入、push或归档。
- 验证：真实DXC重载/未调用函数/前置声明/资源方法/矩阵下标/默认参数/多文件位置，包括Seed()默认式和Global()全局初始式探针；同时覆盖未引用全局初始式、被显式实参覆盖的默认式。核对实际Forward的13个无子树默认实参和unity_RendererUserValue初始化。合成未知callee/隐式构造、NULL/损坏深度、同名入口、prev链、循环图、预算、旧成功覆盖、来源错配。跑全部Python回归，并对固定原始Forward AST运行CLI；独立Q以原始AST和输出核对声明ID和路径。现有核心/证明/依赖文件以基线c1de3d7及92源快照核对；唯一允许变化项是可选inventory_hdrp.py的产物哈希元数据，其余91份必须一致。本项未改数学前端或Lean文件，不重复27个既有Lean控制，沿用该基线已完整通过的证据，明确记录此验证边界。
- 完成：可靠工具/实际报告、可复查缺口、独立P/Q、文档与本地命名提交。不能将报告的缺口数量或ANALYZED当作Forward已转Lean。

## 后续工作（Outlined，不授予核心实现权）

完整Forward验证仍是方向。应根据第一项结果规划通用的Frag/out入口、来源映射、函数共享/按值与out更新、向量/矩阵/数组，以及只读资源/有界或可证明循环、整数位运算和数学intrinsic。现有“全部helper展开成4096 SSA绑定”不宜直接用于完整Lit，应先确定可共享函数/循环表示及完整执行条件的数学契约，再进入核心实现。

浮点位重解释是实数模型的真实边界，不可偷偷引入全浮点：例如CopySign的位操作分支在ignoreNegZero=true时可被证明排除；_DiffusionProfileHash和unity_RenderingLayer.x则把float当位载体；IsNaN还可能位于异常数据恢复路径。第一项只给出路径和事实。后续须调查常量传播能排除的部分及必要位载体表示，形成明确数学方案；不能把asuint当整数数值转换、把所有float位解释任意抽象后宣称原实数保证不变。

只支持小部分Lit应在后续提案中列为范围裁剪并说明保证变化，不能自主把材质子函数当完整Forward验收。完整Lit分阶段落地，不承诺此项已经实现所有语义。

## 当前检查点

P第一轮指出默认实参/全局初始化隐含调用未封闭、外部重载身份与状态/来源接口未冻结，故修订1未Ready。修订2补齐上述契约及真实oracle；第一项等待聚焦P复核。通过后根据用户此前明确免重复方案人工审阅的授权，持久化本项精确grant和Approved状态再写产品代码。任何改变核心数学对象、绕过未知语义、改变支持/失败保证或引入新依赖的工作不在本项授权内。继续使用Smart管理及Git正常审阅，不使用Lavish，不创建新TreeDive项目。
