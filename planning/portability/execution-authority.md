# Grant windows-fresh-001

- status: completed
- source: delegated_session
- node_frame: planning/portability/plan.md修订2，独立P第二轮Ready，2026-10-26。
- target_slices: Windows x64干净目录复现、既有安装流程自包含修复、启动指南和实际证据。
- authorization_message_exact: “接下来我们要执行 overnight 了”；“明天的话，我可能会在别的地方使用我们这里的仓库”；用户另确认“仍是 Windows x64”。
- unique_referent_evidence: 该项已在overnight范围中展示，用户持续免重复方案人工审阅，sealed portability条目明确PLAN_AND_CODE。
- authorization_basis: 当前running Session的portability ceiling内，经独立P两轮关闭环境隔离/缓存失败问题后派生；不修改数学语义或依赖版本。
- recorded_at_local: 2026-10-26T01:52:00+08:00
- allowed_actions: 方案内bootstrap/进程环境/缓存wrapper修复、受控回归、专属干净clone/固定依赖真实下载、两例正式证明、独立Q、指南/证据、本地提交。
- exclusions: 本项不push、无merge/archive、无机器全局修改、无依赖升级、不删用户文件、不改数学保证、不隐式依赖Unity。
- stop_conditions: 需要改变数学/状态/平台/版本保证；无法取得锁定依赖且缺关键oracle；独立Q关键问题三轮未闭合。
- acceptance_boundary: 含本项修复的精确源码版本在空环境bootstrap成功、lerp/packed PROVED及审计；原checkout全核心验收另属packing；完成后交publish处理。
- delegated_session: planning/overnight/current.md；shader-forward-2026-10-26；item portability；sealed envelope sha256 afcc1f80b2eb30be69411cd4633dc9d8ac79b0b918eaaf4302fc76ae66188206；plan revision2/P2 passed。
- state_reason: 69d058a在真正空目录重建依赖后，两正式正例通过；129单元/缓存缺失控制/导入检查通过，独立Q第二轮Verified，当前指南和精简证据完成。
- superseded_by: none

## Grant windows-refresh-002@revision-1

- status: completed
- source: delegated_session；同一sealed portability目标内的追加验证，不改产品代码/配置/版本。
- target: 已在空目录真实下载/安装并Q2验证的artifacts/portability/Fresh Checkout，从69d058a安全更新到当前源码2fc87bb；依赖两锁须完全相同，复用该副本自己的已验证工具/缓存，不从主目录复制构建物。
- actions: 先确认tracked状态为空；fetch本地Git源码并detach已知提交；核对锁/工具/九依赖/无alternates/无Unity及子进程环境隔离；检查shared材质、helper完整场与packed正例；保存独立结果/哈希/状态，不覆盖原69d fresh证据。
- authorization: 用户要求另一处Windows x64取得最新可用仓库；已有免重复方案审阅及running session的PLAN_AND_CODE授权。既有Ready环境/隔离方案不变，本项仅测试源码后续提交，轻量自查即可，无新增实现。
- exclusions: 重装/升级依赖、机器配置、删除、污染主proof工作区、push/merge/archive。
- stop: 副本有tracked改动、两锁变化、工具/依赖核验失败、外部环境/Unity渗入、形式检查失败。
- recorded_at: 2026-10-26；源码最终shared Q/41控制仍独立进行，不以追加复现替代。
- result: 副本2fc87bb三例PROVED、Git前后clean；独立事实复核通过。六工具文件/九依赖/两锁匹配，无alternates/Unity。见../evidence/windows-shared-2026-10-26.json；不覆盖5961f8e/b074163错误路径补丁，不称为第二次空目录安装。

## Grant windows-refresh-003@revision-1

