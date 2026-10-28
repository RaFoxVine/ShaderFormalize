# Agent 如何尝试验证两份 Shader

这是使用者/证明agent的入口。仓库接受两份受支持的HLSL、输入范围和一份尝试证明，输出可复查的数学目标及检查结果。工具不会自动判断任意程序是否等价。安装、转换、证明和默认验收均不需要Unity；Unity脚本只属于可选开发验证。

## 准备核心环境

本机支持Windows x64、PowerShell7、Python3.9+标准库、Git和curl。仓库内工具由dependencies.lock.json固定，本地Lean4.35/DXC在.tools，mathlib、FloatLib及传递revision由唯一proof/lake-manifest.json固定。各数值路径共用工具链和依赖，实数与IEEE模型含义分别定义。

新机器或新的干净目录请先按[Windows启动指南](windows-setup.md)取得工作分支并重建本地工具；不能依赖原工作区的ignored缓存。

```powershell
pwsh -File tools/bootstrap.ps1
pwsh -File tools/run_demo.ps1
```

第二条是完整核心验收。开发迭代可用 `-Example branched` 等只检查某个示例；正式交付运行默认全套。核心命令不会查找Unity或读取外部Unity工程。

## 为一个输入对生成目标

将原版、改写版和schema2输入约束作为明确文件保存。两边入口、uniform及资源布局必须一致；不支持的源码直接拒绝。先运行prepare：

```powershell
python tools/shaderformalize.py prepare --original examples/branched/original.hlsl --optimized examples/branched/optimized.hlsl --constraints examples/branched/constraints.json --output artifacts/my-pair
```

读取该目录的result.json、original/optimized.model.json以及GeneratedModel.lean。生成模块中的 `ShaderFormalize.Generated.expected` 是完整目标；后续证明必须精确匹配它。prepare不是证明成功。

float按实数解释；输入范围是用户提供的前提。采样/导数是双方共享的完整函数操作。控制流模型的expected还要求两份程序已执行的normalize均有合法定义域：这些是需要证明的结论，不能把缺失条件偷偷添加为假设。生成目标可能比单独颜色等式更强，因为还包括裁剪结果和运算合法性。

helper返回值按函数内部路径选择，保留调用范围外的完整字段值；实际执行条件另外控制域要求、采样/导数上下文和裁剪。`proof/ControlHelperFieldProof.lean`展示同一分支中ddx(Identity(x))与ddx(x)对任意共享Ops的证明，`ControlHelperDomainProof.lean`检查未调用helper的域不会被误加。

包含整数打包时使用schema5：uint按32位精确整数解释；float→uint和移位也产生带执行条件的定义域结论。`asfloat(uint)`只生成位载体，`asuint`可取回它；载体不能参与数值计算，当前也不能跨helper参数/返回边界。完整支持范围、例子及限制见[整数打包](integer-packing.md)。

函数图较大时，可在prepare和check都加`--frontend shared`。它生成schema6，每个helper保留一份实际Lean定义；每个调用仍携带完整字段、裁剪状态和定义域结论。默认auto保留旧模型，shared双方必须统一选择。正常结构化材质的证明是`proof/SharedStructuredProof.lean`；支持边界和命令见[共享函数](shared-functions.md)。

shared还接受默认参数、out/inout、float矩阵和定长数组，支持整变量、字段、下标及不重复swizzle写回。正常调用材质见`examples/copyback`；矩阵/数组材质见`examples/aggregate`和`proof/AggregateMaterialProof.lean`，单独运行`pwsh -File tools/run_demo.ps1 -Example aggregate`。输入/输出别名及未规定顺序的兄弟表达式存在读写冲突时拒绝，不自行选择求值顺序。[复合值与输入范围](aggregate-values.md)。

## 写证明并交给检查器

手写Lean文件应导入GeneratedModel，并提供完整名字 `ShaderFormalize.AgentProof.equivalent`，类型为 `ShaderFormalize.Generated.expected`。现有proof/BranchedProof.lean和proof/ControlDomainProof.lean分别展示材质分支和有条件归一化的完整证明，可据实际目标采用不同策略。

```powershell
python tools/shaderformalize.py check --original examples/branched/original.hlsl --optimized examples/branched/optimized.hlsl --constraints examples/branched/constraints.json --agent-proof proof/BranchedProof.lean --output artifacts/my-pair
```

check每次重新从HLSL生成目标，将提交证明放入受控模块；再用独立模块绑定完整目标并审计传递公理。只有全部成功才给PROVED。检查器拒绝sorry、自定义公理和伪造同名目标；允许的基础公理只有propext、Classical.choice、Quot.sound。

证明agent可以修改自己的证明，读取生成目标/诊断并迭代。不要编辑GeneratedModel、语义定义、转换器或审计器来使当前输入通过；这会改变被验证的问题。核心开发任务对这些文件的修改另属代码审阅流程。

## 解释结果

- PROVED：本次输入、约束、数学模型与完整目标的证明通过；查看源码/目标/证明/语义模块哈希以复查对象。
- UNPROVED：当前证明未通过，包括无法证明定义域；这不代表已经证明两份程序不等价。保存尚未解决的Lean目标及相关约束。
- UNSUPPORTED / INVALID_INPUT：查看具体拒绝原因，分别表示语言范围外或输入/布局/约束不合法。
- ENVIRONMENT_ERROR / INCONCLUSIVE：工具、超时或共享工作区占用问题，不是数学结论。

有限数值回归和可选GPU运行用于发现反例及转换错误，不代替Lean证明。一个观察到的有限反例应注明输入、所属模型和复现方法；工具目前没有独立的DISPROVED状态。

所有check共用proof中的生成文件，使用仓库写锁串行执行。不要并发启动多个prepare/check；不同--output目录不代表不同证明工作区。完整日志和生成文件留在ignored artifacts/.cache/.tools/proof/.lake，提交HLSL、输入约束、手写证明和必要证据。

## 可选开发验证

显式提供UnityProject才会运行GPU/已保存HDRP场景检查：

```powershell
pwsh -File tools/run_demo.ps1 -Example branched -UnityProject '外部Unity工程绝对路径'
python tools/inventory_hdrp.py --project '外部Unity工程绝对路径'
```

前一条在核心成功后追加开发验证，后一条调查官方Lit固定配置。它们需要外部Unity项目/可选开发环境，其结果和路径不参与核心安装、转换或证明。HDRP调查得到预处理源码不等于完整Lit已被导入或证明。
