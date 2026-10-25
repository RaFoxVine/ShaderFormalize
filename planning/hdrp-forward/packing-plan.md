# Forward基础扩展：整数打包（修订1）

## 目标与整体位置

用户要求继续补齐实际HDRP/Lit Forward的能力，确认“不考虑浮点数底层实现”，同时要支持延迟渲染常见的8位量化、整数位字段、float位载体。完整Forward仍是总目标；本次先完成其中可独立验证的整数打包链路，不把小示例当作Forward验收。此前用户已明确免重复人工方案审阅，Smart仍执行独立P/Q及精确授权。DXC解析源码及类型；Python负责受支持AST的数学解释；Lean负责等价与全部已执行计算的定义域；Unity保持可选且不改动。

## 共享框架及本项实现范围

在现有schema2/3/4旁增加schema5 packing前端与发射器，复用ControlProgram的执行掩码、值拷贝、helper展开及定义域结论。只增加受控的类型/验证/发射扩展点，不复制整个控制流解释器。普通float仍是实数；uint是Lean内置BitVec 32，包含截断的加减乘、按位与或异或非、逻辑移位、无符号比较。移位计数要求小于32，作为执行guard下的证明义务，避免对未核实的超宽计数行为作约定。除uint以外的整数类型本项明确UNSUPPORTED，后续signed不是项目排除项。

本项接受uint标量局部、struct字段及按值helper参数/返回，不扩展stage/cbuffer的整数或payload输入布局。整数字面量从源码恢复十进制/十六进制和u后缀，核对DXC值，限制32位。未带u的literal int只允许现有实数字面量转换或被DXC明确转换成uint的非负常量，不推断有符号运算。float→uint使用向零截断，在实数值0≤x<2^32时合法，条件作为结论中的定义域义务；uint→float是toNat到实数的精确数值转换。C样式/函数样式cast仅允许DXC已解析的合法转换结构，不做源代码模式识别。

asfloat(uint)生成带静态payload标记的float载体；asuint(payload)恢复同一32位值，asuint(uint)为恒等。载体仍占HLSL float槽，但其Lean类型是BitVec 32。标记经过快照、局部赋值、struct拷贝及相同类别的分支选择保留；混合数字/载体的选择、载体的数值计算/比较/clip/导数/采样/输出，全部UNSUPPORTED。第一项不允许载体跨helper参数/返回；允许在helper内部完成uint→carrier→uint往返。如此不需猜测float参数是颜色还是位载体；后续显式payload输入接口及按调用类型实例化另立Ready项。普通实数asuint、任意asfloat后数值运算、IsNaN位技巧明确拒绝，不能添加任意Real→bits抽象冒充真实编码。

保留所有定义的语法验证和未调用helper初始化验证。非法或未知构造不能因输出未使用而绕过。支持的新类型由专用模块集中负责识别/验证/值规则；原有默认类与测试契约不扩大。schema5保证与schema4相同：约束范围内两侧所有执行的域义务成立，且输出及丢弃状态相同。约束schema2保持；其输入仍纯实数，因此原范围及nonzero语义不变。两侧schema不同但接口一致时使用更强的schema5发射器，不要求改写版残留无用uint代码。

## 文件、消费者及失败契约

tools/shader_packing.py负责检测、类型与AST扩展和payload流；tools/shader_packing_lean.py负责新操作、位载体类型和cast/移位域义务；proof/ShaderFormalize/Packing.lean负责精确uint模型及通用位字段证明。现有types/validation/frontend/control/emitter只增加明确的扩展点；CLI semantic_modules审计加入Packing，guarantee准确描述实数加32位整数模型。examples/packed新增正常helper/struct写法的RGBA8量化与两字段打包、载体往返和拆包，以及错误字段位置的负例；proof/PackedProof.lean由agent提供证明，核心不内置证明搜索。

更新统一verify_demo.py和tools/run_demo.ps1可选项及README/当前文档，默认核心验收包含新正/负例。测试用真实DXC验证AST、全量位字段边界，覆盖cast临界/越界、shift计数、截断、payload标记丢失/混合、未调用函数拒绝。现有CLI状态、公理白名单不变；bv_decide默认会依赖Lean.ofReduceBool，本项不得使用。复用内核可检查的BitVec定理与位外延证明，不能为通过证明添加新公理。

## 验证及停止条件

完成要求：真实HLSL原版/等价改写版通过prepare/check并PROVED；故意错误拆包用原证明检查必须UNPROVED，另提供独立可计算反例；越界量化或超宽移位不能靠相等但未定义而PROVED；payload误用UNSUPPORTED；全部现有核心回归及新增控制通过；独立Q检查真实diff及绑定/公理证据；本地命名提交。无Unity调用/写入、依赖变更、push或归档。

如发现需要float编码、隐藏输入假设、放宽公理或改变定义域保证，停止受影响实现并说明。后续共享函数表示、out/inout、数组矩阵、资源与循环仍需按实际Forward需求推进；当前IsNaN可达路径及外部float位载体必须保留为明确缺口，不能悄悄排除环境光探针或声称完整Forward已经跑通。
