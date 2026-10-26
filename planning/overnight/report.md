# Overnight结果：普通Shader语言链路已跑通，完整Lit保留语义阻断

仓库现在能把两份正常写法的HLSL交给DXC解析，再转换为Lean的实数/精确uint模型，供agent提交并检查等价证明。Unity仍只是可选开发集成，核心安装、转换、证明和默认回归不依赖它。

新增共享函数定义、默认参数、out/inout、矩阵、定长数组、元素写回，以及固定次数uint for。组合示例examples/complete包含结构体、UV矩阵、光源数组、输出数组、法线归一化、平方边缘光、采样、clip和两次循环中的ddx/光照累积；原版与手工展开版的完整目标已经Lean证明，量化任意输入场和相同的采样/导数操作，不靠有限采样代替证明。

完整核心实际通过213项单元和57项正式控制：27 PROVED、28 UNPROVED、2 INVALID_INPUT，全部符合预期。错误系数、真正执行normalize(0)、未执行非法计算，以及旧功能都包含在控制中。独立审阅通过，旧25个正例的模型和目标文字保持兼容。源码为d348566；精简证据在planning/evidence/static-loops-2026-10-26.json，矩阵阶段证据另有aggregate-2026-10-26.json。初期两处证明脚本错误及失败目标保留，未修改数学保证来绕过失败。

| Overnight项 | 实际结果 |
|---|---|
| 整数打包 | 完成，源9df384c；最终回归继续覆盖 |
| 普通语言与组合材质 | 完成，源d348566，213/57及独立审阅通过 |
| 固定HDRP/Lit Forward | Blocked at decision，完整源码尚未转换/证明 |
| Windows x64复现 | 完成：原空目录真实安装固定依赖，后续独立副本更新到d348566，两新正例PROVED并经事实核验 |
| Git发布 | 待最终推送并核对远端SHA |

完整Lit的阻断不是精度问题：反射探针球形求交会对负判别式求平方根，再用IsNaN恢复无交点结果；纯实数模型无法直接表示这段行为。不能把IsNaN改成false或悄悄增加判别式非负假设。可复现的小例、实际静态路径和恢复条件在planning/hdrp-forward/real-boundary.md。下一轮须确定是否先选择并证明不执行这条路径的固定配置，或明确异常恢复的数学契约；其余入口、资源、动态循环等缺口仍须随后处理。

循环目前限于静态常量边界的uint for，单循环最多64次、每函数总展开4096步，超过预算拒绝，不做fuel截断；符号边界、while/do、break/continue等尚未支持。新组合示例没有Unity/GPU验证，转换器与DXC仍在可信边界中，没有证明转换器自身正确。没有引入IEEE浮点编码或新公理。

另一台Windows x64按docs/windows-setup.md拉取codex/shader-equivalence-planning并执行本地bootstrap；快速检查新示例可用`pwsh -File tools/run_demo.ps1 -Example complete`，完整回归用默认run_demo。工具和依赖位于仓库本地的.tools/.cache/proof/.lake；缓存、完整日志、开发副本和Unity工程不进入Git，保留本地失败证据供恢复，不需要为发布删除它们。独立副本是同一台机器上隔离安装依赖的验证，没有声称已经在另一台物理电脑实测。

没有进行merge、rebase、force push、正式归档或机器全局配置变更。当前普通语言工作已闭合；完整Forward的下一步需上述语义选择。
