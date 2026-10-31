# 当前工作

| 工作 | 状态 | 实际结果 / 剩余事项 |
|---|---|---|
| 统一方案与独立P | Completed | 现有4.35、单workspace/包、隔离模块与共享锁、缓存API迁移已确定 |
| 源码与配置迁移 | Verified | 唯一4.35工具链/workspace及依赖；必要手写证明兼容修复，未改语义、目标和输入假设 |
| C盘实际worktree移除 | Completed（少量元数据待手动删除） | 三份实际Git worktree已移除，源码快照保存；仅D主目录注册；残留链接/标记/当前聊天元数据删除遭自动审批拒绝 |
| 真实验证与独立Q | Verified | 306单元；77哈希核验保留+6实际重跑共83核心控制；IEEE16单元/九控制/核心回切、19原型；E独立bootstrap/交错证明；最终独立Q通过 |
| 删除旧4.24及临时副本 | Blocked（待用户手动操作） | 下列七目标的删除命令在执行前被平台拒绝：blocked by policy；七目标均未删除，没有换方式重试 |
| 提交推送 | Completed | 已验证源码6d25493已非强制推送到origin/codex/shader-equivalence-planning；ls-remote确认远端精确SHA，工作目录干净；本段为发布状态补记 |
| 回到原始目标的成果与下一步 | Completed（规划调查） | 已有HLSL→Lean证明闭环；正式Vertex/完整HDRP/IEEE语言覆盖仍有缺口；下一步优先官方求交/NaN恢复函数链，本次未实施新能力 |

## 可手动删除的旧环境与临时副本

以下七处均已检查无reparse point，当前运行不使用它们；小型验证记录已保存在主目录artifacts和已入库精简机器证据中。只删除准确列出的目录，不删除其父目录。

- `D:\2FileBuildWorkPlace\Formalize\ShaderFormalize\.tools\lean-4.24.0-windows`
- `D:\2FileBuildWorkPlace\Formalize\ShaderFormalize\.cache\lean-unification-20261028`
- `D:\2FileBuildWorkPlace\Formalize\ShaderFormalize\artifacts\portability\Fresh Checkout`
- `D:\2FileBuildWorkPlace\Formalize\ShaderFormalize\.tools\leantar`
- `D:\2FileBuildWorkPlace\Formalize\ShaderFormalize\.cache\ieee`
- `D:\2FileBuildWorkPlace\Formalize\ShaderFormalize\prototypes\ieee\.lake`
- `E:\CodexValidation\ShaderFormalize-lean435-20261029`

合计约16GiB逻辑文件大小。保留当前`.tools/lean-4.35.0-windows`、唯一`proof/.lake`、`.cache/mathlib`和根`.cache/downloads`中的当前官方ZIP。

## C盘小型残留

- `C:\Users\xc\.codex\worktrees\basic-math`：junction，目标E盘只剩名称标记；只删除链接本身，不递归跟随目标。
- `C:\Users\xc\.codex\worktrees\ieee-prototype`：只剩名称标记。
- `C:\Users\xc\.codex\worktrees\compute-texture`：只剩`ShaderFormalize\.git`；退出当前聊天或Codex后再删，避免占用。

E盘`E:\CodexWorktrees\basic-math`和`E:\CodexWorktrees\compute-texture`也只剩名称标记；前者仍是上述junction目标，先删链接再处理标记目录。不要清理其它项目`compute-load-store`或`srgb-plan-handoff`。

Lean4.35下载分片目录已不存在；这不是agent完成删除的声明。全局worktree根目录由用户在界面迁移到E盘，agent没有改全局配置或现有清理策略。机器证据见[本轮记录](../evidence/lean-unification-2026-10-31.json)。
