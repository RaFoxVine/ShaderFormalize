# 工具链初步调查：本机编译器与 Unity 连接

日期：2026-10-24。依据：[已确认范围](scope-and-toolchain-r2.md)。

## 本轮回答了什么

本机已有 DXC、Slang 和 Unity CLI。Unity CLI 能连接用户指定的 Unity 6.5 工程，状态为 `ready`，目前没有发现需要升级 Unity 的理由。

对同一个包含两种 sampler、向量计算和分支的小样：DXC 的调试输出已经包含带类型的函数体；本机 Slang 的 AST 调试输出没有函数体，部分表达式类型还是空的。Slang 能把该小样编译为 HLSL，生成的 HLSL 也通过了 DXC 编译。

因此，HLSL/DXC 目前有一个可用于原型调查的入口；Slang 在生成运行代码方面已有正面证据，但证明侧的程序提取还需要找到更合适的接口。这不是最终语言选择，也不说明 Slang 无法提供类型化程序结构。

## 比较使用的同一个小样

[sample.slang](evidence/toolchain-probe-2026-10-24/sample.slang) 使用两种语言共同接受的基础写法，包含：

- 一个 cbuffer，内有颜色与系数。
- 一个 Texture2D、两个分别绑定的 SamplerState。
- 两次 SampleLevel、向量分量读取、乘法、条件分支和复合赋值。

这次小样只调查编译器能输出什么信息，不是在实现或证明该 Shader，也没有把它导入 Unity。文件扩展名不代表最终选择 Slang；DXC 在本次显式指定 profile 的调用中也接受这个输入。

## DXC 的结果

实际版本见 [dxc-version.txt](evidence/toolchain-probe-2026-10-24/dxc-version.txt)。

执行了：

```powershell
dxc -T ps_6_0 -E main -ast-dump <临时目录>/sample.slang
```

[完整输出](evidence/toolchain-probe-2026-10-24/sample.dxc-ast.txt) 中可以看到函数体、两次 SampleLevel 调用、sampler 身份、float3 类型、分量选择、if 和 `+=`。这支持进一步调查如何自动导出这些信息。

局限：当前拿到的是调试文本。尚没有验证稳定的结构化导出接口，没有写转换程序，也没有验证宏、复杂重载或完整 Shader 的覆盖。不能把文本输出成功当成前端已完成。

## Slang 的结果

实际版本为 `2026.1-52-gc8ddf20bb`，见 [版本记录](evidence/toolchain-probe-2026-10-24/slang-version.txt)。

执行了：

```powershell
slangc <临时目录>/sample.slang -entry main -stage fragment -target hlsl -O0 -dump-ast -o <临时目录>/sample.generated.hlsl
```

[AST 调试输出](evidence/toolchain-probe-2026-10-24/sample.slang-ast) 有声明，但没有本例的函数体，部分表达式显示 `type : rvalue null`。该输出记录的语言版本为默认的 `2018`。目前不能把这份输出直接当成“已经完成类型检查的完整程序”。

[生成的 HLSL](evidence/toolchain-probe-2026-10-24/sample.generated.hlsl) 包含两种 sampler 和计算、分支。对该文件另执行：

```powershell
dxc -T ps_6_0 -E main -Fo <临时目录>/sample.generated.dxil <临时目录>/sample.generated.hlsl
```

该编译退出码为 0，DXIL 文件为 4400 字节。这验证了本例的 Slang → HLSL → DXC 编译路径，尚未验证 Unity 中运行或与原程序的形式等价。

另外尝试了当前在线文档列出的 `-language-version 2026`；本机版本返回 `unknown command-line option '-language-version'`，退出码 1，所以没有得到这一方言模式的比较结果。不能据此声称已测试当前最新版 Slang。后续调查必须使用与候选版本相符的接口文档。

为解释调试导出的阶段，读取了官方 master 的 [slang-compile-request.cpp](https://github.com/shader-slang/slang/blob/master/source/slang/slang-compile-request.cpp)。该源码把 DumpAst 放在解析阶段，在之后另做语义检查。这与本地看到的不完整类型信息相符；所读取的 master 不是本机二进制的精确构建版本，因此只作为机制参考。本轮下载的源码 SHA256：`02918C3D9863F1A9B4CBB1C26085A1A98F17FA87C79AFBEFCA73984EEE92BE00`。

本机还有一个实际文件位置细节：`-dump-ast` 把 `sample.slang-ast` 写到调用工作目录，本轮已将该临时产物移出仓库根目录并保存为证据。后续调用应明确设置临时工作目录，避免污染项目。

## Unity 的结果

执行 `unity status --format json`，保存了 [原始结果](evidence/toolchain-probe-2026-10-24/unity-status.json)。目标为：

```text
D:\2FileBuildWorkPlace\Unity Project\Example Project\HDRP-Sample-6000.5.9
```

结果为一个实例，版本 `6000.5.9f1`、状态 `ready`。使用显式 `--project-path` 查询命令目录，能看到 `eval`、`eval_file` 和 `run_script` 等实时 C# 入口。这只是接口发现，尚未调用它们执行新代码。

已通过 `unity skill show` 读取 CLI 随附指南，并读取其连接命令说明。没有安装或更新 CLI、插件、包或编辑器，没有修改 Unity 工程。

## Lean 的状态

当前 PATH 未找到 `lean` 或 `lake`，常见的 `C:\Users\xc\.elan\bin` 路径下也没有相应文件。这只说明当前没有发现可直接调用的环境，不表示全盘检查后认定机器上绝不存在 Lean。

本轮没有安装 Lean/mathlib，也没有运行形式证明。端到端可行性仍需要真实的 Lean 检查结果。

## 下一步调查应解决什么

下一步应围绕“能否自动取得可解释的程序”，分别核查 DXC 和 Slang 的结构化接口与接入成本。随后给出一个完整的首个闭环方案：两份 Shader 怎样进入数学模型、agent 怎样写证明、Lean 怎样检查，以及同一份代码怎样在现有 Unity 中运行。转换实现语言也由这些实际接口决定。

本轮不据此锁定 HLSL、Slang 或 C++，也不为了方便而把源码实数等价替换成编译产物等价。自动求解和反例搜索仍不在必要交付内。

## 调查中的限制与失败

- GitHub 的递归文件树 API 返回了速率限制错误，未作为证据；后续直接读取了官方指定源码文件。
- Slang AST 文件实际位置与帮助文案描述不同；首次读取错误位置失败，定位后保留了真实产物。
- 新方言选项在本机版本不支持，未进行新版本安装或把失败当作成功。
- 还没有运行 Lean 证明或新的 Unity Shader；本报告不声称已打通完整验证链。
