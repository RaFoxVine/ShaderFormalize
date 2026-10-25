# 结构化 HLSL 执行证据

2026-10-25，规划授权提交31c43f0，实施从e157ad4的数值IR继续。当前使用入口以根README为准，本文件记录实际执行、修复与机器结果。

## 实际实现

shader_types.py解释DXC结构/字段身份和值类型；shader_frontend.py统一处理旧/新源码，按已解析的函数声明ID定位重载。内部结构体使用持久字段值，更新复制父路径，参数帧不捕获调用者局部。入口结构体叶映射完整路径，entry_layout保留名义类型/字段/semantic，shaderformalize逐项比较两侧接口。Lean语义与数学库版本没有改变；不存在输出拍平HLSL的交付物。

新增examples/structured原始、改写、故意错误的材质。原始以BuildSurface/EvaluateLighting/ShadeSurface组织，改写使用不同内部类型、函数划分和分配律；入口布局及uniform保持一致。Unity共享RunUnlit.cs通过明确模板替换项选择新例子，使用Structured.shader.template向main填入PSInput.geometry；资产在Assets/ShaderFormalizeStructured，与旧场景隔离。

## 初验及独立Q第一轮修复

实际DXC与数值回归55项初验通过，包括原39项。补充绑定上限、未调用helper未知节点检查后进入独立Q。Unity新例子初验PASSED：144输入组合、2304回读像素、容差1e-4、GPU/CPU最大误差2.6244463757763015e-07，错误材质差异0.9415104389190674；保存重载真实HDRP Camera StandardRequest两球各18232有色像素，对齐图像误差0。

Lean新材质初验PROVED，构建162.906s、独立检查61.594s，仅propext/Classical.choice/Quot.sound。此初验早于Q修复后的完整重跑，不替代最终验收。

Q第一轮指出：未消费/先覆盖的helper实参表达式会丢失normalize域要求；未调用helper内除法/未知intrinsic只凭节点kind被接受；1050次别名赋值使递归resolve_alias抛RecursionError。分别修复为helper实参每个数值叶都先留绑定、所有函数体静态检查具体操作/调用身份/转换、别名迭代追踪并合成分量选择。新增忽略/覆盖/结构体实参、未调用normalize不增加前提、未调用不支持操作、长别名链回归。修复属于原执行集的正确性要求，未改变数学模型。

Q第二轮进行中又指出同一静态责任的上下文遗漏：未调用helper仍能藏向量分量赋值或嵌套赋值。新增shader_validation.py，完整区分声明、语句、表达式、左值；静态/动态调用共用checked_call，声明共用validate_declaration。新增分量左值、嵌套赋值、/=、static局部及return后语句反例。Q独立执行24项纯前端structured测试通过，确认这些已报问题关闭。

同一复核还发现64个字段/16层深度本身无法限制共享类型DAG的指数展开。check_shape现缓存每种名义类型的深度与数值叶数，任何结构体超过4096叶在创建值之前明确拒绝。实测8^10叶的声明DAG、正常材质及按值复制三项定向检查0.233s通过，避免为极小源码做十亿次深度遍历。新增叶预算用例。为使最终统一结果完全对应最终代码，中间的两次验收在修复后停止；仅终止命令行已核实的本轮进程树，并检查其退出，不影响编辑器或用户VSCode的Lean进程。

## 最终验收状态

Q确认此前源码问题关闭后，完整命令65项回归及12项数学控制全部通过；旧lerp Unity也通过，但旧Unlit场景保存失败。Editor启动时恢复了已打开的UnlitComparison，Unity明确不允许另一个场景覆盖打开的路径。共享RunUnlit.cs现检查目标是否已加载，已加载时另存*.Validation.unity；替代也打开则GenerateUniqueAssetPath，不关闭或覆盖原场景，并报告requestedScenePath与实际scenePath。实际重试Unlit PASSED，使用UnlitComparison.Validation.unity，144数值、重载真实相机与对齐检查均通过。

Q进一步指出旧场景仍加载、两套球体同为layer30时可污染实际相机图像。直接设置Camera.scene在当前HDRP不足以隔离，新增隐藏本次两球的检查确实检出36464有色像素。修复为重载场景后用CalculateAvailableSceneCullingMask/SetSceneCullingMask给本次scene独立掩码，并设置camera.overrideSceneCullingMask。只改本次scene的运行状态，finally关闭，不改其它场景对象。Unlit/structured实际重跑均PASSED，sceneIsolation=true、isolationPixels=0，原数值/场景/对齐检查继续通过。

为满足单命令闭环，场景保存修复后再次执行完整命令。数学阶段运行期间补齐上述Unity隔离修复，并在Unity阶段开始前更新C#脚本哈希；确认除此脚本以外所有数学实现、证明、测试、模板和输入完全未变，分层检查时间记录在ignored artifacts/structured-layer-hash-validation.json。最终源码哈希在structured-final-source-hashes.json。输出保存在ignored artifacts/structured-full.log，先前失败日志保存在structured-full-before-scene-fix.log，数学通过摘要保存在structured-formal-before-scene-fix.json。独立Q第二轮正式结论及最终结果尚未确认，不将运行中标成完成。Unity使用既有6000.5.9f1工程，隐藏启动，无工具/包升级或VSCode环境调整。td doc-pending仍报告未注册，不初始化新TreeDive项目。

## 最终结果

最终完整命令exit0，末尾Demo passed：65项回归、12项控制全部通过；lerp/Unlit/structured三套Unity PASSED。structured正例PROVED，build38.5s、独立检查23.594s，仅三个允许公理；错误版UNPROVED，缺失域INVALID_INPUT。最终GPU/CPU误差2.6244463757763015e-07、对齐图像0、两球各18232像素、隔离污染0。源字节与GPU副本吻合，最终28个实现/输入/模板/证明文件与分层快照哈希一致。精简证据及实际图片在planning/evidence/structured-material-2026-10-25.json和structured-preview-2026-10-25.png。

独立Q第二轮正式通过，所有已报告问题关闭。Q后只更新文档、状态和证据审阅字段，没有实现变更；git diff --check通过。首次授权时间按31c43f0实际提交时间校正。本次本地提交保存实现和证据，不push，不正式归档；当前用法以README为准。依赖与运行缓存保持本地且由Git忽略，临时实验/失败日志保留作诊断，未删除用户资料。
