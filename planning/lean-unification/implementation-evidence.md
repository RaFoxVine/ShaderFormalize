# 执行与恢复

起点5275357，主目录D:/2FileBuildWorkPlace/Formalize/ShaderFormalize，codex/shader-equivalence-planning。前次301单元通过；83核心控制已有完整实测，本轮恢复核对414核心+50IEEE证据哈希。

三个C工作区的功能源码已合入主目录。唯一额外IEEE README已保存在artifacts/cleanup-20261028。basic-math两条指向D盘工具与包的junction已按精确目标检查后只删除链接本身；主目录14份工具/语义/manifest指纹保存在同目录primary-preflight.json。

Codex archive_worktree拒绝basic-math，实际错误为Another active task still uses this worktree。没有强制删除活动工作目录；改用用户允许的跨盘迁移，并保留原C路径的小型兼容junction。已开始basic-math迁移，exec session78630；后续目录和实际结果待记录。包含其它项目资料的C盘残留目录不在清理范围。

全局Worktree root已获准改E:/CodexWorktrees，现有清理策略保留。官方文档确认UI入口；所用Windows Computer Use技能禁止自动操作ChatGPT桌面UI，当前可用app工具也未提供设置写入能力。尚未声称全局设置已生效，已告知用户手动设置；源码调查确认本机设置来自persisted atom git-worktree-root，不会往config.toml虚构字段。

## 后续恢复状态

- 用户进一步要求本项目worktree全部删除后再调整全局根目录。basic-math跨盘搬迁完成；compute-texture的内容搬到E后，Windows因当前会话占用拒绝删除C原目录，操作未完整成功。没有把该失败记录为整体迁移成功。
- 改为保存三份本地源码快照引用后，逐个删除已核实的Git worktree；源码引用分别为refs/cleanup-snapshots/basic-math-20261028=ce5e8258c8d92251d8156963fefbcca099de2a45、compute-texture-20261028=9b5d2391a835850e77b3a23b6ca7f5d5682cc43c、ieee-prototype-20261028=24c2357f380a1f13e9488ed1c2b9e326a1e61db3。清理session12191已删除E的前两份实际worktree，正在删除C的IEEE；最终状态/源码快照JSON待核对。没有删除其它项目目录。
- 清除C兼容junction与E marker-only目录的组合命令在执行前被平台自动审批拒绝，只有blocked by policy无细节。未重试相同删除动作；C basic-math仅指向E marker目录，C compute-texture仅空壳/少量Git元数据，已向用户说明不能称为全部目录删除完成。C可用空间已从约13GiB增至27GiB，最终值仍待记录。不要对残余junction作递归清理。
- 原14份主环境指纹已确认无漂移后，解除writer的manifest/语义写入限制。root将旧proof/.lake/{packages,build}同盘移至.cache/lean-unification-20261028/{packages-4.24,build-4.24}，旧lakefile.olean*同处备份；原prototypes/ieee/.lake/packages已移动到唯一proof/.lake/packages。新mathlib和FloatLib HEAD分别56a005...、8c887...，没有重新复制工具或依赖。
- audit_ieee作为唯一migration writer，源码/PS语法和四个工具/锁/绑定回归已过；已发布唯一manifest并把Model/Probe移入proof/ShaderIeee，删除旧有效配置与FetchCache，统一bootstrap实际进行中，writer exec session42648，日志artifacts/lean-unification-bootstrap.log。根不再运行任何并发Lake writer。旧4.24安装和迁移备份尚未删除，必须等完整验收。
- 清理session12191完整结束：三份实际Git worktree都已删除，git worktree list仅剩D主目录，三份source snapshot引用已保存为artifacts/cleanup-20261028/source-snapshots.json。仅少量marker/junction/当前会话元数据未清理；最后已观察C可用28.29GiB，E95.9GiB。已明确通知用户可调整未来worktree根目录，不声称残余空壳已删净。
- 第一次统一bootstrap发现需要重下2069压缩缓存：4.35旧ltar尚在.cache/ieee/mathlib，而新位置夹有4.24归档。writer主动停止其进程树（42648 exit1，不作成功证据）；root将混合目录移至迁移备份archives-mixed-before-unification，再把2067个现有4.35 ltar同盘移到唯一.cache/mathlib。重启76080，日志artifacts/lean-unification-bootstrap-resume.log，最多仅需下载两项新根。没有把上游重新全面构建作为先决条件。
- 当前版本官方安装ZIP在主目录未保留（仅安装本体有固定哈希），root为后续干净目录复现重新获取同一个4.35 ZIP到.cache/downloads，使用现有分段下载器和官方固定SHA，日志artifacts/lean-unification-release-cache.log。缓存/依赖安装仍位于D工作目录，不写入C。
- 第二轮bootstrap已完成缓存：仅新增下载2项，2069依赖已复用/解包；4.35 BootstrapSmoke实际通过，Real.sqrt可加载，仅旧Mathlib导入别名弃用警告。随后标准Lake布局补编FloatLib所需依赖，writer最近报告2234/2397、无错误。原包根lib/ir旧输出保留到新构建全部验证后清理；不在活动编译时重排缓存。
- 只读预检发现P2：新probe为兼容真实二进制替换测试把工具校验置于锁前，ENV失败可在未获锁时覆盖active owner报告。已修复先获锁后校验/写报告，busy不覆盖；二进制负控改为临时脚本/锁/两exe副本fixture。writer三项实测11.638秒通过，audit_sync独立三项8.092秒Verified，日志artifacts/review-ieee-probe-ownership-q.log；这不是完整迁移Q。
- 验证分工：writer只完成bootstrap、核心→IEEE→19原型烟测和必要单元后交付源码静止；完整全部单元/83核心/9IEEE及干净目录复现由root接管，避免单个agent turn两小时时限中断长门禁。没有将当前构建进度当成迁移完成。

## 2026-10-29 迁移验收接续

- 统一bootstrap session76080已exit0，2397项构建全部成功；ShaderIeee.Model/Probe实编通过，原型两条定理依赖仅三公理白名单。日志artifacts/lean-unification-bootstrap-resume.log。writer开始核心真实check，后续IEEE与原型检查尚待完成。
- 官方4.35安装ZIP分段续传session40299已exit0：216/216、902262322字节、SHA256=5fc033e93e1a7bc59c5ebf311103d2c9cd18d4b3eddda4ffa3414e8adb0ef79e；保留.cache/downloads当前安装归档，不重下。第一次下载超时未当成功。DXC ZIP也已从旧Fresh Checkout按根锁校验后复制到根.cache/downloads，避免删除旧临时目录时丢失当前归档。
- root创建独立E:/CodexValidation/ShaderFormalize-lean435-20261029用于复现，Git clone无hardlink；包源及固定版本标准构建/压缩缓存为独立副本，不用junction、不复制项目生成或Submitted/Verify及其编译缓存。缓存复制session97779已exit0。此验证是带已固定上游缓存的新checkout复现，不宣称再次从零编译全部上游。
- 原始目标只读复核：两份HLSL→完整数学目标→手写证明→目标绑定/公理审计已有闭环；Vertex尚无正式入口，完整HDRP/Lit Forward只有固定源码提取及调用结构分析，尚未生成目标。已修正HDRP当前说明：IEEE路线已建立，后续是实际语言/资源组合接入，不再把是否建立IEEE列为未决；历史决策原文单独保留。此文档修订不授予新Shader功能实施权。
