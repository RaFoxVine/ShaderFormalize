# 二进制向量、局部数组与固定循环：binary-data-003，修订1

本片承接binary-control-002，在用户批准的Overnight B上限内细化。授权包见overnight-request-2026-10-31.txt及planning/overnight/current.md。独立P第1轮已通过；A完整验收通过、精确grant及Approved状态持久化以前，不修改产品代码。总体执行目标仍由delta.md拥有。

## 交付结果与支持范围

让agent用uint2/3/4、局部定长数组和常量次数for组织打包/hash代码，证明与标量展开版输出的完整存储位相等。保留现有float4 stage ABI：`uint4 words = asuint(input); ...; return asfloat(words);`可以输入并观察四路任意32位编码，不必在本片引入uint stage或cbuffer布局。

uint向量支持同标量族的分量/组合构造、uint标量广播、swizzle读写、按值helper参数/返回、struct字段、标量bool选择及分支汇合。已有uint加减乘、与或异或、左右移、一元非/负和八种复合赋值按分量解释；移位逐分量取低5位。`asuint(floatN)`、`asfloat(uintN)`及`asuint(uintN)`保持相同lane数，不做数值转换。向量比较产生的bool向量不开放；需要比较时显式取标量分量。

局部数组长度每维1..64，深度最多16，沿用类型256和叶数4096预算。元素为已支持的普通值或struct，可嵌套数组；不开放数组stage/cbuffer、数组参数/返回、struct中的数组字段、隐式补零initializer或array decay。逐元素初始化后才能读取相应元素；未写部分不能被填零。

数组与向量下标只接受源字面量、当前活动静态循环counter及它们组成的纯uint表达式。一般局部变量或helper参数作为下标拒绝，即使预检查占位值或实参恰能折叠成零；用户可直接写`a[i + 1u]`。每次实际展开执行都解析下标并检查范围，常量越界即拒绝，包括不活动分支；不生成越界fallback，不把现有real bounded_index目标丢进只有位等价的IEEE目标。此限制不会推及现有real入口。

循环为`for (uint i = STATIC_START; i < STATIC_END; ++i)`，接受现有前/后缀++与规范unroll属性。起止界为源纯uint常量表达式，每循环最多64次，每帧最多4096次完整展开；支持嵌套、if和纯helper。循环体不能修改counter、提前return/discard或使用资源；while/do、break/continue、动态/符号界拒绝。零次循环不初始化任何值，预算耗尽明确拒绝，不截断执行。

本片不开放矩阵、signed int、数值float/uint cast、整数除法/余数、bool向量、资源、Compute、out/inout/default参数或默认入口切换。uint stage/cbuffer保持拒绝；helper按值参数和struct字段允许uintN。binary32 profile、完整输出位目标、空schema2约束、IEEE_PROVED及gpu_profile_matched=false不变。

## 共用机制与后端责任

现有IR用整数1..4表示float形状，用字符串uint表示整数标量，不能将uint2直接编码成2。保留旧IR字节，新增uint2/3/4叶型，建立共同的scalar_type、lane_count、vector_type等形状帮助函数。TypeRegistry、initialized、SSA、record、partial_vector、components/vector及局部地址共同消费这些类型，不让IEEE emitter独自识别新类型。partial_vector保存完整类型和对应标量分量，拼装时检查分量族一致。

从shader_addresses.py、shader_aggregate_values.py与AggregateProgram提取普通局部值/地址机制，供real和IEEE组合使用：声明身份、只读、field/swizzle/index路径、单次destination捕获、持久替换、部分初始化及逐分量分支汇合。重复目标swizzle拒绝，重复读取允许；RHS先完整求值，`v.xy = v.yx`保持值语义。读取已初始化分量不能先要求整个向量已初始化。

real保留矩阵、uniform布局、out/inout、数值语义、bit-carrier分量禁令与bounded_index义务。IEEE提供自己的下标捕获、常量计算、普通uint/binary32分量政策和数值运算。不能让IEEE继承包含Copyback/Shared/Control实数语义的整个AggregateProgram。

数组注册/完整initializer/record形式的值组织提为普通本地aggregate机制，real的AggregateTypes保留matrix和uniform职责。IEEE组合自己的类型注册器及共用aggregate行为。旧types.empty/zero_value区别必须保留：用户未初始化元素是None，内部返回占位零仅由后端zero_value构造。

把shader_loops.py的规范parse、counter检查、完整展开和帧记录提为静态循环mixin，real LoopProgram保留原公共导入与后端组合，IEEE在本地aggregate前端组合该mixin。不复制for执行器。循环对终止效果检查通过后端hook；共享AccessChecker把缺失参数mode按in处理，兼容IEEE按值metadata。不得把real function_effects表当作IEEE必有状态。

