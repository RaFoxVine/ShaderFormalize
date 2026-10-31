# 二进制迁移的实施框架（修订1，首片实施前审阅通过）

用户已经要求先做二进制、随后进入新主线；规格层先跑通流程再细化，不以完整HDRP为最终验收。diff rendering已确认指延迟渲染/G-buffer，不是可微渲染。delta.md保存总体目标；本文件明确当前第一个可独立验收的迁移切片。后续完整迁移仍是必须完成的目标，第一片不冒称整体切换已完成。

## 所在位置及第一片结果

当前IEEE入口复用公共DXC AST读取器和Program类型/函数支持，但其表达式白名单只覆盖float、sqrt和位往返，连uint加减乘/掩码都拒绝。第一片把已有FloatLib binary32与真正uint32计算接起来，使同一段正常HLSL能在全存储位语义下混合计算、打包与hash。它位于DXC解析之后、Lean目标生成之前；不是独立的手写Lean替代Shader。

选择继续使用已定类型AST及现有IeeeProgram，不在这片引入LLVM/DXIL解析器或新依赖。共享AST/类型结构由现有Program拥有；本片只增补已解析节点的二进制含义。后续公共执行表示迁移另形成切片，不能趁本片悄改实数入口或Compute目标。

## 明确语义与接口

- 沿用当前binary32最近偶数、保留subnormal、逐操作舍入、无隐式FMA的参考profile；完整存储位相等，gpu_profile_matched=false。命令仍为ieeeformalize.py prepare/check，成功仍IEEE_PROVED，空schema2输入约束不变。
- 增补标量uint32加、减、乘（模2^32）、按位与/或/异或、补码取负和按位非；uint六种比较及uint/bool三元选择。识别合法十六进制uint字面量，保持DXC数值与源码token一致校验。
- 左移和逻辑右移使用移位量低5位（模32）。该规则由SM5官方指令说明及固定DXC动态移位输出探针核对；不能沿用旧实数打包器对shift<32的域限制，也不能直接假设Lean宿主移位规则一致。包装函数显式表达该规则。
- asuint/asfloat仍为真正float32与uint32存储位重解释，可跨已支持的按值helper及struct字段；asuint(uint)恒等重载按DXC签名核验。不添加float数值转uint或uint数值转float，不用宿主float近似转换代替。
- 本片保持float4入口、原有结构体/helper/float向量范围。uint向量、signed int、整数除余、一般if/循环、纹理资源及Compute扩展不在当前切片；后续迁移必须处理，不因本片通过而标全局完成。二进制整数没有NaN，uint比较不能错误调用浮点比较。

## 具体代码归属与删除

修改tools/shader_ieee_frontend.py的表达式校验/构造和literal读取，tools/shader_ieee_lean.py的分类型发射，proof/ShaderIeee/Model.lean的显式uint语义包装；增补tools/test_ieee.py、examples/ieee-bits及其手写证明、正式控制清单/runner，以及当前能力说明和证据。复用现有shader_packing.uint_literal时应按精确源码token和DXC值校验，不改旧函数语义。

没有全局配置、依赖更新或Unity工程改动；本片不删除旧模型/证明、不改变主实数CLI的默认意义。暂时保留旧入口是迁移阶段状态；完整二进制替代和旧案例逐项重新验收仍列为后续工作，不能长期双轨后宣布完成。

## 验收

1. 单元：真实DXC解析新增运算、hex边界、UINT_MAX回绕、比较/三元、helper/struct组合；错误混合类型和仍未开放的转换/资源要明确拒绝。
2. 固定DXC动态移位DXIL探针与至少0、31、32、33、UINT_MAX移位量的语义例子；有限例子不代替后续全称定理。
3. 实际两份HLSL的完整Lean证明：四个8位字段打包/拆包或掩码保持、动态移位等价变换、32位hash的结构等价改写、float位模式经helper/struct保存恢复。输入为任意原始binary32存储值，内部量化为uint；不把有限输入测试称全称证明。
4. 对应错误掩码/系数/移位改写真实到达Lean证明失败；继续通过原IEEE九项正式控制与19原型库检查，保留sorry/额外公理/伪造目标拒绝。
5. 跑全部Python单元；核心实数/Compute产品源未改时不重复旧83条长门禁，用源指纹核对及IEEE suite内核心回切确认隔离。任何公共源改动按影响扩大相关正式回归。
6. 独立实施审阅后记真实证据、提交推送。出现需要新profile、新公理、弱化等价或布局/错误政策改变时停止受影响部分并重新说明。

## 当前就绪切片：binary-bits-001@r1

本切片独立实施前审阅已通过，无阻塞；审阅额外核对了实际DXC移位探针，并要求落实高位uint比较、NaN/±0回归及任意uint的asuint(asfloat(u))逆定理，均属于上述验收。向用户展示具体范围后，才记录精确实施grant。用户最新“可以开始”授权推进二进制目标，但先前稿仅有Candidate；不伪造为此前已审阅具体接口。方向不再重新投票，只确认本次刚具体化的首片实施范围。
