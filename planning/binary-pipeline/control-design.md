# 二进制分支与局部赋值：binary-control-002，修订1

本片承接已完成的binary-bits-001；总体目标仍由delta.md拥有。基线为d0da6ea06029d92ac754f4d186841d53b8f3addf。本片独立实施前审阅P已通过，当前为Execution Ready、等待用户批准；尚未修改产品代码。

## 要交付什么

让现有二进制入口接受普通的纯计算分支：if/else、嵌套if、main及按值helper中的提前return、分支中的局部变量/struct字段赋值与汇合，以及标量uint的八种复合赋值（+=、-=、*=、&=、|=、^=、<<=、>>=）。例如helper按编码高位选择打包方式，再提前返回包含uint和float字段的struct；agent可以证明它与使用三元选择的改写版输出存储位完全一致。

条件必须已经是标量bool，例如word < 0x80000000u或value != value。保持现有浮点比较、舍入与uint32规则，包括NaN、自比较、正负零和低5位移位。if(floatValue)、if(uintValue)所需的隐式数值转bool，以及signed int、数值float/uint cast不在本片开放。入口/布局、空schema2约束、ieee-1、IEEE_PROVED和gpu_profile_matched=false不变。

本片不包含循环、数组/矩阵、uint向量、out/inout、默认参数、资源、clip/discard、导数、采样或Compute。它为后续二进制循环与资源处理提供分支能力，不代表这些后续工作已完成，也不切换默认实数CLI。

## 为什么复用现有分支执行器

固定DXC已经能完整解析这种写法。[规划探针证据](../evidence/binary-control-plan-2026-10-31.json)保存了实际输入、摘要和结果：DXC exit0，包含IfStmt、uint CompoundAssignOperator和helper/入口ReturnStmt；当前IEEE入口明确以UNSUPPORTED拒绝IfStmt。完整本地输出位于artifacts/binary-control-planning。这是本项目接入范围的限制，不需要重新解析HLSL或更换编译器。

目前ControlProgram把分支/函数返回的通用执行和实数表达式、clip/sample等语义写在同一个类中。直接让IEEE继承整个实数前端，会继承实数零值、数值转换和效果处理；另写一份分支解释器则会重复维护汇合和提前返回规则。本片把通用骨架提取为共享基类，两个数值前端各自解释表达式。

## 代码归属与执行过程

1. 新增tools/shader_flow.py，拥有Flow及GuardedProgram(Program)：执行掩码、SSA快照、条件汇合、函数调用帧、返回收集、作用域与已有复杂度限制。从shader_control.py搬移对应逻辑，保持原顺序和数据形状。real ControlProgram继承GuardedProgram，继续拥有自己的expression/call/sample/clipping/model；discard处理通过real前端回调实现，公共骨架不定义丢弃、纹理或数值运算。shader_control继续导出Flow，兼容既有LoopProgram等导入。
2. Program提供后端零值构造钩子，用于未调用helper检查的已初始化形参占位和返回汇合的内部默认值；现有实数实现仍生成原来的零值。IEEE实现生成精确的+0编码（asfloat(0u)）、uint零、false及其向量/record组合。用户未初始化局部仍为None，绝不能用零值钩子填补；分支一侧未赋值的读取和未调用helper错误仍须拒绝。
3. 在shader_ieee_frontend.py把现有IEEE表达式校验/解释分离为共享语义mixin。现有IeeeProgram继续配Program处理无if的程序；新增IeeeControlProgram配GuardedProgram处理含if的程序。只要任何定义中存在IfStmt（含未调用helper）就选择分支前端；bool、三元本身不触发迁移，保留旧21控制的既有目标。mixin不继承另一个具体前端，避免两个完整Program实现的多继承冲突。
4. 分支前端复用既有静态检查：每个非void函数所有语法路径必须返回；条件已定型为bool；所有helper均检查语法、调用图和初始化；入口只读，helper按值参数及局部可写；record复制和字段更新保持值语义。旧无if的IeeeProgram保留其无guard状态的预检查；新IeeeControlProgram使用guarded预检查，保存、重置并恢复完整的guard/alive/frame/branches等状态。不能仅凭现有control=True就假设对象已经拥有这些状态，也不能把旧预检查放进mixin覆盖新前端的完整预检查。
5. uint复合赋值由IEEE语义拥有，复用Program的validate_statement/assign_statement扩展点。检查左右操作数、结果、DXC的ComputeLHSTy/ComputeResultTy均为uint，并只接受上述八种运算；先读取已初始化旧值，再以现有uint操作构造新值，写回同一局部/字段。分支和直线程序使用同一规则，不开放表达式中的赋值或带副作用的lvalue索引。
6. IEEE输出仍由shader_ieee_lean.py发射为纯函数：SSA值和bool选择构成float4输出，全称expected保持完整存储位相等。新增支持的所有数值操作均为总函数，没有外部效果和浮点异常状态；不活跃分支的纯中间表达式可以出现在Lean let中，其值不进入被选择的输出，不增加“所有分支非NaN/除数非零”前提。guard注解不能被解释为已支持资源/导数/丢弃；以后接入这些效果必须另作语义设计。

