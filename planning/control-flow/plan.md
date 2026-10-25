# 自包含核心与一般条件控制流（修订1）

## 目标与用户约定

仓库的产品能力是：两份HLSL经固定DXC typed AST转为Lean定义/命题，为agent提供可本地运行的尝试证明与独立检查环境。不是自动等价判定器。仅使用理想实数，资源/输入布局精确一致；DXC/转换器/语义定义仍为可信边界。Unity只供本仓库开发时作有限GPU/真实场景验证，不是安装、转换、证明或默认核心验收的依赖。保持本地Lean4.24/DXC/mathlib锁，无全局配置与依赖升级。

用户已认可轻量收尾→一般if/else及三元/布尔/提前return→固定官方HDRP/Lit变体调查的顺序，最新再次确认上述产品/Unity边界。沿用用户此前免完整方案额外人工审阅、先跑通的授权；独立P/Q与Git审阅保留，不使用Lavish，不初始化新的TreeDive项目分区。

## 核心和开发验证入口

bootstrap及shaderformalize的prepare/check保持纯核心，不能导入或查找Unity、Unity CLI或Unity工程。run_demo.ps1默认仅运行仓库内前端/证明控制；显式提供UnityProject时才追加可选开发验证，保留原命令兼容。另提供按example运行核心检查的简短入口，复用现有verify_demo/CLI，不建立第二套转换器。默认完整核心验收必须在PATH找不到unity、且不提供UnityProject时实际通过；Unity失败只影响明确启用的开发集成层，不伪装核心证明失败。

README以核心使用为首要说明，将Unity与HDRP调查列在可选开发部分。锁和bootstrap不包含Unity包；Unity脚本/模板留在独立目录。开发记录、GPU证据和用户外部Unity工程不被打包成核心依赖，临时探针留ignored artifacts，保留工具/编译缓存。

## 新语言能力与职责

固定-HV 2021。DXC负责所有语法/类型/引用/重载解析；适配器解释已定类型节点。支持标量bool局部、内部结构体字段、helper按值参数/返回；true/false、标量实数比较、bool相等/不等、!、&&、||；普通if/else、嵌套分支、数值/向量/记录/布尔分支赋值，标量条件的?:，numeric/record/bool/void helper和main的提前return。&&、||和?:按HLSL2021标量短路语义执行。入口与cbuffer仍为既有float数值布局，不新增bool stage输入或bool cbuffer。

所有函数静态按语句/表达式/左值上下文检查，包含未调用函数；未知节点/类型/属性/运算明确拒绝。沿用完整变量/字段赋值和按值语义；numeric/record/bool helper保持不改变裁剪状态，裁剪限main/void helper语句，避免引入未约定的表达式副作用求值顺序。仍排除循环、out/inout、数组、矩阵、一般除法/pow、预处理与额外资源能力；本轮不自动改写或拍平HLSL。

旧schema2数值与schema3纹理例、原证明和命令保持可用。仅出现一般控制流/布尔值/三元的新程序走schema4；旧if(比较)discard特例可保留原路径。一对程序任一使用schema4时，两边统一提升到新的完整函数发射器，确保if→三元等跨表示验证。

## 条件执行的数学表示

位置集合E、uniform常量、varying完整函数、共享Fragment.Ops及Option颜色输出沿用既有含义。新增ControlProgram拥有符号帧、当前函数仍执行的位置谓词、全Shader仍存活的位置谓词和已返回的条件/值。每个分支从同一输入符号帧按值复制，以条件/反条件执行；合并按条件选择每个外部叶值。分支局部声明不泄露。只在一支初始化的值，若另一支仍继续，则后续读取明确拒绝；已return/discard的支不限制继续支的初始化。

return只结束当前函数在相应位置的执行。返回值按返回条件合并；helper返回后恢复调用者执行条件，不误把void return当discard。discard使对应位置退出整个Shader，clip按每分量>=0保留。非void函数必须在每条语法路径返回或（main中）discard；缺失返回、不可达return后语句、未初始化读取拒绝。所有helper实参先求值，即使结果被忽略；仅短路未进入的运算不要求执行。

新模型的opaque操作接收当前完整执行位置谓词（调用分支、之前裁剪、当前函数return的联合限制），放入既有Ops.context列表的单一谓词项。这样能够表达分支内的执行条件，而不模拟quad/相邻片元；不添加导数或滤波公理。旧IR与新IR配对时，旧有裁剪条件前缀按合取提升为同样的执行谓词。旧schema2/3独立验证仍用原语义；schema4采用明确版本化的执行mask语义，不宣称证明跨不同执行条件移动导数/隐式采样。

