# Overnight 交付：二进制局部数据与 uint Compute

本次批准的 A/B/C 实现及验收全部完成；D 按约定只交付方案。当前可以把正常 HLSL 的位运算、分支、局部向量/数组/固定循环转换为二进制 Lean 模型，也可以单独验证纯 uint Buffer 的单 pass Compute。二进制尚未替代默认实数入口，自定义规格与多 pass 尚未实现。

## 交付结果

| 项目与授权上限 | 实际结果 |
|---|---|
| A：当前分支批次，PLAN_AND_CODE | 完成 if/else、嵌套分支、main/helper 提前返回、struct 字段汇合及 uint 复合赋值的最终验收和独立 Q。 |
| B：局部数据，PLAN_AND_CODE | 完成 uint2/3/4、swizzle 写入、同 lane 位重解释、局部定长数组和固定次数规范 for。共享普通值与控制骨架，各数值后端保留自身语义。动态循环及资源访问不属于这条像素入口。 |
| C：uint 单 pass，PLAN_AND_CODE | 新增显式 `--model uint32-buffer`，验证实际 HLSL 的标量 uint/bool、纯 helper、Count 尾线程 guard 和 StructuredBuffer<uint>/RWStructuredBuffer<uint> 有序读写。Lean 完整目标同时包含双方访问界内、跨线程无 WW/WR 冲突和所有资源全部最终内存相等。 |
| D：规格及图，PLAN_ONLY | 首个单候选规格方案 `spec-single-005@r2` 已通过独立 P2，实际 B/C 前置已完成，状态 READY_FOR_APPROVAL。固定任务身份、输入条件 P、输出关系 R、安全与允许修改范围 Frame 均已具体化；拟用精确量化和输入相关整体误差两任务验收。多 pass 发布、符号循环和两图前缀和继续保持 Candidate。没有写 D 产品代码。 |

C 复用公共 uint 运算、分支和证明引擎，提取泛型有序内存；默认 legacy 入口保持原合同。新入口每次调用使用独占 run_id 目录，stdout 给出本次 result_path，避免旧成功被当作本次结果。owner 争用、环境错误、超时/中断及目标/语义篡改已有实际控制。

## 实际验证

最终冻结产品为 `25ff1915742ce9dbc8f06bb7eff41877dad2dc89`，验证期间核对 170 份源码/配置及 211 份示例，未发生字节漂移。最终串行五阶段全部 exit 0：

- 118 项旧目标及状态逐项相同，232 份实际生成模型快照已核对。
- 347 项 Python 单元及 83 项核心控制符合预期：38 PROVED、43 UNPROVED、2 INVALID_INPUT。
- 37 项 IEEE 专项单元、35 项正负控制及默认实数回切通过；35 项中 16 IEEE_PROVED、19 UNPROVED。
- 19 项 binary32 原型检查通过。
- 新增 uint Compute 的 16 项控制符合预期：6 PROVED、10 UNPROVED。正例包括 hash、别名、打包、guard、边界和嵌套 guard；负例覆盖错误计算、Store/Load 越界、WW/WR、目标伪造、sorry、额外公理及篡改。

安全负例先证明其他条件，只留下对应的真实越界或竞争义务。边界正例把参考表达式绑定到实际生成 kernel，并对十项移位的删除/错误计数及共同计数错误给出 20+6 个可观察性不等式。证明审计保持原公理白名单。

最终独立 Q3 在证据检查点 `4c9e8b1` 给出 PASS、issues=[]，只读独立核对 2438 项指纹、本次全部 16 个 run 的身份和产物。前两轮发现的环境分类、越界隔离和边界可观察性问题均已修复并重新实际验收。历史失败日志保留，没有重写成一次无失败运行。

持久证据：`planning/evidence/binary-compute-2026-10-31.json` 为 PASSED。A/B 各自证据分别为同目录下的 `binary-control-2026-10-31.json`、`binary-data-2026-10-31.json`。原始产物保存在忽略的 `artifacts/`，没有将依赖缓存或运行产物加入 Git。

## 限制与下一步

当前 uint Compute 不接受 float 资源、普通向量/局部数组/循环、纹理、groupshared、barrier、atomics 或多 pass；B 的局部数据能力尚未与这个资源后端组合。当前 binary32 是固定参考 profile，尚未匹配具体 GPU；DXC 和翻译器仍属于可信边界。UNPROVED 表示提交证明未通过，不等于已经证明程序不等价。

下一步可以批准 `planning/binary-pipeline/spec-single-design.md` 的单候选规格切片，先跑通“给定数学性质，证明一份实际 HLSL 满足它”，再逐片组合资源循环与计算图。整体二进制迁移及多 pass 仍有后续工作，不能以本次整数 Compute 成功代替这些交付。

## Git 与环境

A 完成记录 `e701125`、B 完成记录 `30d6752`；C 产品 `25ff191`、实际验收证据 `4c9e8b1`、最终 Q/状态收尾 `a2c77ac8ff766aed8dfd7f56b27dd09f37962e15`。已将上述提交非强制推送到 `origin/codex/shader-equivalence-planning`，并用 ls-remote 核对收尾提交完全一致。本报告及 Session 的最终记录随后提交并推送到同一分支，交付消息给出最终远程 HEAD。

依赖、Lean 版本、默认入口、Unity 和全局配置保持既有状态，没有新建 C 盘 worktree。节点保留待用户 H-X；没有合并或归档。工作范围没有删减，D 继续遵守仅规划的授权上限。
