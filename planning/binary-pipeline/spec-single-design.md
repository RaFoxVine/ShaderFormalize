# 单候选自定义规格：spec-single-005@r2

本文件是Overnight D的PLAN_ONLY交付，具体化“给定固定Lean输入性质与输出关系，验证一份真实HLSL”的首片，独立P第2轮通过。总体目标与规格信任边界见spec-graph-design.md；多pass、符号循环和发布语义仍由该文件规划。本片没有代码grant；C依赖尚未最终验收，不标Execution Ready。

前置C（binary-compute-004@r2）已在实施，以下接口已由作者核实，泛型内存与生成模型已完成首次编译，C整体尚未最终验收。B已验收；C最终代码检查点、完整回归与独立Q仍是本片实施授权的依赖。下文区分已出现的C接口与首规格片拟增加的责任，不把规格功能说成当前能力。

## 交付目的与范围

当前 pair 验证回答两份实现是否相等。本片让任务发起者先固定一个数学目标，agent 再提交一份候选 HLSL 和证明，检查器验证该候选的安全、允许修改范围及输出性质。P/R 使用 Lean 定义，可观察整个有效数组并表达依赖输入的误差预算，不限制成几个 JSON 误差选项。

首片复用 C 的纯 uint32、单 pass、有限无循环 HLSL 子集，不扩语言、资源类型、dispatch 能力或 GPU profile。候选仍经过 DXC 解析和相同的执行语义，不用另写一个 Lean 算法代替实际 HLSL。实数/legacy 默认入口与已有 pair 模式保持原合同。多 pass、scratch、符号循环、浮点误差、纹理和概率自动化不在本片内。

## 层次与责任

任务发起者拥有固定 ABI、Compute 约束、P/R 和允许修改区域。任务文件及规格源发布为一个可核对的 task_id；更换其中任何已绑定内容产生另一任务。候选作者可以修改 HLSL 与提交证明，不能用本次运行时临时算出的新身份悄悄替代发起者要求的旧任务。

执行层复用 C 的 importer、共享 uint 表达式/分支和资源事件 emitter，产生一份候选的有限执行定义。公共 engine 继续拥有源快照、DXC 调用、Lean 编译、缓存、公理审计、目标绑定与结束核对。新增任务加载层拥有 manifest/lock、规格依赖快照与身份检查；规格 backend 拥有完整 expected 的构造。它不再实现一套解释器或 prepare/check 循环。

工具保证验证准确绑定到所提交的固定 P/R，不能一般性判定任意 Lean P 是否合理、非空或间接编码安全条件。实际结论只适用于 Domain 与 P 均成立的输入；不额外要求所有 Domain 输入都无条件安全。首批验收任务提供合法输入及预算分支见证，一般任务不强制非空见证。

## 单候选入口与公共 engine

拟通过现有 CLI 的显式模式选择本能力：

```text
computeformalize.py check --model uint32-spec
  --task <task.json>
  --task-lock <task.lock.json>
  --expected-task-id sha256:<64位小写十六进制>
  --candidate <shader.hlsl>
  --agent-proof <proof.lean>
  --output <产物容器>
```

prepare 使用相同任务身份和候选参数，生成目标但不声称证明成功。新模式拒绝 pair 的 original/optimized 参数；不将同一候选复制两次。默认 legacy 和 C 的 uint32-buffer selector 不变，不从 JSON 或坏输入自动猜测模式。

公共 engine 的源输入由 backend 显式提供：pair 为 original/optimized 两项，spec 为 candidate 一项。它对这些源执行同一套快照和 DXC→IR 流程，再调用 backend 的契约核验与目标生成。旧 prepare(args, output)、check(args, output) 的默认调用保持兼容。具体 backend 配置对象及扩展点以 C 交付为准，不预先要求 C 实现未承诺的规格功能。

C当前Backend只有uint、prefix、theorem三个字段，prepare/check接收默认LEGACY的keyword-only backend；源快照/DXC和模块编译循环已共享。首规格片将其扩为明确的源角色、importer、契约构造、目标生成及语义模块配置，公共循环消费这些配置；legacy/uint pair各提供两个角色，spec只提供candidate。现有Backend常量和默认direct caller保留。单候选uint契约检查抽出公共资源/入口核验，旧uint_contract(data,original,optimized)继续包装同一核验；不复制一次candidate去填pair。

spec 运行沿用 C 每调用独占新 run 子目录的政策，stdout 返回本次 run_id/result_path；runner 只读取匹配身份的结果。共享 workspace 仍只允许一个 writer，不维护有竞争的 latest 报告。

## 任务描述与首 ABI

task.json 的拟定 schema 如下，顶层只接受这些字段：

