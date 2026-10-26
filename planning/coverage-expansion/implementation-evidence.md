# 并行扩展执行记录

本文件用于中断恢复与追溯，只记录实际发生的工作。范围及授权分别见parallel-plan.md、execution-authority.md；本轮采用用户指定的“信任上游声明、代表性接入检查”策略，不开展完整外部审计。

## 当前恢复入口（2026-10-27）

- 主目录：D:/2FileBuildWorkPlace/Formalize/ShaderFormalize，分支codex/shader-equivalence-planning。
- c3a2297：本批委派、切片与精确授权；新Session shader-expansion-parallel-2026-10-26，封存hash见authority。
- c401924：固定VerCors2.4本地接入及实际并行/barrier正负例。4项PASSED，独立Q1 Verified；入库证据../evidence/vercors-integration-2026-10-27.json。
- 563955a：数学与实验性Compute源码及统一runner；独立审阅通过，最终完整验收已完成，242单元/69控制=32P/35U/2INVALID。
- 主目录初次验收`pwsh -NoProfile -File tools/run_demo.ps1`（原session58689）因DXC缺失中断，已完成242单元及39控制。原失败摘要/日志保留artifacts/acceptance-interrupted-20261027。固定DXC恢复及核心Lean smoke通过后，核心源码无变化，独立恢复审阅Verified；ignored helper artifacts/resume-parallel-acceptance.py实际完成剩余30控制（session61456 exit0），日志artifacts/parallel-core-resume.log，最终artifacts/acceptance/result.json为PASSED并显式保存39+30中断上下文。
- ignored helper `python artifacts/record-parallel-evidence.py`已实际运行，只接受PASSED统一摘要，核对目标/输入/证明/语义/公理日志后生成../evidence/parallel-expansion-2026-10-27.json。该JSON保存代码、报告、原中断及续跑日志hash，未把单次失败伪装成无中断通过。

## 数学切片

实现worktree C:/Users/xc/.codex/worktrees/basic-math/ShaderFormalize，数学agent已冻结代码。28个文件逐一检查主目录无漂移后回拷，清单artifacts/math-integration-files.json，隔离证据复制到artifacts/basic-math-isolated。

独立IEEE agent Q1 Verified：14新单元及structured26/source25/control19旧单元通过；3完整正例PROVED、3负控UNPROVED；27旧正例从原捕获DXC AST重新导入，生成目标逐字不变，未把这称为重跑旧Lean。无新Lean语义模块或核心依赖升级。主目录统一gate再次实际完成了相同六个控制。

## Compute切片

实现worktree C:/Users/xc/.codex/worktrees/compute-load-store/ShaderFormalize，源码已冻结；19个新文件回拷主目录并入563955a，清单artifacts/compute-integration-files.json。其余共享数学源码未由Compute agent修改。

15项最终独立有限回归通过。首轮两正四负完整控制通过，数学agent独立Q1代码/证据审阅通过。中途修正了顺序if后alive的SSA共享，避免mask指数复制；因此对受影响的生成目标作重建比对和针对性补检，而非沿用旧目标hash。子目录最后OOB补检由root明确终止并标为INCONCLUSIVE，由主目录接手。当前主目录六项均已实际完成两PROVED/四UNPROVED；独立Q2 Verified：从六份最终捕获AST重生成后，模型及Lean目标与实际检查快照逐字相同，输入/证明/语义/公理日志吻合，公共runner状态修复通过核对。该Q还检查了六个新数学控制及242单位结果，未提前覆盖旧57控制的最终验收。

首期模型统一物理资源identity，保留线程内顺序overlay及最后已执行Store；范围与跨线程WW/WR为完整待证结论。根给run_compute_suite.py补了启动IN_PROGRESS与单位失败FAILED，防止残留上次成功摘要；没有改变其生成语义。

## 浮点接入切片

实现worktree C:/Users/xc/.codex/worktrees/ieee-prototype/ShaderFormalize。固定FloatLib8c8871576a941a86e73dcf0882702b823139aa93、独立Lean4.35、10个manifest依赖；不改核心4.24和锁。900MB官方ZIP已实际完整下载并核SHA，2067份所需Mathlib缓存已取得；2396/2396构建任务成功，两条调用上游定理的本地证明仅三项标准公理，19项运行检查实际通过，报告EXTERNAL_LIBRARY_PROTOTYPE_PASSED。它不是HLSL自动浮点转换。

Compute agent独立Q1 Verified，核对了实际报告/日志/依赖固定性。两处自己的脚本问题已修复并用失败fixture核对：异常重跑覆盖旧PASSED；切换依赖HEAD前后拒绝tracked dirty。未审计/重证整个FloatLib。工具/包缓存已回迁主目录，省略重复download_ranges.py并改为公共tools/download_release.py；D实际热跑19项通过，独立Q2核对12文件/helper、实际报告哈希、公理及本地工具版本后Verified。提交8372a6e，入库证据../evidence/ieee-integration-2026-10-27.json。

## 环境与实际修复

数学/Compute worktree只读复用主目录工具及mathlib包junction，独立写各自生成目标/项目构建目录，这不是独立依赖安装。首次两边的lake build曾因新增tactic导入触发共享mathlib编译缓存写入；包源码/锁未改。停止各自进程后，数学改用已有定理/缓存，Compute改逐模块`lake env lean -o ...`并缩窄import，后续不再并发补编共享依赖。

GitHub单连接下载实测很慢，改用最多8连接的校验Range下载，最后仍验证完整官方SHA；工具在tools/download_release.py。VerCors固定release实际launcher位于解压根目录vercors.bat，参数为`--backend silicon`。PVL的run是保留字，示例方法最终使用execute。早期路径、选项、解析失败均未算作正例或权限负例通过；最后四次实际成功/拒绝与Q证据吻合。

## 临时worktree清理中断与恢复

Compute隔离证据先保留到主目录artifacts/compute-isolated。手动移除临时junction的命令被自动审批拒绝，未执行；随后调用内置archive_worktree，Compute临时checkout已归档。紧接着主目录DXC消失，导致control-mixed环境失败。时间关系与共享.tools junction有关，但没有工具内部日志证明具体删除路径，原因未完全确定。其余临时worktree暂停清理，不再次对含共享junction的目录执行归档。

恢复使用既有独立Windows副本的官方DXC压缩包，完整SHA及三个binary均与核心锁一致；核心Lean/lake二进制也匹配，BootstrapSmoke实际exit0；独立Lean4.35文件总数和体积仍与迁移前完全一致。源码、已有报告和证明快照无改动。恢复审阅另外对中断前未纳入组摘要的五个control例，从捕获AST重生成，目标逐字相同。已完成39个控制可复用，剩余30个必须实际续跑；最终摘要保留中断事实。不要把初次失败日志改写成单次全通过。

本批实际续跑已完成，收尾证据审阅后结束Session并推送。必要IEEE环境保留主目录；基础数学与IEEE临时worktree暂留，下一批先做源快照再复用，不归档这些共享链接。用户已明确批准下一轮四项Overnight，计划在../overnight-expansion-2026-10-27/。未执行merge、正式H-X或Node归档。
