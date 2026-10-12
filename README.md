# sandbench

<p>
  <img src="https://img.shields.io/badge/AI_Infra-sandbox_bench-B4532A?style=for-the-badge" alt="AI Infra">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Docker-cgroup_isolation-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/leftover-0_after_bench-1F3B4D?style=for-the-badge" alt="no leftover">
</p>

隔离容器里跑一条命令，再压一轮 **创建 / 执行 / 销毁** 生命周期。用来把「沙箱」翻译成面试官能听懂的 Infra：配额、超时、失败分类、残留回收、并发延迟。

这不是 RAG Demo，也不是生产沙箱（没有 gVisor / Kata）。隔离边界是 Docker + cgroup，和华为那段离线 Cube 沙箱同源：先把生命周期和失败模式测清楚，再谈业务。

## 它证明什么

| 能力 | 本仓库怎么做 | 对应通用 Infra 岗 |
| --- | --- | --- |
| 资源隔离 | `--memory` `--cpus` `--pids-limit` `--network none` | 容器平台、稳定性、云主机 |
| 安全默认 | 非 root、`cap-drop ALL`、只读根、`no-new-privileges` | 安全 / 运行时 |
| 故障分类 | `ok` / `timeout` / `oom` / `error` | 可观测、SLO、值班 |
| 生命周期 | `docker run -d` 计创建，`docker wait` 计执行，`docker rm -f` 计销毁；bench 后按 label 扫残留 | 调度、K8s、资源泄漏 |
| 压测 | 并发 1 / 10 / 50，各 50 次，输出成功率、分阶段延迟、残留 | 性能、容量规划 |

## 依赖

- Python 3.11+
- Docker daemon（本机已能 `docker run busybox`）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

若本地没有 `busybox` 标签，先：

```bash
docker pull busybox
```

## 用法

单次执行：

```bash
python -m sandbench run -- sh -c 'echo sandbench-ok'
```

复现 README 里那张表（并发 1、10、50，各 50 次，负载是 `echo`）：

```bash
python -m sandbench matrix --jobs 50 --concurrency 1,10,50 --workload ok
```

超时和 OOM 各跑一小轮，确认分类，不混进上面那张表：

```bash
python -m sandbench bench --jobs 6 --concurrency 3 --workload timeout
python -m sandbench bench --jobs 4 --concurrency 2 --workload oom
python -m sandbench leftover   # 应为 (none)
```

`ok` 负载的原始数字在 [reports/matrix.json](reports/matrix.json)。

## 本机结果

2026-10-12 跑的，负载 `echo sandbench-ok`。机器是 macOS 26 arm64，Docker Desktop 29.6.1，虚拟机 8 CPU / 3.8 GiB。创建时间是 `docker run -d` 返回前的耗时，包含创建和启动；`echo` 往往在这一步里就结束了，所以执行时间只是之后 `docker wait` 收回退出码的时间。

| 并发 | jobs | 成功率 | 创建 p50 (ms) | 创建 p95 (ms) | 执行 p50 (ms) | 销毁 p50 (ms) | 残留 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 50 | 100% | 156.02 | 264.31 | 31.03 | 28.0 | 0 |
| 10 | 50 | 100% | 1987.66 | 2905.86 | 69.87 | 190.93 | 0 |
| 50 | 50 | 100% | 9101.06 | 10615.66 | 68.09 | 253.76 | 0 |

并发从 1 拉到 50，成功率仍是 100%，销毁后残留是 0。创建 p95 从 264 ms 涨到 10.6 s。瓶颈在 Docker Desktop 这次只给了 3.8 GiB 的虚拟机，50 个容器同时创建时卡在 dockerd，不在 `echo` 本身。

同一次代码里，`sleep 30` 配 2 秒超时会被记成 timeout，向 tmpfs 写超过内存上限会被记成 oom（退出码 137）。这两轮残留也是 0。

## 面试怎么讲（8 分钟）

1. **问题**：给不可信代码一个短生命周期环境，必须限制 CPU/内存/PID/网络，跑完不能留容器。
2. **取舍**：用 Docker 当隔离边界，而不是自己做内核模块；和实习里先评估能不能交付、再压测是同一件事。
3. **机制**：`docker run -d`、到点 `docker kill`、然后 `docker rm -f`。每次带 label，bench 结束再扫残留。
4. **结果**：打开上面的表。成功率、残留、创建延迟随并发变差，三列都要讲。
5. **没做的**：没有 gVisor / Kata，没有排队。被问到就说下一步是把创建从同步 `docker run` 改成有队列的调度。

口述稿见 [INTERVIEW.md](INTERVIEW.md)。

## 和华为实习的关系（对外口径）

实习代码和内网 Wiki 不能开源。本仓库是 **同构的公开练习**：隔离规格、压测、残留，不出现内部产品名以外的一句背景。

## License

MIT