IEEE常量运算使用自己的uint规则：当前op名uint_subtract/multiply/shift_left/right/negate与packing的sub/mul/shl/shr/neg不同，且旧packing对大移位量政策不同。静态上下界/下标常量通过后端hook解释；跟踪的是源允许的静态来源，不能因为未调用helper检查使用零参数占位而接受输入相关下标。循环counter的静态身份和当前迭代值按作用域维护并恢复。

IeeeSemantics仍拥有语法、运算类型、所有复合赋值metadata和intrinsic签名检查。新uintN广播只接受类型一致且已校验的DXC splat。新增本地aggregate/loop前端与GuardedProgram组合；自动选择器只在新uintN/数组/循环出现时使用新路径，旧纯标量/旧if路径继续保持原目标。私有类名可按清楚的MRO组织，不能以多继承绕入real数值/效果规则。

IeeeEmitter增加`Fin n → UInt32`，逐lane调用现有uint与bitcast标量Model。components/element/Lean类型都使用共同形状接口；旧float向量和标量发射保持原字节。新增类型不是新数值profile，不加新公理，不放宽绑定核验。

## 实施顺序和文件

本片内部先完成向量，再完成数组/循环；每阶段有针对性单元及真实正负例初测，整个003作为一个精确grant和最终验收单元，共用改动全部完成后运行一次默认完整核心门禁，不在两个内部阶段机械重复同一长门禁。

预计调整shader_types.py、shader_aggregate_values.py、shader_addresses.py、shader_aggregate_types.py、shader_aggregate.py、shader_loops.py、shader_access.py，以及IEEE frontend/emitter。允许新增小型共用形状/地址/静态循环模块，原模块保留现有消费者的入口。删除提取后的重复方法，不保留两套array/for规则。测试、真实HLSL/proof、controls、coverage和当前说明同步更新；没有依赖或全局环境变更。

## 实际验收

四组真实original/optimized/wrong HLSL：

- vector-pack：uint2/3/4构造与广播、读写swizzle、部分初始化、struct复制、按值helper和bool分支；改写为同序标量操作。
- vector-ops：所有既有uint运算、一元操作和八种复合赋值在最终输出可观察，逐lane移位覆盖0/31/32/63；改写为同序标量运算，不能让后续掩码抵消被测操作。
- array-hash：uint[4]与四次规范for，读取/更新后按相同顺序输出；改写为手工展开。
- array-vector-loop：嵌套定长数组、uint向量、逐元素初始化、嵌套循环及loop中的分支/helper；改写为显式展开。

正例必须真实DXC→IEEE→完整全称输出位目标→Lean证明→独立绑定与原三公理检查。错误版改变最终可见位，必须成功导入并在SubmittedProof未通过；保留实际原因，不把UNPROVED说成已证明不等价。证明只使用可审计的内核证明，不增加native/SAT公理。

单元涵盖型别/签名metadata篡改、部分初始化读写、重复写swizzle、只读输入、未调用helper、错误bitcast lane、动态和占位参数下标、越界、循环counter修改、65次/4097次预算、零次循环后未初始化读取，以及所有仍排除的相邻语法。静态uint表达式测试覆盖溢出与32/33等移位量，保证使用IEEE规则。

以A验收后的完整83核心+27IEEE目标作为迁移前基线。比较全部110个可导入目标及状态；差异先诊断，不能直接替换基线。最终串行运行全部Python测试、扩展完整IEEE suite（27+8控制，含real回切）、原型19及默认完整核心83。受影响的aggregate/copyback/shared/helper/loop/Compute消费者包含在核心门禁中。

初测后独立Q，记录真实失败尝试、最终源指纹、输入/目标/证明/公理、完整门禁及提交推送。若需新profile/IR语义、隐含数值转换、资源或弱化初始化/边界/绑定，则停止受影响项并记录决定，不凭Overnight上限扩张。普通实现和证明问题自主修复。

## 独立P记录

2026-10-31，/root/binary_data_plan_review第1轮PASS，无阻断或需要用户新决定的事项。reviewer独立对照上限、方案和实际types/address/aggregate/loop/flow/IEEE emitter，只读检查，未修改文件或运行Lean/Lake/测试。它确认typed形状、共用提取及后端边界可实施，特别要求实施/Q核验分量初始化汇合、counter身份跨作用域/helper恢复和旧real地址安全/目标兼容；这些已在本修订合同内。PASS不代表A已经通过，不能绕过A依赖或精确grant。

另有root实际DXC规划探针：uint2/3/4构造、八种vector复合赋值、同lane bitcast，以及局部数组/规范unroll for均exit0。DXC结果/计算类型含uint4及vector<unsigned int, 4>的对应别名；静态检查必须核对canonical类型，而非只匹配字面uint。源、摘要与真实metadata保存在planning/evidence/binary-data-plan-2026-10-31.json，原始AST在artifacts/binary-data-planning。这仅验证DXC可解析，不冒充IEEE支持或Lean证明。
