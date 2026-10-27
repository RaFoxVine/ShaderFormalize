# VerCors 并行与同步接入原型

这个独立原型用于确认：成熟并行验证工具能在本地运行，接受正确的访问权限/同步模型，并拒绝具体错误。它不改变 ShaderFormalize 默认实数证明环境，不需要 Unity。

```powershell
pwsh -File prototypes/synchronization/bootstrap.ps1
python prototypes/synchronization/run.py
```

需要 Python、curl 和 Java 17+。已有 Java 可以直接使用；也可给 bootstrap 的 `-JavaHome`、run.py 的 `--java-home` 指定本地 JDK/JRE。脚本只设置本进程环境，不安装到系统或更改全局设置。固定的 VerCors Windows release、哈希及来源在 dependencies.lock.json；工具放仓库 .tools，下载放 .cache。分块下载保留已完成块，网络中断后可重跑。

两份源码使用 VerCors 的 PVL 建模语言：

- `ParallelAdd.pvl`：线程各自读取两个输入元素，写自己的输出。负例把所有写入改到地址0，要求验证器指出权限不足。
- `SharedExchange.pvl`：两个线程先写自己的共享槽位，在 barrier 交换访问权限后读邻居槽位。负例移除 barrier，要求邻居读取因缺少权限而失败。

运行器把实际输入快照、完整日志、退出状态及哈希保存到 `artifacts/synchronization/`。只有正例实际成功、负例实际到达权限错误，最终报告才为 PASSED；环境错误或语法错误不算预期负例。

这里检查的是 PVL 模型中的并行访问及 barrier 权限，没有把外部验证器结果变成 Lean 内核证明。固定两线程的真实 HLSL→PVL 入口另见[同步访问安全检查](../../docs/synchronization-hlsl.md)。同步例检查访问安全，未宣称完成任意 GPU 调度或数值等价证明。现阶段按工具声明使用它的验证能力，先跑代表例，不全面审计验证器内部。

2026-10-27，本地四项控制全部符合预期：两个正例通过、两个负例到达实际权限错误；独立Q核对通过。[入库证据](../../planning/evidence/vercors-integration-2026-10-27.json)。

参考 [VerCors 2.4.0](https://github.com/utwente-fmt/vercors/releases/tag/v2.4.0)（MPL-2.0）、上游的 [parallel vector-add](https://github.com/utwente-fmt/vercors/blob/v2.4.0/examples/concepts/parallel/vector-add.pvl) 和 [GPU prefix-sum 权限流](https://github.com/utwente-fmt/vercors/blob/v2.4.0/examples/concepts/gpgpu/prefixsum-drf.pvl)。本目录的两个小例子为本项目编写，依照这些公开模型使用权限与barrier接口。
