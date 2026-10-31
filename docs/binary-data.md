# 二进制局部数据

IEEE入口接受uint2/3/4构造、同族标量广播、swizzle读取及局部写入。uint运算按32位模算术逐分量执行，移位量逐分量取低5位；比较条件须为标量bool。按值helper和struct字段可以使用uint向量。重复读取分量允许，重复写目标分量拒绝；右侧先完整求值，再更新目标，因此`x.xy=x.yx`交换原值。

入口保持float4输出和float输入/cbuffer。`uint4 words=asuint(input)`把任意binary32编码作为四路uint输入，`return asfloat(words)`观察完整结果位。asuint/asfloat须保持lane数，数值float/uint cast、bool向量、矩阵和资源不在此入口支持范围。

局部数组每维1..64、深度最多16，支持已有普通值和struct元素以及嵌套数组。完整initializer必须逐元素提供；也可以声明后逐元素写入。只允许读取已经初始化的分量/元素，分支汇合保留两侧共同初始化的部分。数组参数、返回、struct中的数组字段、stage/cbuffer数组及隐式补零initializer拒绝。

下标只能来自源字面量、当前静态循环counter及其纯uint表达式，一般局部变量或helper参数不能作为下标。每次展开检查确定下标的范围，越界或动态下标拒绝，不生成默认值。未调用helper也检查语法和初始化；预检查零占位不能成为静态下标来源。

规范for形如`for(uint i=0u;i<4u;++i)`；起止界为纯uint源常量表达式，支持前/后缀++和现有unroll提示。每循环最多64次，每帧最多4096次展开体执行。执行完整展开，不按fuel截断；body不可修改counter或提前return，break/continue、while/do、动态界拒绝。零次循环不会初始化任何值。helper自己的正常返回不终止调用者循环。

公共形状、局部地址、partial值、固定数组和静态循环机制由real与IEEE共同使用；数值操作、内部零值、下标安全政策分别属于后端。real的矩阵/布局/copyback/bit-carrier和bounded_index义务由原入口保留。IEEE输出目标量化全部输入存储位，使用既有binary32 profile及原公理审计；gpu_profile_matched仍为false。

真实示例位于examples/ieee-data，四组分别覆盖向量打包、逐分量运算、数组hash、嵌套数组循环。各组original/optimized/wrong分别用于完整位等价和错误改写证明失败控制；正式结果由对应artifacts记录。
