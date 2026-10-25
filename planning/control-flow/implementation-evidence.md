# 自包含核心与条件控制流执行记录

读者是后续维护/复核agent；本记录解释本轮授权、实测、修正与尚待闭合事项。当前有效产品用法归README和docs/agent-workflow.md，批准规划保持历史不重写。

基线5ed98a2，授权提交4a33b36。独立P第一轮通过，精确授权见execution-authority.md。用户明确核心只负责两份HLSL转Lean及agent尝试证明环境，Unity仅作可选开发验证。未新增依赖/全局配置，未使用Lavish，未push。Smart脚本doc-pending确认当前无_TreeDiveCode，沿用既有planning结构，不初始化其他项目。

## 初验与表示修正

DXC固定-HV2021，增加标量bool、一般if/else/?:、提前return与短路运算。先通过分支别名完整导数、then裁剪对else中性、void return/discard以及条件normalize的有限/Lean控制。正常branched材质包含真实结构体与helper、纹理开关和三模式着色；其完整Lean目标已在artifacts/branched/final-probe/result.json得到PROVED，保持允许基础公理集合。

初次完整材质证明因反复展开布尔SSA和裁剪谓词达到Lean预算，而GPU已通过。这不构成形式证明完成。将布尔表达式转为有上限的共享命题决策图，按events展开guarded effect，保留数学含义，无新增公理；再按着色模式和实际裁剪条件进行手写证明，得到完整PROVED。真值表、长别名及资源上限由独立Python回归检查；转换器仍属于可信边界。

## 独立Q及修复

第一轮Q发现旧schema3提升时normalize误用True guard、旧Program缺总调用展开上限，以及未调用helper初始化未检查。分别修复为当前event之前的effect合取guard、共享check_invocation、隔离的全部helper符号初始化检查；后者丢弃临时绑定/效果并恢复所有状态，不增加未调用函数的数学域义务。新增混合schema全discard的完整Lean正控及真实DXC回归。

第二轮Q代码通过：control16、boolean4单元通过；独立探针验证未调用clip/normalize helper对实际模型无污染，effectDAG与原有限解释器81组输入/2349谓词值一致。未发现新语义缺陷。要求最终明确Unity语言模式边界，已补README：模板未固定HLSL2021，GPU只覆盖有限颜色/mask，短路由固定DXC核心回归覆盖。

## 当前机器验证

显式 `run_unity_suite.ps1 -UnityProject ...` 五例全部PASSED。新branched为120组/245760像素，独立CPU颜色最大误差2.3792381398379803e-08，182680保留/63080丢弃，43020阈值边界保留；错误纹理开关及错误裁剪阈值有实际GPU反例；保存重载场景对齐误差0、隔离污染0。Unity源hash与Lean输入相同。实际预览已目视检查。

最终默认核心命令在子进程PATH无法发现unity且无UnityProject参数时执行，环境记录artifacts/core-environment.json，完整日志artifacts/control-full-core.log，退出0。102项单元及27项证明正负控制全部符合预期，其中10个完整目标PROVED，branched构建69.359秒/独立绑定审计22.672秒。92份实现/输入/证明/依赖文件原始字节快照在artifacts/control-final-source-hashes.json，不包含每次检查会变化的ignored SubmittedProof生成文件。运行期间，ControlMixedProof最后两步在suite执行该控制之前补齐，随后已由最终完整suite验证，证明SHA与报告一致；可选inventory_hdrp.py另补SHADER_TARGET并独立重跑调查。最终快照已包含这些修订，核心转换实现与测试字节自完整运行开始保持不变。

精简证据planning/evidence/control-flow-2026-10-25.json已核对全部92源哈希、10份正例的输入/证明/语义模块/依赖锁，以及五GPU输入和模板哈希；GPU与被证明HLSL字节一致。新增实际有限反例：零向量下原条件normalize正常返回、错误提前normalize触发未定义；将void helper的return换成discard，同一输入由输出颜色变为丢弃。前者同时是完整Lean负控，后者为有限实数模型反例，不冒称不等价的自动形式证明。

## 官方Lit调查

固定HDRP17.5.0 Forward，镜像记录146源文件，选定宏配置可预处理且独立DXC完整typed AST成功。初版漏SHADER_TARGET导致FastLog2缺失；根据官方Common.hlsl保护条件及Lit target4.5补宏45后解决，未修改Unity包。当前转换器首个真实拒绝是隐式sampler方法的嵌套invalid sloc头；实际源码另含uint/位运算与void/out Frag入口。完整AST不是当前子集支持证明；后续仍需可达分析。详见docs/hdrp-investigation.md及planning/evidence/hdrp-forward-2026-10-25.json，完整来源哈希/固定宏在artifacts/hdrp/result.json。

## 交付状态

独立Q第三轮通过：复核全部原始报告、92源快照、10证明、五GPU、HDRP来源/宏/输出、Unity语言模式边界及最终说明，未发现未关闭阻塞。本次实现/记录以 `feat: verify shader control flow with standalone core` 本地命名提交，无push。人工H-X及正式归档待用户后续处理。运行日志、调查镜像、工具和编译缓存保持ignored；废弃BranchedProbe源文件已移除，不提交实验垃圾，不清理用户资料。
