# 统一 Lean 与依赖

目标：将实数与 IEEE 两条路径统一到已安装的 Lean 4.35.0；完成真实回归后删除旧 4.24 安装与缓存。数学含义、输入范围、三公理白名单及两类成功结果保持原约定。用户要求现在迁移，不继续长期维护两套环境。

## 最终结构与职责

- 根 dependencies.lock.json 统一固定 Lean 4.35.0、DXC、mathlib 56a005855ea17e0b0958f73ec801ae140b0a1679、FloatLib 8c8871576a941a86e73dcf0882702b823139aa93；沿用现有官方 ZIP 与二进制哈希。
- proof/ 为唯一 Lake workspace、manifest、传递包与构建缓存；mathlib/FloatLib 各一份。实数与 IEEE 语义分别由原模型拥有，工具链统一不合并二者的数值含义。
- IEEE 模型与生成/提交/绑定模块使用 ShaderIeee.* 独立模块路径和命名空间，不能与核心 GeneratedModel/SubmittedProof/Verify 的 olean 或声明冲突。共同绑定生成器保留旧调用兼容。
- 两个 CLI 共用 workspace 锁串行编译；保留用户命令、独立 IEEE profile 和 PROVED/IEEE_PROVED 区分、目标/公理审计及报告绑定。
- 原型 PowerShell 入口作薄兼容 wrapper，调用统一环境与 probe；撤销第二套 Lake/Lean/工具锁的有效配置，历史证据保留真实旧版本事实。
- 安装使用固定 SHA 物化传递包。新版 cache API 替代旧 FetchCache 和 leantar0.1.15 下载器，使用 4.35 自带 leantar，定向取得实际 import 根并运行 smoke。ProofWidgets inputRev=main 不得当 tag 拉取。

## 实施范围

唯一源码 writer 为 migration agent：工具定位/环境/hash、两个 CLI、公共绑定、bootstrap/seed/cache、两个旧 workspace/锁、IEEE模型/证明/probe、必要核心证明兼容修复、相关测试与当前使用说明。现有 CLI 参数、错误终态、输入数学条件和证明强度不得弱化。

root 独占 planning、C/E 目录迁移、依赖缓存物理搬迁、旧安装清理、整合验收和提交推送。writer 不操作 C worktrees、不复制一套新工具；收到 root 环境就绪前只改源码，不运行 bootstrap/cache/Lake。独立 Q 由另一 agent 审核，不由 writer 自评代替。

## 验收与删除条件

首先核对 4.35 工具/包 revision 与 import closure，冷启动核心模型、BitVec、floor/tactic 兼容探针。4.24 的 olean/项目构建缓存不能混用；4.35 既有上游缓存可复用，项目生成模块缓存必须失效。

最终运行 301 项以上的全部单元、83 项核心正式控制、IEEE 9 项控制与19项原型检查；预期负例和三公理审计全部保留。实际交错运行两路径，确认生成/缓存/绑定不会串用；工具漂移和失败覆盖旧成功仍需通过。

独立 Q 闭合且验收通过后，root 删除明确命名的旧 4.24 工具、包/cache 和临时迁移备份；先检查绝对路径/reparse point，保留已提交源码、必要证据及当前环境。不升级数值 profile，不新增公理/隐含输入前提，不触及 Unity 或其它项目。

独立 P 已由 audit_ieee 完成，结论可行；明确闭合 getFiles/validateLeanTar 与 ProofWidgets main/tag 两处 API 问题，实际证明兼容以编译为准。若需要改变数学含义、目标或接受子集，停止相关更改并回到用户讨论。