```json
{
  "schema": 1,
  "abi": "uint32-spec-1",
  "constraints": {},
  "spec": {
    "module": "ShaderComputeSpec.Task.ExactEven",
    "precondition": "ShaderComputeSpec.Task.ExactEven.P",
    "relation": "ShaderComputeSpec.Task.ExactEven.R"
  },
  "sources": [
    {
      "module": "ShaderComputeSpec.Task.ExactEven",
      "path": "ExactEven.lean"
    }
  ],
  "frame": {
    "writable_binding": "Output",
    "region": "count-prefix"
  }
}
```

constraints 嵌入完整 C schema3 约束，不再指向另一份可变 JSON。schema、abi、frame 的可接受值明确校验，未知字段、重复 JSON key、错误数字类型及缺失声明均拒绝。JSON 整数字段不接受 bool 或浮点替代。

首 ABI 只有 Source、Output 两个不同物理资源，identity 分别固定为 0、1；这属于首片限制，不承诺通用资源布局接口。Source 为只读 uint Buffer，Output 为可写 uint Buffer；具体声明、寄存器和 numthreads 按 C 的契约核验。容量、launch 与 Count 范围来自任务并由候选符合，不由候选扩大。113 容量、T=128、0≤Count≤113 是两个验收任务的参数，不是所有未来规格任务的永久数值限制。

稳定 Lean ABI 拟提供 Input（count : UInt32、initial : uint 内存）与 Output（最终 uint 内存），以及 Source/Output identity 常量。任务模块提供精确类型 P : Input → Prop 和 R : Input → Output → Prop。内存类型是 C 实际 uint 内存特化的别名；不能在实施时重建一份看似相同但独立的内存语义。

C当前ShaderComputeUint.Model将Memory/ThreadResult分别特化为泛型ComputeMemory的UInt32版本；Memory实际为Nat→Nat→UInt32，safe接收threads与kernel，finish接收threads、initial及kernel。ABI直接使用这些声明。UintComputeEmitter.definition(name,contract)拥有kernel发射，现generate_uint_compute(original,optimized,contract)拥有pair组装；规格backend复用前者，并在共用模块组装中增加单候选expected，不重新定义uint运算或内存。

允许修改区域由 manifest 固定为 Output[0,Count)。Frame 对所有物理 identity 和地址量化：该区域以外的值都必须等于 initial，涵盖 Source、Output 尾部及其它地址。候选不能通过输出选择或提交证明放宽 Frame。P/R 如何表达真实目标由任务发起者负责，Frame 的固定构造由检查器负责。

## 发布、lock 与 task_id

拟新增任务发布工具 spec_task.py freeze，读取 manifest 及依赖，生成 task.lock.json 并输出 task_id；它不检查候选，不宣称规格已经被实现。发起者固定该身份后，prepare/check 必须显式传入 expected-task-id。缺失或不匹配不回退为当前文件身份。

lock payload 拟包含 schema、task.json 原始字节 SHA256、任务源的模块名/规范相对路径/原始字节 SHA256、本项目稳定 ABI 与执行语义的传递模块及 SHA256，以及 dependencies.lock.json 与 proof/lake-manifest.json 的 SHA256。绝对机器路径不进入身份。模块名限定为普通点分标识符；任务源路径相对任务目录，解析后必须留在该目录内，拒绝重复模块和 Windows 大小写路径碰撞。

规范序列化使用 JSON sort_keys=True、separators=(",", ":")、ensure_ascii=True，再以 UTF-8 编码求 SHA256；task_id 为 sha256: 加 64 位小写十六进制。lock 中的 task_id 字段不进入 payload，避免自引用。检查器从实际输入重新构造 payload，不能只相信 lock 自称的散列。原始文件散列意味着只改 manifest 排版也会产生新任务身份；这是可预期的字节绑定政策。

该机制提供任务内容身份，不负责鉴别提交者角色、签名或访问控制。调用方仍需把发起者确认的 expected task_id 传给检查器。候选与 proof 不进入规格身份；它们作为本次实现与证明另行绑定。

## 规格依赖、编译和结束核对

任务模块使用保留前缀 ShaderComputeSpec.Task。运行时复制准确源快照到对应受控模块位置，保持原模块/namespace，不重写 Lean 源。任务不能覆盖稳定 ABI、语义模块或候选动态文件。真实导入闭包中允许 lock 声明的任务模块、已绑定的本项目稳定依赖及固定上游库；触达任何候选 GeneratedModel、SubmittedProof 或 Verify 均拒绝，未声明的其它本地模块也拒绝。

受控任务模块具体位于proof/ShaderComputeSpec/Task/<模块后缀>.lean，由本次run在workspace锁内安装，映射以显式任务模块注册表为准；该运行目录纳入.gitignore，不存放用户的发布源。任务真实源与快照保留在任务目录/本次run。已有同名前任务文件不参与新闭包，编译只消费本次注册来源；稳定library只列Abi，不让失败候选或历史任务进入默认build。模块source/olean位置通过共享engine的显式模块映射提供，不能另起编译器循环。

