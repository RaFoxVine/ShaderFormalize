# 矩阵、定长数组与局部元素地址（修订1，P1 Ready，依赖待闭合）

## 目标及责任

本片属于已授权overnight language，依赖copyback切片完整验收和独立Q闭合后才实施。目标是让普通Shader的矩阵计算、定长局部/参数数组、元素更新和复合uniform进入现有实数证明体系。DXC负责语法、声明身份、重载和已确定类型；导入层负责将这些类型及操作解释为有确定数学含义的值。共享调用、完整输入字段、实际执行域、任意共享Fragment.Ops继续沿用。本片不是循环实现，也不代表完整HDRP/Lit证明。

2026-10-26独立P1 Ready，无关键阻断；检查了现有地址四处消费者、record展开、官方mul/调用顺序和真实DXC AST。代码权限须在前置copyback完整闭合后另行持久化。

继续使用显式shared/schema6；auto的旧支持范围不变。矩阵和数组在导入层拥有源形状，在数学模型中降低为现有float/vector/bool/uint叶组成的有序record；不新增不透明矩阵操作、不假设新的公理。旧schema6及schema2/3/4/5保持可读和相同数学文本。本片新增可选uniform_layout/input_groups元数据，必须进入两边接口比较及目标哈希；旧模型缺失时按空解释，不能忽略一侧新增的布局。

完整范围：float矩阵1至4行/列；每层长度1至64、深度最多16、总数值叶最多4096的固定数组，元素可以是现有值类型/struct/矩阵/数组；局部、函数in/out/inout及struct字段可以包含这些值。synthetic类型另限256，不挤占原64个用户struct限制；helper/binding/interface原预算保留。stage入口仍只接受原float/vector或其带semantic的struct；矩阵/数组stage输入、bool/uint uniform、资源数组另片处理，不静默转成float。

## 类型、矩阵与初始化

类型只从typed DXC声明读取；规范化const、row_major/column_major、HLSL输出参数__restrict以及matrix<float,R,C>/floatRxC别名，保留必要的布局属性。T[2][3]解释为外层2、内层3，不能反转。source struct字段身份仍逐个验证；synthetic record字段按确定顺序生成，保留逻辑形状供运算和地址校验，普通叶发射继续复用当前实现。

