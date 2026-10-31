# 二进制分支、提前返回和局部赋值

二进制入口可以直接处理纯计算的if/else、嵌套分支，以及main和按值helper中的提前return。局部变量与struct字段在分支后按所选路径汇合；结构体复制保持值语义。

```powershell
python tools/ieeeformalize.py check --original examples/ieee-control/branch-record.original.hlsl --optimized examples/ieee-control/branch-record.optimized.hlsl --agent-proof proof/ShaderIeee/RecordControlProof.lean --output artifacts/my-binary-control
```

条件需要是标量bool，例如`word < 0x80000000u`或`value != value`。`if (floatValue)`和`if (uintValue)`所需的隐式数值转bool尚未支持，可以显式写比较。标量uint支持`+= -= *= &= |= ^= <<= >>=`，含义与对应的普通运算一致；加减乘模2^32，移位量取低5位。复合赋值读取已有值，所以目标必须已经初始化，入口参数仍只读。

三个示例分别覆盖：

- `branch-record`：根据编码高位选择struct字段，再复制和修改副本；改写版用三元选择。
- `helper-return`：helper和main提前返回，八种uint复合赋值与保持同一运算顺序的显式赋值比较。
- `float-branches`：处理NaN、正负零和分支除法，改写版使用选择表达式；比较包括输入的完整位编码。

这些运算使用既有binary32参考profile；输入覆盖所有存储位模式，成功结果仍为`IEEE_PROVED`，`gpu_profile_matched=false`。目标检查最终输出的完整存储位相等，没有额外的“输入不是NaN”或“所有分支除数非零”假设。未被选择的分支可以产生特殊值；纯中间值不影响最终所选输出。这里没有浮点异常标志或外部写入语义。

每组另有错误改写。`UNPROVED`表示提交证明未通过，并不自动证明两份程序不等价；报告和日志保留具体失败原因。

所有非void函数仍须在所有语法路径返回。分支一侧没有初始化而后续读取、未调用helper中的错误、写入只读输入、递归或超出规模限制都会拒绝。内部证明占位值不能替用户局部补初始化。当前上限为32层分支、每个函数调用帧128个返回分支、4096个SSA绑定及既有helper/struct限制。

分支和函数返回使用与实数前端共用的`shader_flow.py`，表达式仍由各自后端解释。没有if的旧IEEE程序继续走原直线前端；默认实数CLI的意义未改变。循环、资源、Compute、clip/discard、导数、采样、数值cast及uint向量还不属于这个二进制入口，整体迁移状态见[任务表](../planning/binary-pipeline/tasks.md)。