本地 Lean4.35 源码提供 --deps-json，可用于获得实际 import，而不另写完整 Lean 头部解析器。只读依据为 Lean/Shell.lean 中 deps-json 分支，以及 Lean/Elab/ParseImportsFast.lean 的 printImportsJson；输出含 errors，未来实现须检查内容，不能只看 exit0。本次只核实了源码，未实际运行该命令，其实际输出及模块解析接点仍待实施验证。

本项目及任务模块递归建立依赖闭包并拓扑编译。固定 Lean/Mathlib/FloatLib 继续使用现有工具锁、lake manifest 与已安装依赖的信任边界，不为本片重做整个上游供应链审计。固定环境与模块解析须保证实际导入的是已绑定来源，不能接受任务前缀覆盖上游模块。

缓存链为 C 的稳定执行模块、规格 ABI、任务依赖、GeneratedModel、SubmittedProof，最后独立 Verify。缓存键覆盖源、传递依赖、工具锁、task_id，并核对目标 olean 内容；任务定义变化不能复用旧证明成功结果。具体字段与现有 C 缓存接口对齐，不增加第二个编译循环。

结束核对覆盖任务文件、lock、规格源及快照、ABI/语义依赖、生成目标、提交证明与依赖锁。编译消费的是冻结快照，结果同时记录输入原路径和准确散列。既有目标绑定与原三公理白名单继续适用；规格中的 sorry 或额外公理若进入最终定理，也必须被最终审计拒绝。

## 完整 Lean 目标

下列是拟定目标形状，Memory、safe、finish 和 kernel 签名应使用 C 的实际声明：

```lean
def expected : Prop :=
  ∀ (initial : Memory) (count : UInt32),
    Domain count →
    Task.P ⟨count, initial⟩ →
    let result := finish threads initial (candidate initial count)
    safe threads (candidate initial count) ∧
    Frame count initial result ∧
    Task.R ⟨count, initial⟩ result
```

Domain 来自固定任务的 Count/launch 契约。candidate 是实际 HLSL 生成的有限定义，safe 继续包含访问 bounds 和不同线程 WW/WR 排除。C 的无循环受支持程序构造总定义，因此首片正常完成由有限执行构造保证，不先开发通用故障 Outcome 或终止证明器。不能把目标改成“若存在一个正常输出则 R”。

生成模型、提交证明和独立 Verify 使用 ShaderComputeSpec 独立命名空间，Verify 固定消费 Generated.expected，提交证明不拥有 expected。task_id 在生成文件与报告中留档，身份安全来自外部 expected-task-id 核对与内容绑定，不能用目标里一个字符串自等证明代替它。

两个满足允许误差 R 的候选不自动精确等价；如需精确比较，仍须另证对应输出关系。本片只验证单候选满足固定任务。

## 文件责任与兼容迁移

| 拟改位置 | 职责 |
|---|---|
| tools/computeformalize.py 与 C 实际公共 engine | 显式 spec 路由、单候选角色、沿用 prepare/check 和独占 run 生命周期 |
| tools/spec_task.py | 严格任务/lock、发布、task_id、规格依赖闭包与冻结核对 |
| C 实际 uint emitter | 复用候选 kernel，新增单候选规格目标构造；保留 pair 输出 |
| proof/ShaderComputeSpec/Abi.lean | 固定 Input/Output、identity 和 Frame 辅助 |
| proof/ShaderComputeSpec 的动态 GeneratedModel/SubmittedProof/Verify | 本次候选、提交定理和独立绑定；纳入 .gitignore，不进入默认 library roots |
| tools/proof_contract.py | 复用命名空间 Verify；仅必要时补公共参数化 |
| examples/compute-spec、任务规格与独立证明、专用 suite | 两项规格和真实正负控制 |
| 单元、文档、coverage、planning/evidence | 验证绑定/缓存/失败政策并说明能力与信任边界 |

稳定 ABI 可注册独立非默认 library；不将失败候选或临时任务加入默认 build。旧 pair API、legacy 默认入口、既有模型 schema、依赖版本与 Unity 内容保持，不批量改写旧证明。公共 engine 扩展必须通过旧消费者回归，而不是迁移旧测试去覆盖新模式后称兼容。

## 失败政策

所有结果归属与 workspace busy 处理沿用 C 已审政策：先创建本次独占 run，再取锁；busy 返回本次 INCONCLUSIVE，不改 owner 产物，不继续解析坏约束或工具。参数或输出路径本身不能落盘时明确 stderr/nonzero，不声称保存了报告。

