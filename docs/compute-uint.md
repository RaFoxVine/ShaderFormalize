# uint Buffer 单 pass Compute

显式运行 `python tools/computeformalize.py check --model uint32-buffer`，使用实际 HLSL、schema 3 约束和 agent proof 验证单 pass。默认 legacy 入口仍采用原实数模型；新入口不承诺 GPU profile 匹配。

本入口的普通值及纯 helper 参数/返回为标量 uint/bool。支持 uint32 模算术、按位运算和低五位移位；支持 if/else、提前 return、局部赋值。资源是显式寄存器的 StructuredBuffer<uint>/RWStructuredBuffer<uint> 下标读写；helper 可读 Count，Buffer 访问只允许 main。一个 b0 uint Count，入口为 void main(uint3 : SV_DispatchThreadID)，仅直接 x/y/z 分量，y/z 为零。float、普通向量、数组、循环、纹理、同步、atomics 和多 pass 不在此入口范围。

schema 3 严格包含 schema、dispatch_groups、count_range、bindings。每个 Buffer 显式给 identity/capacity，同 identity 是同起点、uint stride4 的物理资源，容量必须相同；未知 view 字段拒绝。Count 范围上界不得超过固定 launch 总线程数。容量不必大于 Count 上界，每次真实访问的界内条件由 Lean 证明。

完整 expected 同时要求双方所有线程的 Load/Store 合法、不同线程无 WW/WR 同址冲突、所有物理资源全部地址的最终内存相等。同一线程使用有序写入 overlay；不同声明别名读回能看到此前最后一次写入；未写地址保留任意 initial 值。短路与三元未选侧不会留下有效访问义务。UNPROVED 表示当前提交证明未通过，不表示已经形式证明不等价。DXC 和 typed-AST 翻译仍是可信边界。

`--output` 是产物容器。每次调用独占一个随机 run_id 子目录；stdout JSON 给出 run_id/result_path。必须读取本次身份对应的报告，不能读取容器根部旧 result.json 或别的成功 run。同/不同容器争用共享证明 workspace 时，拒绝者有自己的 INCONCLUSIVE 终态，不能覆盖 owner 的文件。无法解析 argv 或无法写产物位置时返回 stderr/nonzero。

`python tools/run_compute_uint_suite.py` 串行验证真实正负控制。`python -m unittest discover -s tools -p test_compute_uint.py` 检查导入、能力边界、契约、guard 和结果归属。新证明候选位于 ShaderComputeUint 命名空间；稳定 Model 注册非默认 library，不将动态 SubmittedProof 加入默认 build。