- status: completed
- source: 同一sealed running overnight portability目标内的追加源码验证，既有Ready隔离协议不变，无产品/配置/依赖变更。
- target: 已有独立Fresh Checkout由2fc87bb更新到64992ea；只fetch Git源码，复用副本自身固定工具/缓存。不得复制主目录工具或proof产物。
- actions: 状态干净后detach确切64992ea，逐项核对两锁/六工具/九依赖/无alternates/无Unity/子环境隔离；分别运行copyback材质、copyback完整场导数、packed三个正式正例；另存fresh-copyback-verification及对应日志，不覆盖之前两次记录；事实复核、精简证据和本地提交。
- authorization: 用户明确明天在另一台Windows x64拉取最新仓库；免重复人工审阅和portability委派持续有效。此项沿用已P/Q通过的同锁追加复现步骤，仅目标源码和正例变化，轻量自查。
- exclusions: 产品代码/版本/全局配置/Unity改动、复制构建物、主proof工作区写入、删除、push/merge/archive。
- stop: 副本有tracked变更、锁/工具/依赖不匹配、环境污染或形式正例失败。
- acceptance: 三例实际PROVED、哈希和审计核验、Git前后clean；独立事实复核，不替代主目录165/47及copyback Q。
- recorded_at: 2026-10-26；代码64992ea已提交，主目录最终全套仍在运行。
- result: 64992ea三正例实际PROVED，前后Git clean；独立事实核验通过，同锁/六工具/九依赖/无alternates/隔离/无Unity及输入/目标/证明/数学模块/公理均吻合。见../evidence/windows-copyback-2026-10-26.json；不称为第二次真空安装。

## Grant windows-refresh-004@revision-1

- status: completed
- source: 同一sealed running overnight portability条目的最新源码追加验证；沿用已P/Q通过的独立同锁协议，无产品或配置变更。
- target: 独立Fresh Checkout由64992ea更新到9bec4aa，只fetch Git源码，使用副本自身原始下载的工具/缓存。主目录完整190/53验收另行串行，不共享生成文件。
- actions: 干净状态后detach确切9bec4aa；核对两锁/六工具/九依赖/无alternates及隔离/无Unity；实际检查aggregate材质、完整场导数、合法下标三个正例；另存fresh-aggregate-verification及日志、独立事实复核、精简证据和本地提交。
- exclusions: 从主目录复制工具或构建物、升级/重装依赖、全局/Unity改动、删除用户数据、push/merge/archive。
- stop: 副本dirty、锁/工具/依赖或隔离不匹配、形式正例失败。
- acceptance: 三例实际PROVED及输入/目标/证明/模块/公理核对、前后clean；只称同锁追加源码复现，保留原真空安装和前两次记录。不替代aggregate完整Q或主验收。
- recorded_at: 2026-10-26；数学语义与依赖锁没有漂移，复用已Ready验证步骤，仅换确切源码和覆盖正例。

- result: 9bec4aa三个正例实际PROVED，前后clean；独立事实复核通过，输入/目标/证明/四数学模块/manifest/DXC及标准三项公理吻合。副本锁原始哈希与其原安装基线一致；主副本CRLF/LF不同而JSON内容一致。见../evidence/windows-aggregate-2026-10-26.json；不替代主190/53或aggregate最终Q。

## Grant windows-refresh-005@revision-1

- status: active
- source: running sealed overnight portability条目；用户要求另一台Windows x64拉取最新可用源码，持续免重复方案人工审阅。同锁追加验证协议沿用已P/Q及事实核验通过的004，仅改变源码和两个覆盖正例，无产品/配置/依赖变更。
- target: 独立Fresh Checkout从9bec4aa更新至d34856609b7a897c093314bc497606d9f6a369d1；使用副本原安装的固定工具/缓存，不复制主目录依赖或构建物。
- actions: clean后fetch确切提交并detach，核对两锁/六工具/九依赖/无alternates/无Unity及子环境隔离；实际检查complete组合材质和loop-domain-zero两个正例，另存fresh-loop-verification.json与日志，独立事实复核、精简证据和本地提交。
- exclusions: 主proof工作区写入、全局/Unity改动、依赖更新/重装、复制工具或build、删除用户数据、push/merge/archive。
- stop: tracked状态dirty、锁/工具/依赖/隔离不匹配，或形式正例失败。
- acceptance: 两个实际PROVED、输入/目标/证明/模块/锁/公理核验和前后clean；只称同锁源码追加复现，不替代主213/57或loop最终Q，不是第二次空目录安装。
- recorded_at: 2026-10-26；d348566已有213单元和四新正式控制符合预期、Q1源码审读，主完整57及最终Q另行继续。脚本artifacts/portability/fresh_loop_verify.py沿既有协议生成，尚未执行。