矩阵逻辑上按行组织，行内为列。支持完整矩阵/数组InitListExpr、普通NoOp包装、HLSLMatrixSplat、HLSLMatrixTruncationCast、矩阵逐分量+/-/*/负号、transpose及DXC已确定重载的mul。普通矩阵*是分量乘；mul按标量缩放、向量点积、矩阵×向量、向量×矩阵、矩阵×矩阵逐一核对维度，以现有实数加乘展开。标量矩阵splat填充全部元素，矩阵缩小取左上子矩阵。用户自定义函数仍优先按DXC身份分派，不因新增builtin名称错误屏蔽用户函数。

允许DXC明确表示的FlatConversion零初始化（例如(S)0），按目标叶类型生成零；不据此支持任意数值位编码。数组只接受完整且类型一致的初始化树；本地DXC拒绝float x[3]={1.0}，不得自行按C++补零。未初始化值逐叶保留，不能从数学零值推断源程序已经写入。整个未初始化vector增加仅存在于导入器的逐分量状态；静态分量写全后成为普通vector，整值/未写分量读取拒绝。分支只在两侧均初始化的分量保留已初始化状态；这种内部状态不得进入序列化模型或Lean。

实际DXC aggregate-operators.ast.txt:99/106将嵌套数组内层InitListExpr标为void；初始化递归须从已验证的父数组形状传递目标类型，逐层核对完整元素数和叶类型，不能要求内层节点自行携带最终数组类型。

## 统一地址和表达式顺序

用typed地址描述统一整变量、struct字段、数组元素、矩阵行/列元素、向量下标/不重复分量swizzle。地址包含DXC根声明身份、每段源类型及字段/索引/分量路径；静态描述用于访问集合，实际绑定时解析调用者symbol并求值及快照索引。矩阵/向量的CXXOperatorCallExpr只接受已验证的DXC内建operator[]签名，不把任意C++运算符当下标；数组使用ArraySubscriptExpr。只剥离匹配接收类型的LValueToRValue地址包装。

读、赋值、+=/-=/*=及copy-out共用地址层，替代原整变量/字段tuple的内部消费者，避免每处各自解释索引。选定元素读使用完整字段的有限选择，写按相同索引条件逐元素更新，其他元素保留。swizzle交换和多个输出均先快照所有结果再写，禁止重复目标分量。out不读取目标旧值，但要执行索引表达式；inout还读取旧选中值。索引在地址形成时捕获，copy-out时不得重新求值。

下标支持uint及DXC整数字面量；不把一般有符号int悄悄转成uint。动态下标必须满足实际执行位置0<=index<size。新bounded_index原语保留uint值，以严格正整数size元数据产生guarded域结论；不取模、不增加输入前提。发射器、共享模型validator和有限求值器都验证类型/size/引用，有限oracle仅在实际执行越界时失败。读取使用一条checked索引的快照，避免重复执行域。静态常数也经过范围检查；可从有限纯uint常量表达式/局部快照恢复常量，越界不能靠常量折叠漏掉域。

访问集合按路径段比较：相同根、兼容前缀可能重叠；静态不同元素/不同分量可判不重叠，动态下标视为可能匹配任一元素。两个copy-out无法静态证明不重叠则拒绝。地址索引的读写也进入兄弟表达式冲突检查，尤其F(out a[i], G(out i))、a[i] += G(out i)以及嵌套下标；不能只检查最后目标。保留现有调用/构造/采样/普通二元未定序冲突规则与if/三元/短路顺序。动态写需要所有可能被保留的目标已初始化；静态元素写可逐步初始化定长值。

## Uniform、范围及迁移

将cbuffer的结构检查与值类型检查分开：旧默认入口仍用原规则；shared先保存已核验身份的字段，再由新类型注册表解释float/vector/struct/矩阵/定长数组。仍仅单个register(b0)，不支持packoffset等未知属性。uniform_layout记录每个源字段的完整类型形状、顺序及矩阵packing（缺省按固定DXC命令的列主序）；显式row_major与默认column_major不能因为逻辑矩阵值相同而被当作相同接口。嵌套字段布局也保留；无法解析的packing属性受控拒绝。

数学输入按确定路径展开，例如_M[0]为一行、_Weights[1].color为叶；uniform没有位置参数。每个真实叶仍计入原最多64输入预算，名称无歧义。input_groups记录源矩阵/数组/struct及子组到展开叶的映射，便于范围选择。ranges可选完整组或精确叶，组展开后与叶范围取交集，交集为空报INVALID_INPUT，不能引入无法满足的前提使证明真空成立。nonzero_vectors只接受真实float2/3/4叶及原有合法swizzle；整个矩阵/数组不是向量。旧平面uniform模型/范围规则结果保持。

文件消费者：shader_frontend的构造类型/buffer结构/uniform构建提供默认保持旧行为的小钩子；新shader_aggregate_types.py、shader_aggregate.py和统一地址模块承接shared专属逻辑；shader_access改用typed路径与地址求值足迹；shader_validation增加按program策略的地址/语句钩子；copyback所有地址消费者迁移共用接口；packing/shared Lean与有限求值/模型检查实现bounded_index；shader_model及CLI接口/范围解析支持可选布局与组；统一runner、说明与精简证据同步。无新依赖/公理/Unity写入。

## 可执行验证和止损

先用真实固定DXC单元验证非方阵、两种mul方向/矩阵积、标量全填充、截断、transpose、普通*分量乘、嵌套数组顺序、struct零/完整初始化、各类参数复制/输出、静态逐叶初始化、动态读取/写回及索引快照、swizzle交换和独立输出。有限计算与明确手算结果比较，不能只让同一实现互相比较。负例覆盖维度/签名/类型错误、越界实际/非实际域、部分初始化、重复/重叠/动态未知输出、索引兄弟读写冲突、整数/载体误用、超预算、坏模型size与引用、异侧布局/范围冲突；旧入口拒绝新语法。

正式控制至少六项：包含默认参数/out/inout/struct/矩阵/数组的正常光照材质与手工展开版PROVED、故意交换矩阵系数UNPROVED；分支元素更新后ddx与内联对任意E/Ops PROVED；实际执行合法下标PROVED、相同源码实际越界UNPROVED、非法下标只在未执行分支PROVED。证明目标仍合取两侧域及最终Option颜色相同，公理白名单不变。旧47控制与新控制统一runner真实通过；Q核对全模型引用、目标/模块/输入/证明哈希和旧生成文本不变。初期raw DXC调查在artifacts/language-probes，不宣称GPU验证。

停在需改变实数/完整字段/实际域、隐含物理布局假设、接受有顺序依赖程序、新入口/IEEE/新公理、无法执行关键oracle或三轮独立Q仍有关键问题。普通实现故障按同合同修复。循环仍后续单独Ready/P/精确grant；本规划自身不赋予产品代码权限。

主要语义依据：[HLSL mul](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-mul)、[HLSL转换草案](https://microsoft.github.io/hlsl-specs/specs/4-Conv.html)、[调用顺序草案](https://microsoft.github.io/hlsl-specs/specs/5-Expr.html#function-calls)，并以仓库固定DXC真实typed AST确认支持的写法。Packing只影响外部输入对应关系，数学矩阵仍按逻辑行列解释。