约束沿用32层分支、每帧128个返回分支、4096个绑定/调用及现有struct/helper上限。达到上限明确拒绝，不能截断执行或以默认零返回。旧real前端的效果掩码、定义域目标和输出仍由其原有后端拥有。

## 验收与兼容

新增三组真实HLSL，每组original/optimized/wrong：

- branch-record：按编码字段选择结构体各字段，与三元/统一出口改写比较；包含嵌套if、两侧初始化、分支后读取和struct值复制。
- helper-return：uint helper含提前return及局部复合赋值，与保持相同运算顺序的显式赋值改写比较；八种复合赋值均在实际DXC测试中覆盖，至少一份完整HLSL证明目标使它们影响输出。
- float-branches：NaN判定、正负零判断、分支除法/位返回与对应选择表达式比较；覆盖不活跃分支的特殊值不改变最终输出。错误版本删除NaN分支或改变返回选择。

三个正例必须通过真实DXC→IEEE模型→完整Lean目标→独立绑定及原三公理审计，输入仍量化任意binary32存储位；三个错误版本必须到达SubmittedProof未通过，记录实际失败原因，不把UNPROVED说成已证明不等价。提交证明不得采用sorry或额外native/SAT公理。

单元覆盖各uint复合赋值及metadata篡改、main/helper提前返回、嵌套分支、完整/不完整struct初始化、只读入口写入、未调用helper错误、状态隔离、边界限制；仍拒绝循环、效果、资源、数值cast和不支持条件。检查非活跃分支不被错误附加实数定义域前提。

运行全部Python测试、扩展后的完整IEEE suite（既有21项+新增6项，含默认实数回切）及原型19项。共享分支骨架发生改动，因此还运行tools/verify_demo.py的默认完整核心验收，涵盖现有control、packing、共享helper、copyback、aggregate、loops、数学和Compute消费者，不使用上一片“公共源未改”来豁免。本片还要对旧21项IEEE及旧核心可导入案例比较迁移前后的生成目标指纹；差异必须解释并验证，不可直接替换旧证据为成功。

测试和门禁串行共用现有workspace锁，完整日志放artifacts。初步验证后独立实施审阅Q；补齐当前能力说明、覆盖表、tasks和机器证据，沿用已获授权的非强制提交推送。不修改依赖、全局配置、Unity或旧Lean安装。

## 就绪与停止条件

依赖只有已完成的binary-bits-001及现有工具链。拟修改Program零值钩子、shader_control的骨架归属、IEEE语义与选择器、相关测试/控制/文档；不复制real/IEEE的语言解析。实现可自行选择私有函数命名和文件内组织，不能改变以上责任或等价结论。

若共享提取无法保持旧效果/返回语义、发现须更换profile/IR或削弱目标/审计、需要资源/循环/数值cast才能成立，停止受影响部分并修订方案。若旧目标指纹改变，先诊断实际差异，不能未经说明把兼容承诺降为仅能编译。独立P通过并展示精确checkpoint后，才申请本片实施授权。

2026-10-31独立P第1轮通过，无阻塞。reviewer为/root/binary_control_plan_review，只读核对源、现有消费者、门禁和实际DXC探针，没有运行Lean或修改文件。它确认现有语句扩展点、公共分支提取和纯总函数IEEE发射可行；重点要求已落实在上文的guard状态区分、递归零值/占位两处用途、动态分派兼容，以及将原if/uint复合赋值拒绝测试改为正例并保留相邻负控。P不代替实施后验证或用户授权。

本次Ready Set只有binary-control-002@r1，Frame为delta.md及本方案。用户批准后才能记录新的active grant、修改产品代码并执行完整验证；后续循环、资源、Compute及整体主入口迁移仍未就绪。
