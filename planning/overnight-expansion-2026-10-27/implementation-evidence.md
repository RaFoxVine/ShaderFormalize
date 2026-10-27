# 本夜执行记录

本夜范围、语义、接口与文件所有权见plan.md；授权见execution-authority.md。用户已明确批准四项Overnight，无需等待逐项人类确认。新Session已running，封存hash见authority，旧Session完整结束记录保存在planning/overnight/deprecate/shader-expansion-parallel-2026-10-26-20261027-020807.md。

## 当前恢复入口

- 主目录D:/2FileBuildWorkPlace/Formalize/ShaderFormalize，工作分支codex/shader-equivalence-planning。
- d3b7f5f已推送：上批最终242单元、69控制（32P/35U/2INVALID）及独立最终证据Q通过；39+30恢复记录真实保留。
- 8a13f50：新Session/委派/Frame/Math-Compute-Sync精确Grant在代码前提交；IEEE P随后已闭合固定工具预期启动校验，新增ieee-hlsl-001和root共同检查提取合同在其代码前提交。
- Math复用C:/Users/xc/.codex/worktrees/basic-math/ShaderFormalize；root逐文件验证旧28源文件与主目录相同，作本地恢复snapshot b27f399，再checkout d3b7f5f，tracked clean。ignored依赖/旧证据未删除。现由数学agent独占其指定代码文件。
- Compute新managed worktree已完成：C:/Users/xc/.codex/worktrees/compute-texture/ShaderFormalize，d3b7f5f基线。root物理复制4.24工具2.28GiB/DXC与包缓存1.55GiB，session64605，日志artifacts/compute-texture-environment.log；C盘准备前可用11.62GiB。源码可由Compute writer实施，但复制完成前不要运行Lean/bootstrap/cache。
- IEEE原型C checkout已保存本地恢复snapshot5067283后checkout d3b7f5f，tracked clean；ignored4.35/FloatLib缓存保留，另物理复制自身DXC。P已Verified，精确Grant派生后等待root交付共同API再开工；D主目录环境完整保留。

所有shell调用显式使用相应workdir，根负责主目录。不要对含共享junction的临时checkout做内置归档；此前具体事故和恢复见上一批implementation-evidence.md。当前工具/包均为已验证版本，不要求重新下载或全面上游审计。

## 接管后的并行恢复

- 新三个coder分别接管Math、Compute和IEEE原工作区，保留未提交改动，不提交/推送；root继续主目录同步入口、公共API和最终整合。独立同步Q另行只读审阅。
- root公共检查提取`proof_contract.py`已机械交付IEEE工作区。主目录实际242项旧单元通过；lerp完整DXC/Lean检查PROVED，三标准公理，见artifacts/handoff-smoke/lerp。
- HLSL同步入口新增`shader_sync.py`、`syncformalize.py`、`run_sync_suite.py`和固定两线程例子。首次正例因par结束权限形状不完整被VerCors拒绝；随后按是否有真实barrier分别恢复own/neighbor权限，正例通过，删barrier不保留重分配。
- 同步11项单元通过，覆盖AST事件、显式uint32模、barrier权限、alias/容量拒绝、报告哈希和Java环境错误。`python tools/run_sync_suite.py`实际结果：original EXTERNAL_SAFETY_VERIFIED；missing-barrier与shared-conflict均为EXTERNAL_SAFETY_UNPROVED且日志含真实insufficient permission；aliased-contract UNSUPPORTED。报告在artifacts/synchronization-hlsl/acceptance。
- 主目录全量单元在新增9项同步测试时为251项通过；加入2项报告/环境测试后为253项，最终统一回归和独立Q结果待记录，不以较早计数代替最终结果。
- 独立同步Q1为CHANGES_REQUESTED：arrayBounds误报ENVIRONMENT_ERROR、两输入触发StopIteration并遗留IN_PROGRESS、锁后timeout不覆盖终态、解压VerCors未与锁ZIP逐文件核对。root逐项修复并增加两输入/两输出、timeout、锁竞争、ZIP漂移单元及真实越界控制。
- 修复后15项同步单元和257项总单元实际通过；同步suite五项控制全符合：正例VERIFIED、删barrier/冲突权限UNPROVED、越界arrayBounds UNPROVED、alias UNSUPPORTED。安装目录597个文件逐项与锁定ZIP的大小和SHA256一致。
- 独立Q2实际复跑15/257单元、核对41项产物哈希、直接复测两输入和timeout，并调用真实597文件payload比对， verdict PASS，四项Q1 finding全部闭合，无新critical/major。精简证据为planning/evidence/synchronization-hlsl-2026-10-28.json。