锁空闲后，坏manifest/lock/schema、初始任务身份不匹配、不支持的候选，以及任务Lean语法/类型或P/R签名错误为INVALID_INPUT并标明task阶段；固定依赖缺失/损坏为ENVIRONMENT_ERROR；超时为INCONCLUSIVE；实际目标/证明/审计失败为UNPROVED。运行中已绑定内容发生变化拒绝当前证明并报告具体原因，不能保留PROVED。意外内部错误独立报告，不能包装成数学反例；shared编译器根据模块角色报告task错误与submitted-proof失败，底层调用与缓存只有一份。

PROVED 表示在记录的 Domain、P、uint32 语义及固定任务下，候选安全、遵守 Frame 并满足 R；不声明已经匹配具体 GPU。UNPROVED 只表示当前提交未通过，不一律称实现已被证伪。PREPARED 也不代表任务性质已证明。

## 首批验收

两任务均为 Source/Output 容量113、T=128、Count 为0..113，量化任意初始 UInt32 内存和全部契约内 Count，包含尾线程与空有效区间。证明须来自真实 HLSL 转换。

精确任务：P 要求每个有效 Source 元素不超过255；R 要求 Output[i].toNat = 2 * (Source[i].toNat / 2)。候选可以在输入大于255时产生不同结果，以检查结论真正受固定 P 限定，而非无意证明另一无条件任务。正确版清除最低位；错误版对有效域内的数产生不同结果。

误差任务：P=True。E 为有效输出与输入的 Nat.dist 总和，S 为有效输入的 toNat 总和，N=Count.toNat。R 要求 S<2N 时 E≤N，否则 2E≤S。清除最低位的候选满足该关系；清除低两位的错误版在正长度全3输入时超过预算。两分支提供可达见证；错误算术在真实 SubmittedProof 失败，不以不支持语法代替。

还需一个数值 R 正确但修改有效区外 Output 的候选，成功导入且安全，却在真实完整目标的 Frame 处失败。例如仅在Count=0时由线程0额外写Output[0]：访问在容量内、没有冲突、有效输出关系为空，但破坏必须保留的初始值。规格/任务替换、expected task_id 不匹配、未声明本地依赖、候选模型导入、目标伪造、缓存依赖变化、运行中篡改、sorry/额外公理均有对应控制。单元覆盖严格字段、路径/模块重复、任务身份规范、当前 run 归属和旧成功不复用；身份失败与数学证明失败分别记录。

另有R及Frame均成立、仅safe失败的真实候选，独立检验spec目标没有遗漏安全性：正常路径清除最低位，在通常Count guard之前，仅当Count=0且线程ID=0时额外读取Source[113u]并存入未使用局部变量，不额外写入。容量113时该Load越界；Count=0时输出关系为空、全部内存保持，只有访问bounds失败。它须成功导入且GeneratedModel实际编译，在SubmittedProof的真实safe义务失败，不能用旧pair负控或输入拒绝替代。当前C前端会保留未使用局部值产生的Load事件。

片末运行适用的完整既有回归与新 spec suite，对公共 engine、语义模块和旧 pair 目标兼容给出实际证据，并经独立 Q。具体测试数量用届时 C 交付的真实基线，不在此预填成功数字。

## 依赖、停止条件与未冻结项

进入实施前须完成 B/C 验收与独立 Q，核实 C 的 backend/缓存/契约/emitter/结果 API，把以上文件归属与签名对应到实际代码，再对最终冻结稿独立 P并取得新的精确代码授权。D 的 PLAN_ONLY 不派生代码 grant。

本稿已对应作者确认的C初版接口，明确了模块快照路径、单候选契约/目标及Backend所需扩展；这些都是首规格片未来修改，不要求C现在实现。最终需核对C命名检查点的接口是否保持、完成独立P，并在实施时实际检验--deps-json输出与闭包。接口细节若不改变本合同可机械对齐；若改变ABI、任务身份或完整目标，必须修订设计。首ABI、manifest/lock/task_id和失败政策均为具体提案，不是已实现能力。

若需要新增执行 profile/公理、绕过固定任务身份、弱化安全/Frame/完整目标、扩到符号循环/图/新资源，或关键真实验收不可用，应停下受影响项重新规划。普通 API 对应、编译诊断、证明和合同内缺陷可在取得该片授权后自主解决。当前不因这些待对齐项重开已确认的二进制与自定义规格方向。

## 独立规划审阅

独立P第1轮由/root/binary_data_plan_review只读检查f03eb67，发现1项P1：缺少仅safe失败的单候选真实负控，不能用C旧pair模式负控检验spec新目标组装。修订2补上述Count=0额外读取的具体验收后，第2轮审阅b7060153d453be42bc98444d61d650d88d0d9758实际PASS、issues=[]；单候选/任务身份/真实C接口/完整目标和两项数学任务均无剩余规划阻断。没有为本规划执行Lean或写规格功能代码；C最终验收/Q依赖仍保留，P通过本身不授予实施权。
