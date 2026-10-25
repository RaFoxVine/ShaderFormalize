# 本轮执行授权

- status: active
- source: direct_user
- node_frame: planning/fragment-effects/plan.md，修订1，sha256 4cc7b86729ff7d8910aec8312078cb1ec65c696694385c740b9432181b0d5073
- target_slices: tasks.md 两项 Approved，全体完成共同交付纹理/裁剪/导数正常Shader验证。
- authorization_message_exact: “OK，那么我们继续，接下来把纹理采样、裁剪和导数这些语义加进去，还是先找一个正常写法的 Shader，把原版和等价改写版的验证跑通。”
- authorization_basis: 本条明确指定功能，且此前“完整的方案……不需要，先把东西跑通再说”豁免独立人工完整方案审阅；独立P第一轮确认设计可执行。用户指令优先于skill额外审批要求。
- allowed_actions: 范围内代码/测试、固定本地工具、现有Unity工程内独立演示资产/场景及GPU验证、独立Q、文档证据、本地Git提交。
- exclusions: push/发布、依赖升级、新全局配置、修改已有场景/旧例子行为、HDRP/Lit源码提取、quad模拟、删除用户资料、正式归档。
- stop_conditions: 实数/共享抽象操作模型需改变；范围外依赖或关键GPU oracle不可用而无等效证据。
- acceptance_boundary: 实际机器证据和独立Q交付；人工H-X另行发生。
- delegated_session: none
- recorded_at_local: 2026-10-25T18:11:36.8091500+08:00
- state_reason: 用户已授权实施；独立P通过；由根agent唯一写入。
