# 扩展调查与后续工作状态

2026-10-26；调查后用户已明确要求四方向并行推进，并要求信任外部工具/论文声明、以代表性接入检查前进。新执行范围见parallel-plan.md及execution-authority.md；旧sealed overnight不授权本轮，新Session另行封存当前指示。

| 工作 | 状态 | 产物或进入实现的条件 |
|---|---|---|
| 核实基础运算缺口 | Completed | 4 个固定 DXC/导入器探针，见 investigation.json |
| 从官方来源建立覆盖目录 | Completed（初版） | coverage.csv 共 203 行，名称/能力族不是全部重载 |
| 查找可复用的数值/GPU 验证工作 | Completed（资料调查） | research.md；未安装候选依赖、未复现论文 |
| 扩展路线与责任边界 | Approved（本批范围） | parallel-plan.md；三个独立worktree、根agent集成；交叉P通过 |
| 基础运算实现 | Approved | parallel-plan数学切片；浮点agent独立P2通过，精确授权见execution-authority.md |
| 浮点库隔离接入 | Approved | 固定FloatLib/Lean4.35独立原型；Compute agent独立P通过，不改核心锁 |
| IEEE/HLSL 数值配置接入 | Outlined | 取决于评估；固定舍入、NaN/零位相等、融合/FTZ/近似运算等配置和报告保证 |
| Compute Load/Store | Approved（首个切片） | 1D StructuredBuffer首例和独立命令；同线程overlay/物理alias/完整状态与安全目标，数学agent独立P2通过 |
| 并行/同步外部工具接入 | Approved | 本地VerCors和代表并行正负例；不冒充HLSL同步自动导入或Lean证明 |
| groupshared/barrier/atomics | Outlined | 后端规则、阶段/允许执行语义和可核查安全证明桥接后再定实现 |

## 本轮证据与审阅

- 基线 `77a19dadcd1ab7df71f11d029474ecc9efc75da6`；产品源码未变。
- 调查探针：min/max/sqrt/division 全部 DXC accepted、转换器 UNSUPPORTED。具体诊断和官方页面内容哈希随 investigation.json 入库。
- binary32 重结合见证：Python struct 有限计算得 0 与 1；不是形式反证或 GPU 测试。
- 官方函数清单原始缓存与临时提取脚本在 ignored artifacts/；保留可审阅 CSV 和调查 JSON，不提交缓存/网页/下载依赖。
- 独立 P 首轮：研究与路线提案通过，可交用户讨论，不构成实现就绪或实现授权。关闭实数受限域与 HLSL INF/NaN 行为混淆；依建议细化矩阵覆盖说明和阶段来源链接。调查 JSON 另保留源码模板、四个表达式及完整 DXC/前端调用参数，供异机复查。
- 独立 P 第二轮针对性核对：上述三项修订均闭合，无新增问题；候选实现维持原状态。
- 上述“未授权实现”是调查阶段历史状态；当前新增精确范围由用户后续并行指示派生并持久化。核心工具链升级仍不在本批内；新产品能力需以实际结果为准。
