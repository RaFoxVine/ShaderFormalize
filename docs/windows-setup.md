# 在另一台Windows x64使用仓库

需要PowerShell7、Python3.9或更新版本、Git、curl，以及下载固定依赖所需的网络。所有数值路径使用仓库内同一套Lean4.35.0、固定DXC和proof/工作区；不需要Unity或VS Code的Lean环境，也不修改机器全局PATH、elan或Git配置。

## 首次取得源码并安装

```powershell
git clone --branch codex/shader-equivalence-planning https://github.com/RaFoxVine/ShaderFormalize.git
cd ShaderFormalize
pwsh -NoProfile -File tools/bootstrap.ps1

# 首次烟测：完整生成目标、检查证明、公理审计。
python tools/shaderformalize.py check --output artifacts/first-check

# 验证整数打包示例及其负控制。
pwsh -NoProfile -File tools/run_demo.ps1 -Example packed

# 共享helper、默认参数/out/inout的正常材质及正式正负控制。
pwsh -NoProfile -File tools/run_demo.ps1 -Example copyback

# 矩阵/数组、元素写回及下标定义域。
pwsh -NoProfile -File tools/run_demo.ps1 -Example aggregate
```

已有仓库时，在上述工作分支运行`git pull --ff-only`，依赖锁或安装脚本有更新后再运行bootstrap。完整验收用不带Example参数的`tools/run_demo.ps1`。`prepare`只生成待证命题，只有`check`返回PROVED才是完整证明通过。

工具归档由dependencies.lock.json固定下载地址和SHA256；mathlib、FloatLib及其传递依赖由唯一proof/lake-manifest.json固定Git revision。归档下载后校验，Lean/DXC安装到.tools，Git依赖和编译产物在proof/.lake，下载缓存在.cache。Python代码只使用标准库，不需要pip安装项目包。

同一bootstrap也准备IEEE浮点模型。`python tools/run_ieee_suite.py`执行其独立正式控制，`pwsh -File prototypes/ieee/run.ps1`运行库原型。

这些目录被Git忽略，因此git pull不会带来另一台机器的二进制或编译缓存。每个新目录都需要bootstrap。脚本默认取得当前所需的数学库缓存，实际加载核心模块，并构建FloatLib模型与原型；模块不能加载或构建失败会退出非零。`-SkipMathlibCache`仅准备本地工具和固定源码，不表示数学证明环境完整。

## 出错时保留正确的边界

网络下载失败可以重跑bootstrap，已正确下载的归档会按哈希复用。若提示已安装的Lean/DXC文件损坏，脚本会拒绝继续；它不会自动重装已有安装。先将对应目标保留移出，再重跑，目标均相对本仓库根目录：

| 损坏工具 | 保留移出的准确目标 |
|---|---|
| Lean | `.tools/lean-4.35.0-windows`目录 |
| DXC | `.tools/dxc`目录 |

缓存解包使用Lean工具链自带leantar，不另装旧解包器。不要改动全局编辑器安装；依赖版本以锁文件为准。

安装和检查器会在自己的子进程清除外部LEAN_PATH、LEAN_SRC_PATH、LEAN_SYSROOT，使用本地固定工具和本地依赖。VS Code插件及其elan下载可以独立存在。环境错误/INCONCLUSIVE不是两份Shader是否等价的数学结论。

实数、Compute与IEEE入口共用当前checkout的proof/工作区和写锁，串行编译。IEEE生成模块位于proof/ShaderIeee，与核心模块各自命名；不要用不同output目录同时启动多个检查。需要独立验证时使用另一份checkout，保留各自的本地依赖和生成目录。

## Unity和官方HDRP输入

上述安装、转换、证明及默认验收都不查找Unity。仓库保留HLSL示例、输入约束、手写证明、工具、依赖锁和精简证据；完整日志/本机实验留在ignored artifacts。

官方HDRP调查的完整预处理源码和AST同样属于本机ignored产物，不会随Git自动转移。需要重新调查时，显式提供对应Unity/HDRP工程路径，按[HDRP调查指南](hdrp-investigation.md)运行inventory工具；这不影响核心示例运行。完整HDRP/Lit Forward是否已能转换及证明，应查实际最新结果，不能从调查成功推断。
