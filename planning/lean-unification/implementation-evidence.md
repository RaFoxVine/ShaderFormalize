# 执行与恢复

起点5275357，主目录D:/2FileBuildWorkPlace/Formalize/ShaderFormalize，codex/shader-equivalence-planning。前次301单元通过；83核心控制已有完整实测，本轮恢复核对414核心+50IEEE证据哈希。

三个C工作区的功能源码已合入主目录。唯一额外IEEE README已保存在artifacts/cleanup-20261028。basic-math两条指向D盘工具与包的junction已按精确目标检查后只删除链接本身；主目录14份工具/语义/manifest指纹保存在同目录primary-preflight.json。

Codex archive_worktree拒绝basic-math，实际错误为Another active task still uses this worktree。没有强制删除活动工作目录；改用用户允许的跨盘迁移，并保留原C路径的小型兼容junction。已开始basic-math迁移，exec session78630；后续目录和实际结果待记录。包含其它项目资料的C盘残留目录不在清理范围。

全局Worktree root已获准改E:/CodexWorktrees，现有清理策略保留。官方文档确认UI入口；所用Windows Computer Use技能禁止自动操作ChatGPT桌面UI，当前可用app工具也未提供设置写入能力。尚未声称全局设置已生效，已告知用户手动设置；源码调查确认本机设置来自persisted atom git-worktree-root，不会往config.toml虚构字段。
