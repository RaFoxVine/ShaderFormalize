# ShaderFormalize

验证两份手工改写的 HLSL，在给定输入范围内是否具有相同的**理想实数计算结果**。当前是首个可运行闭环，用一个受限例子验证源码转换、agent 写证明、Lean 检查与 Unity 运行之间的连接。

例子：

```hlsl
// 原始
return lerp(a, b, saturate(t));
// 改写
return a + (b - a) * t;
```

`a`、`b` 是任意四维实数向量，输入条件是 `0 ≤ t ≤ 1`。Python 调用项目内固定版本 DXC，读取带类型的语法树，生成 Lean 定义与完整命题。`proof/AgentProof.lean` 是 agent 手写的证明。检查器另建一个模块，将该证明绑定到本次生成的目标，并检查其依赖的公理。Unity 使用相同 HLSL 文件执行若干输入，检查包装、编译与 GPU 回读能否工作。

## 本地运行

首版环境为 Windows x64、PowerShell 7、Python 3.9 或更新版本（仅标准库）。Unity 测试需要已经打开并可由 `unity` CLI 连接的 Editor；本次使用 Unity 6000.5.9f1、HDRP 17.5.0、Direct3D12。正式验证本身不依赖 Unity。

在仓库根目录运行：

```powershell
# 首次：官方归档校验并安装到本目录，拉取锁定的 Lake 依赖，取预编译缓存。
pwsh -File tools/bootstrap.ps1

# 生成模型并检查已有 agent 证明。
python tools/shaderformalize.py check

# 正例、故意改错、放宽范围、伪造证明等完整检查。
python tools/verify_demo.py

# 在已打开的 Unity 工程运行同一批 HLSL。
python tools/run_unity.py --project '你的 Unity 工程绝对路径'

# 完整验收；首次可加 -Bootstrap。
pwsh -File tools/run_demo.ps1 -UnityProject '你的 Unity 工程绝对路径'
```

默认产物写到 `artifacts/current/`、`artifacts/acceptance/`、`artifacts/unity/`。获得工作目录写锁后先写 `IN_PROGRESS`，成功或失败都会更新 `result.json`；并发请求返回 `INCONCLUSIVE`，保留正在运行者的报告。完整工具日志保存在同目录。检查不同输入时用 `--original`、`--optimized`、`--constraints`、`--agent-proof`、`--output` 指定；修改源码后需要 agent 为新目标提供适当的证明，工具不自动搜索证明。

```powershell
python tools/shaderformalize.py prepare --optimized examples/lerp/wrong.hlsl
```

`prepare` 只生成模型，不表示已经证明。约束格式目前仅接受第三个标量参数的闭区间，端点必须是字符串，按精确十进制有理数读取：

```json
{"schema": 1, "ranges": {"t": {"min": "0", "max": "1"}}}
```

矛盾区间、拼错字段、数字型端点都会拒绝。两侧参数顺序、名称、类型、semantic 和输出 semantic 必须一致。

## 当前支持边界与结果含义

导入器接受单个 `float4 main(float4, float4, float)` 像素函数，各参数带 semantic，返回 `SV_Target` 或 `SV_Target0`，函数体只有一个 return 表达式。表达式支持参数、十进制数字、括号、加减乘、一元负号、`lerp`、`saturate` 及对应的隐式标量广播。数字使用源码中的原始文字，避免把 DXC 打印的已舍入数值当成精确值。接受规范十进制整数与十进制浮点文字；八进制、十六进制和整数类型后缀暂不支持。输入采用 LF 或 CRLF 换行，拒绝预处理符号、反斜杠拼行和其他换行字符（即使位于注释内）。

局部变量、用户函数、预处理、分支、循环、矩阵、纹理、uniform buffer、除法、导数等均暂不支持，遇到未知结构就拒绝。当前还不能导入普通 Unity 项目的完整 Shader；本次验证的是入口表达式这一层。后续扩展必须同时补全导入规则、数学语义和验证例子。

| 状态 | 含义 |
|---|---|
| `PREPARED` | 已导入并生成命题，尚未检查证明 |
| `PROVED` | Lean 检查本次目标与证明通过，绑定定理没有额外公理 |
| `UNPROVED` | 当前证明未通过，或依赖不允许的公理；不能据此断言两份源码不等价 |
| `UNSUPPORTED` / `INVALID_INPUT` | 输入超出支持范围或不合法 |
| `ENVIRONMENT_ERROR` / `INCONCLUSIVE` | 本地工具缺失、超时或已有检查占用生成目录 |

