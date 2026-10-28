# 扩展调查与后续工作状态

2026-10-26；调查后用户已明确要求四方向并行推进，并要求信任外部工具/论文声明、以代表性接入检查前进。新执行范围见parallel-plan.md及execution-authority.md；旧sealed overnight不授权本轮，新Session另行封存当前指示。

| 工作 | 状态 | 产物或进入实现的条件 |
|---|---|---|
| 核实基础运算缺口 | Completed | 4 个固定 DXC/导入器探针，见 investigation.json |
| 从官方来源建立覆盖目录 | Completed（初版） | coverage.csv 共 203 行，名称/能力族不是全部重载 |
| 查找可复用的数值/GPU 验证工作 | Completed（资料调查） | research.md保留调查阶段记录；后续实际接入见浮点/同步切片 |
| 扩展路线与责任边界 | Approved（本批范围） | parallel-plan.md；三个独立worktree、根agent集成；交叉P通过 |
| 基础运算实现 | Completed | 563955a，独立Q1及整合Q2 Verified；最终242单元/69正式控制符合预期，新数学3P3U；中断39项保留、30项实际续跑，见../evidence/parallel-expansion-2026-10-27.json |
| 浮点库隔离接入 | Completed | 8372a6e；2396项构建、19项运行检查、两定理通过，主目录迁移热跑及独立Q2 Verified，不改核心锁；见../evidence/ieee-integration-2026-10-27.json |
| IEEE/HLSL 数值配置接入 | Completed | 65f8fc8；独立binary32逐运算RNE、保留subnormal/NaN/±0、完整存储位相等，3P6U及Q2 VERIFIED；gpu_profile_matched=false；见../evidence/ieee-hlsl-2026-10-28.json |
| Compute Load/Store | Completed | 563955a；主目录2正4负正式控制及15独立有限回归通过，目标重生成逐字相同，独立Q2 Verified；最终完整69控制符合预期 |
| 二维Texture Compute | Completed | add3f17；schema2精确整数坐标、纯helper、OOB Load、独立Store边界和最终内存，27单元及新3P5U旧2P4U通过；见../evidence/compute-texture-2026-10-28.json |
| 七项实数数学 | Completed | 274523c；floor/ceil/frac/step/smoothstep/cross/reflect，主目录3P3U及独立Q通过，27旧目标逐字一致；见../evidence/math-extensions-2026-10-28.json |
| 并行/同步外部工具接入 | Completed | c401924；本地VerCors实际2正例通过/2权限负例拒绝，独立Q1 Verified；入库证据../evidence/vercors-integration-2026-10-27.json；不冒充HLSL同步导入或Lean证明 |
| groupshared/barrier/atomics | Completed（固定子集） | 6f02a08；固定两线程HLSL→PVL访问安全，15单元及五控制、Q2 PASS；atomics/Wave仍排除；见../evidence/synchronization-hlsl-2026-10-28.json |

## 调查阶段证据与审阅（实现前）

- 以下为实现前调查记录，基线 `77a19dadcd1ab7df71f11d029474ecc9efc75da6`；当时产品源码未变。
- 调查探针：min/max/sqrt/division 全部 DXC accepted、转换器 UNSUPPORTED。具体诊断和官方页面内容哈希随 investigation.json 入库。
- binary32 重结合见证：Python struct 有限计算得 0 与 1；不是形式反证或 GPU 测试。
- 官方函数清单原始缓存与临时提取脚本在 ignored artifacts/；保留可审阅 CSV 和调查 JSON，不提交缓存/网页/下载依赖。
- 独立 P 首轮：研究与路线提案通过，可交用户讨论，不构成实现就绪或实现授权。关闭实数受限域与 HLSL INF/NaN 行为混淆；依建议细化矩阵覆盖说明和阶段来源链接。调查 JSON 另保留源码模板、四个表达式及完整 DXC/前端调用参数，供异机复查。
- 独立 P 第二轮针对性核对：上述三项修订均闭合，无新增问题；候选实现维持原状态。
- 上述“未授权实现”是调查阶段历史状态；当前新增精确范围由用户后续并行指示派生并持久化。核心工具链升级仍不在本批内；新产品能力需以实际结果为准。

## 后续

用户已批准下一夜四项委派：七项数学、HLSL IEEE入口、二维纹理Compute、HLSL同步安全入口。其具体Frame及状态另见../overnight-expansion-2026-10-27/plan.md与tasks.md，本批完成不自动宣称这些能力已实现。临时worktree清理因共享链接安全问题暂缓，主目录工具已恢复，具体经过见implementation-evidence.md。
