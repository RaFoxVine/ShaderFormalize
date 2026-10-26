# 扩展调查与后续工作状态

2026-10-26；当前只开展调查和提案，没有浮点/Compute 实现授权，未修改既有 sealed overnight。

| 工作 | 状态 | 产物或进入实现的条件 |
|---|---|---|
| 核实基础运算缺口 | Completed | 4 个固定 DXC/导入器探针，见 investigation.json |
| 从官方来源建立覆盖目录 | Completed（初版） | coverage.csv 共 203 行，名称/能力族不是全部重载 |
| 查找可复用的数值/GPU 验证工作 | Completed（资料调查） | research.md；未安装候选依赖、未复现论文 |
| 扩展路线与责任边界 | Candidate | plan.md；等待新语义范围讨论，独立审阅记录见下 |
| 基础运算实现 | Candidate | 按重载核实官方规则，指定全部消费者/文件迁移、定义域、正负控和旧证明兼容验收，独立 P 后呈现具体 Ready 范围 |
| 浮点库隔离评估 | Candidate | 固定候选提交、工具链、许可证、构建/公理与数值对照方案；依赖升级与默认语义变化单独审阅 |
| IEEE/HLSL 数值配置接入 | Outlined | 取决于评估；固定舍入、NaN/零位相等、融合/FTZ/近似运算等配置和报告保证 |
| Compute Load/Store | Outlined | 先明确语言/入口/资源底座及完整内存目标、别名契约和冲突负控 |
| groupshared/barrier/atomics | Outlined | 后端规则、阶段/允许执行语义和可核查安全证明桥接后再定实现 |

## 本轮证据与审阅

- 基线 `77a19dadcd1ab7df71f11d029474ecc9efc75da6`；产品源码未变。
- 调查探针：min/max/sqrt/division 全部 DXC accepted、转换器 UNSUPPORTED。具体诊断和官方页面内容哈希随 investigation.json 入库。
- binary32 重结合见证：Python struct 有限计算得 0 与 1；不是形式反证或 GPU 测试。
- 官方函数清单原始缓存与临时提取脚本在 ignored artifacts/；保留可审阅 CSV 和调查 JSON，不提交缓存/网页/下载依赖。
- 独立 P 首轮：研究与路线提案通过，可交用户讨论，不构成实现就绪或实现授权。关闭实数受限域与 HLSL INF/NaN 行为混淆；依建议细化矩阵覆盖说明和阶段来源链接。调查 JSON 另保留源码模板、四个表达式及完整 DXC/前端调用参数，供异机复查。
- 独立 P 第二轮针对性核对：上述三项修订均闭合，无新增问题；候选实现维持原状态。
- 未授权代码、工具链升级或新依赖安装；没有声称任何新产品能力已经完成。