Lean 中 `float` 被解释为实数，`float4` 被解释为四个实数；`lerp(a,b,t)=a+(b-a)*t`，`saturate(t)=min(1,max(0,t))`。这不证明实际浮点逐位一致，也不证明编译器正确。DXC、受限 AST 适配器和 Lean 语义定义仍属于可信边界，当前没有对源码到模型的转换器本身作形式证明。证明脚本是本地可信开发输入，会由 Lean 执行，不能将来自陌生人的 Lean 文件当成安全沙箱输入。

Unity 报告 `PASSED` 仅代表有限样本在容差内通过：使用线性浮点 RenderTexture，回读原始/改写/故意改错三侧，并与 CPU 公式比较，拒绝空输出和非有限值；额外检查范围外输入能表现出差异。数学上的任意输入结论由 Lean 证明提供。

## 文件与依赖管理

- `examples/lerp/`：真实 HLSL 输入、范围与错误改写。
- `tools/`：启动、严格导入、命题生成、证明检查与验收脚本。
- `proof/ShaderFormalize/Model.lean`：当前数学语义；`proof/AgentProof.lean`：手写证明。
- `unity/RunProbe.cs`：通过 CLI 在现有 Editor 执行的 GPU 测试脚本。
- `dependencies.lock.json`：官方 Lean/DXC/leantar 下载地址、版本与 SHA256；DXC 使用固定文件哈希，绝不回退到 PATH 上的另一版本。
- `proof/lake-manifest.json`：Lake 固定 mathlib 与传递 Git revision；传递条目来自锁定 mathlib 自带的 manifest。初始化浅拉取精确提交，ProofWidgets 另保留指向同一提交的发布 tag。mathlib 是原生包管理依赖，因此不额外叠加 Git submodule；依赖源码不复制进仓库。

`.tools/` 放本地工具，`proof/.lake/` 放 Lake 包和构建结果，`.cache/` 放下载与 mathlib 缓存，`artifacts/` 放可重建的模型、日志和 GPU 结果。生成的 `proof/GeneratedModel.lean`、`SubmittedProof.lean`、`Verify.lean` 也不提交。安装脚本将 Lean/Lake/mathlib 缓存位置限制在本目录，只设置当前进程环境，不改全局 PATH、elan 或用户配置。Python、Git、curl 与已存在的 Unity/CLI 由开发机提供。`proof/ShaderFormalize/FetchCache.lean` 在初始化时复用 mathlib 的哈希、下载与解压代码，仅遍历 Real.Basic 的依赖；不改变数学语义。

Unity 仅在指定工程的 `Assets/ShaderFormalizeProbe/` 创建三个 HLSL 副本与三个 ShaderLab 包装，不改场景；这些文件由样例重建。暂时保留以便在 Editor 检查；需要移除时可在 Unity 中删除整个 `ShaderFormalizeProbe` 文件夹（连同 `.meta`）。GPU 临时材质、纹理会在脚本 finally 中释放。

发布 Git 时提交源码、依赖锁、手写证明与文档；不要提交本地工具、Unity Library、下载包和运行日志。下载归档在安装校验完成后可以删除；保留工具与构建缓存能避免重复下载。

## 当前验收

2026-10-24 完整运行 `tools/run_demo.ps1` 通过：25 项回归，错误改写、放宽范围、自定义公理、`sorry`、伪造目标五类负例均被拒绝，正例得到 `PROVED`。Unity 实际执行 10 组范围内输入、回读 160 个像素，最大误差约 3.73×10⁻⁸，容差为 10⁻⁵。独立实现复审通过。

精简机器结果见 [验收证据](planning/evidence/first-closure-2026-10-24.json)，执行与修复经过见 [执行记录](planning/first-closure/implementation-evidence.md)。下载归档和分片已清理约 1.36 GB；工具与缓存保留。另有约 21 MB 中断 Git 拉取临时包因自动审批策略拦截未删除，位于已忽略的依赖目录，不影响提交或运行。
