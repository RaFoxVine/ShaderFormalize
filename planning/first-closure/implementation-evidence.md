# 首个闭环的执行证据

2026-10-24，分支 `codex/shader-equivalence-planning`。本文件记录执行与修复经过；当前使用方法以根目录 README 为准。

## 已完成初验

- 固定 DXC 官方 v1.8.2505.1 已在 `.tools/dxc` 安装；归档与三个运行二进制 SHA256 验证通过。无 PATH 回退。
- Lean 官方 4.24.0 Windows ZIP（662142928 bytes）下载完成，整包 SHA256 与官方发布 digest 一致；本地 `lean.exe --version` 输出 `Lean (version 4.24.0, x86_64-w64-windows-gnu, commit 797c613eb9b6d4ec95db23e3e00af9ac6657f24b, Release)`。本地 lean/lake 二进制哈希加入锁文件。
- mathlib 固定 f897ebcf72cd16f89ab4577d0c826cd14afaafc7。root Lake manifest 的传递条目来自该提交的 upstream manifest（原文件 SHA256 记入 dependencies.lock），保留其 URL/revision，设为 inherited，并加入直接 mathlib 条目。使用 Lake 自身读取此 manifest；初始化以 shallow fetch materialize 固定提交，避免 `lake update` 无条件拉取全部标签/历史。9 个依赖的实际 checkout 已完成，日志位于 ignored `artifacts/bootstrap/`。
- mathlib cache 工具及其所需的 Batteries 模块已实际构建。最终使用 `lake --no-cache exe fetchMathlibCache`：项目入口复用 upstream 哈希、下载和解压 API，仅遍历 Real.Basic 依赖；避免额外 Reservoir package cache 端点。714 个预编译模块已下载、解压成功。ProofWidgets 必需的 v0.0.74 tag 已核对指向同一锁定提交，其发布包也实际获取成功。本机 GitHub release 下载的 IPv6 路由停滞，初始化在 `.cache/curl` 写入仅当前进程使用的 IPv4/连接超时设置，未修改用户 curl 配置。
- `python tools/test_shaderformalize.py`：当前 25 项真实 DXC/范围/报告/锁检查通过（2.552s）。独立 Q 后新增的词法、多行位置、中文注释、CRLF、BOM、带单引号和逗号路径用例包含在内。
- `python tools/run_unity.py --project <已授权的 Unity 工程>`：实际运行 PASSED。Unity 6000.5.9f1，Direct3D12，Linear；10 组范围内输入，160 pixels，每像素四分量，最大误差 3.725290298461914e-08，容差 1e-05；错误优化差异最大 6，范围外两侧差异最大 3。报告与完整 CLI 输出在 ignored `artifacts/unity/`。
- Unity 接收 original/optimized/wrong 原始字节副本。报告 SHA256 分别为 `66444f4a51a8163dbc3d6e892ca4f9ce8c91549fa77e5c5a6234fea519fa9384`、`3abedf745c6b0038e3790986d5a808625f20bd3aa9493f45046b5264e46b8bbb`、`646c2c1a31c30c975f2a46a9a7b5bd601c5a91557f7ff8372abb401e762f5c87`。Python 与本地源码重算哈希一致。

## 独立 Q 第一轮与修复

implementation_review 以新会话只读审查真实代码和 GPU 结果，发现三组 P1，首轮判定不通过。其原因和修复为：

1. HLSL 八进制 `010` 是 8，旧实现将源码文字当十进制 10；反斜杠拼行也能改变 token。现仅支持规范十进制整数，拒绝前导零整数、其他进制/后缀和反斜杠。
2. 原先仅拒绝行首 `#`，无法阻止注释后的预处理与 include。现调用 DXC 前和导入时均验证，拒绝任何 `#`、`%:`、`??=`（即使在注释中），不尝试重复实现预处理器。
3. DXC 的相对 col 使用全局上一个打印位置（含 source range 结束和额外声明位置），旧实现错误继承父节点行。现按打印顺序维护位置状态，回归普通多行 lerp 与嵌套表达式。数字恢复只按 LF 物理行划分；接受 LF/CRLF，拒绝 bare CR、VT、FF、NEL、Unicode 行/段分隔符。真实 DXC 用例证实中文注释与 CRLF 下精确数字恢复正常。

审查同时要求最终 Lean 运行与依赖清单证据；这些完成后集中进行第二轮。没有将未运行的 Lean 检查标记为成功。

第二轮复审又复现路径中的单引号被误当成类型引号，导致位置头截断。修复为明确解析 AST 地址后的 source range 与可选声明位置，再读取后续类型/名称；不再用首个单引号截断整行。Windows 路径可含单引号和逗号，但不能含作为 source range 边界的 `<`、`>`。审查者使用相同恶意注释/多行 main 构造，独立确认带单引号和逗号路径下恢复数字 8 正确。环境方面独立核对全部 9 个 checkout HEAD、传递 URL/revision、upstream manifest SHA256 与本地作用域设置通过，未发现新阻断。

## Lean 初验与清理

`python tools/shaderformalize.py check` 已实际返回 PROVED，独立模块 `ShaderFormalize.Verification.checked` 公理审计仅 `[propext, Classical.choice, Quot.sound]`。源码、模型、语义定义、手写证明与 Lake manifest SHA256 已进入 ignored `artifacts/current/result.json`。构建 21.547s，独立检查 23.625s（首次模型构建更慢）。

下载归档与 Lean 分片按已确认的文件清单逐文件清理，释放 1360686079 bytes。目录级清理被自动审批策略拦截后，改用仅删除已确认文件的范围更小方式完成下载清理。另一个中断 Git 拉取留下的 20889599-byte 临时 pack，因只读属性及自动审批策略阻止删除，仍留在 ignored `proof/.lake/packages/mathlib/.git/objects/pack/`；未重试绕过策略。安装工具、锁定包源码、预编译缓存和运行报告保留，以供复用。

清理后再次运行 `pwsh -NoProfile -File tools/bootstrap.ps1 -SkipMathlibCache`，2.843s 成功复用本地工具与全部锁定依赖，无需下载归档。

## 最终统一验收与独立 Q

`tools/run_demo.ps1` 第一遍完整执行已通过：24 项回归、5 种负例、正例证明及 Unity GPU 重跑。路径头修复后的最终完整验收再次通过（退出 0），日志 `artifacts/demo-final.log`：25 项回归（2.612s）；wrong-expression、missing-range-premise、custom-axiom、sorry-proof、forged-target 均 UNPROVED，positive 为 PROVED，随后 Unity GPU PASSED。自定义公理/sorry 用例断言确实到达公理审计，伪造目标断言确实到达独立绑定模块。

第二轮独立 Q 正式通过，无剩余阻断项。审查者独立复现并确认全部位置修复，重算源码、模型、证明、语义定义、依赖锁与 Lake manifest 哈希一致，核对最终负例和 GPU 结果。精简可提交证据位于 `planning/evidence/first-closure-2026-10-24.json`，完整原始运行报告位于 ignored `artifacts/`。证明结论限定于 README 定义的实数语义和受限 HLSL，转换器与 DXC 仍属可信边界。

本轮源码、锁文件、手写证明与文档进行本地 Git 提交；不 push、不发布、不创建/归档 TreeDive Project。用户原审阅稿与标注不改写。
