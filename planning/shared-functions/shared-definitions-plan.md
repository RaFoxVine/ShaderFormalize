# 共享函数数学定义（修订2，Planning Ready；依赖待闭合）

## 目标和依赖

本切片属于overnight language条目。依赖plan.md的完整返回字段修复完成验证；该前置项已在71f307f以132回归/35控制和独立Q2闭合；本项独立P2 Ready。目标是同一个helper只生成一份数学体，调用保留为调用，不再按调用次数递归复制整个体。不是把helper变成任意黑箱；DXC仍解析和确定callee，Lean仍能展开实际生成的函数定义。

后续default/out/inout/矩阵/数组/终止循环保持language总目标，本切片先用既有受支持语法建立共享调用框架。普通按值参数、嵌套struct/float/bool/uint、现有控制流/裁剪/采样/导数均须可组合；载体跨helper边界仍拒绝。原默认schema2/3/4/5及CLI不迁移，新增显式`--frontend shared`和schema6；将来新语法可选择此后端，不逼旧证明马上重写。

## 架构与数学接口

新增SharedProgram复用PackingProgram/ControlProgram的typed DXC表达式、局部控制路径、实际执行前缀和不可变值。所有函数仍逐体检查未知语法/初始化/非递归和预算。每个helper按DXC声明身份缓存一份body model，使用完整字段形式实参占位符编译；源类型/记录字段顺序来自现有TypeRegistry，不自行做HLSL重载解析。当前禁载体跨边界，所以同一源函数的参数数学类型固定，不做不明的按值类型猜测。

helper的数学输入为任意E、共享Ops、同一程序的全局输入、实际入口mask和各参数的完整字段。返回生成的专属结果structure：返回值各叶字段、全局裁剪保留mask、所有实际执行域的Prop。struct按既有字段顺序展开到有类型的叶字段，不丢名义布局。调用者的alive并入传递的entry；callee从alive=True开始计算调用保留mask，entry外保持存活，返回后caller将旧alive与此mask合并。函数内部return只影响本帧路径，完整返回字段不按caller entry清零。

SharedProgram拥有helper缓存和调用事件：编译helper时保存/恢复当前bindings/effects/events/stack/guard/alive/frame等运行状态，嵌套调用递归取得callee缓存，按依赖拓扑生成定义；不把编译helper产生的域误加到主程序。调用点先快照全部实参（忽略或覆盖的实参仍执行），再插入`call`事件；该事件引用确切helper、参数字段和当时entry。结果用指向该事件的有类型叶引用表示，void调用也保留事件。每次调用的域都纳入caller结论，未调用helper定义的域不成为输入假设或主程序义务。

SharedEmitter复用PackingEmitter/ControlEmitter的值和定义域发射，只增加formal参数/entry、call-result/call-alive引用及call事件。每个helper生成明确Lean structure和函数，先callee后caller；每个事件只`let`一次调用结果，再引用其字段/defined。call索引、callee索引、返回字段类型/范围及事件顺序必须验证，未知引用拒绝。BooleanDAG可将这些精确渲染的Bool字段视为共享原子，但不能把它们全称量化成与callee脱离的新任意操作。已有原子仍照原规则。

数学操作仍来自Model/Fragment/Control/Packing；新helper结构和组合定义包含在GeneratedModel哈希中，不新增公理或任意函数假设。schema6完整目标仍要求两侧所有已执行域合法及Option颜色字段相等。本片显式拒绝schema6与旧模型混配，报受控ModelError；CLI双方统一后端，因此正常入口不产生这种混配。旧2/3/4/5之间的既有提升不变。参数布局/资源完全一致的静态检查保留。semantic_modules报告对schema6至少包含现有四数学模块，不落回仅Model分支。

## 文件和消费者

tools/shader_shared.py拥有缓存/事件/调用解释，shader_shared_lean.py拥有共享定义生成；shader_frontend.import_shader保留旧双参数默认接口并增加显式后端选择，shaderformalize CLI配对双方使用同一选择。ControlEmitter可提取begin/finish/extra-event扩展点，默认路径保持原输出；BooleanDAG新增精确已知引用分支。单独共享有限求值器执行相同helper body model的递归调用，保留每帧locals/effects/call结果、完整Ops输入和guard，不使用Lean生成文本求值；可复用既有数值/位/控制算子，不复制一套数学规则。

shader_lean.generate_lean在旧分派之前显式处理schema6与混配拒绝，未知schema不得回落旧数值路径；shader_eval.evaluate_model显式接入共享求值器，schema6不得按普通数值求值。参数/模型选择、JSON类型/引用预算失败都用既有受控状态，不遗留IN_PROGRESS或Python异常。上述分派、混配拒绝和报告模块均有回归，不仅测试CLI正常正例。

`--frontend shared`的消费者是大函数图输入和后续语法扩展。prepare仍只生成、check仍独立绑定/审计。原proof/示例不替换；增加正常结构化着色的shared正反例及手写证明，并将显式后端正负控制加入默认验收。报告清楚区分schema6；source/program预算仍有界，不以无限资源接受递归。

## 验证和完成

真实DXC覆盖float/bool/uint/struct按值、嵌套helper、helper内纹理/导数、void clip/return/discard、实际参数域。共享与现有inline有限结果按独立公式及同一个对全字段和mask敏感Ops比较。构造13层双调用空helper图：旧全展开超过4096拒绝，新模型应只有13个helper体和线性调用事件，不把增长藏到GeneratedModel中；记录定义/事件/生成字节，不靠耗时声称改善。递归/未知未调用体/错引用/预算依旧拒绝。

形式验证至少包含正常结构化着色原版/等价改写版PROVED、错误数值UNPROVED、分支下helper导数与内联对任意共享Ops PROVED、实际执行但被忽略实参的非法域UNPROVED、未调用非法域正例。所有执行域仍为结论；共享定义的域不能默认True。当前全部旧核心控制和新增控制在统一runner通过，独立Q核对实际调用字段/上下文/域/公理，当前文档和本地提交。无Unity写入/依赖升级/push/merge/archive，发布交publish条目。

若需要改变字段完整性/执行语义、把未知helper当任意Ops、允许隐藏域前提或扩展到尚未Ready的新语法，停止受影响部分重新规划；普通实现细节由agent处理。