每个采样/导数、normalize、分支条件和合并值及时写入SSA；绑定携带执行guard，子运算先于父运算。条件选择/返回的非执行区域用确定零/false填充值完成全函数表示，证明不依赖其作为已执行值；opaque同时保留执行条件。沿用4096绑定/128裁剪/32调用层/64输入叶等上限，另限制展开调用4096次、分支嵌套32层及每帧返回分支128，避免空helper或分支产生无界展开。

guard只约束执行、域义务和opaque上下文，普通SSA别名/算术保留完整输入函数，不把每条绑定在guard外清零。零/false只用于真正未定义的选择/返回区域。必须以分支内t=uv;ddx(t)与ddx(uv)等价作为正控。控制帧从同一入口分叉，局部return状态不共享；Shader存活状态可以用全局有序guarded-effect SSA表示（alive := alive ∧ (guard→keep)），但必须验证then的条件裁剪在else位置恒中性、helper返回不复活main已返回位置，不能无条件串行污染另一支。

normalize的定义域按实际guard处理：schema4目标除输出相等外还包含两边全部已执行normalize的guard→dot(arg,arg)>0义务。已有显式nonzero_vectors仍作为用户输入前提，但缺失前提不被偷偷增加；agent必须根据用户范围和分支条件证明上述义务。支持计算表达式参数的定义域证明；失败为UNPROVED，不能用未选分支的非法运算使错误程序被证明。schema2/3旧的显式域检查与状态保持不变。具体范围由现有schema2约束文件提供，不自动增强用户假设。

## 实现位置与消费者

shader_types/validation为bool和一般控制流增加受控规则，默认旧路径不变；shader_frontend保留旧Program，新shader_control解释控制帧/分支/返回，必要时分拆纯值与状态合并辅助模块。shader_control_lean定义新字段/执行mask/域义务发射；新的Control.lean只复用锁定mathlib/Model/Fragment，无新增公理。shader_lean按schema选择并生成用户范围，shaderformalize对实际使用的语义模块记录哈希，继续独立目标绑定/公理审计。有限control evaluator仅作回归/反例，不是证明。

新增正常branched材质：纹理开关、不同着色模式、bool helper/提前return、分支赋值和条件裁剪、选择数值的三元。改写版调整数值选择与公共计算，保持opaque执行条件可证明相同；不依靠未约定的导数跨分支变换。测试覆盖短路域、条件边界、初始化、作用域、helper参数/返回、分支内采样/导数/clip、主程序与void helper return/discard区别、全部函数静态拒绝与资源上限。手写Lean证明完整目标，错误条件/阈值/返回/短路义务须失败，并提供具体数值或GPU反例。

可选Unity开发验证直接include精确HLSL字节，扩展既有受控纹理/UV平面的独立CPU公式与裁剪mask对照，覆盖模式/开关/边界；保存重载实际HDRP场景及对齐检查。包装的短路编译语言配置必须核实，不能仅假设Unity默认与-HV 2021相同；若无法固定，则先用不依赖差异的GPU例子并明确独立前端语义测试，不能声称GPU证明短路。

## 官方HDRP/Lit调查交付

仅为开发材料选择本机固定HDRP版本的一份Forward片元Pass与明确关键字/材质配置，记录包revision、相关源哈希、包含入口和实际缺口。调查工具显式接受外部工程路径，默认核心运行不触碰该路径。尽可能取得该配置的预处理源码；若Unity宏/内建include尚不能独立导出，记录具体阻塞与已证实的源码节点，不能把未预处理的文本扫描当完整可达特性清单。此轮交付是固定输入与缺口调查，不宣称完整HDRP/Lit已经转换或证明。

## 验收与停止条件

先实际DXC小例/有限字段回归与单份Lean初验，再独立Q修复；最后默认核心完整检查在无Unity可发现环境运行，并单独显式执行Unity开发套件。记录原始JSON/源哈希/精简证据，更新唯一README，本地命名提交，不push或正式归档。独立P通过后才持久化精确grant进入代码。若实数/共享操作对象、产品/Unity边界、关键验收或依赖需改变，停止受影响部分重新规划；普通语义实现遗漏在已授权范围内自主修复。
