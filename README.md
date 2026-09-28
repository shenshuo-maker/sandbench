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
| 生命周期 | 每次 run 都 `--rm`；超时强制 `rm -f`；bench 后扫 label 残留 | 调度、K8s、资源泄漏 |
| 压测 | 并发 N、jobs M，输出 p50/p95 | 性能、容量规划 |

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

并发生命周期压测（默认 20 jobs / 5 并发）：

```bash
python -m sandbench bench --jobs 20 --concurrency 5 --workload ok
```

刻意打超时（验证客户端超时后容器被清掉）：

```bash
python -m sandbench bench --jobs 6 --concurrency 3 --workload timeout
python -m sandbench leftover   # 应为 (none)
```

JSON 报告默认写到 `reports/latest.json`。

## 面试怎么讲（8 分钟）

1. **问题**：给不可信代码一个短生命周期环境，必须限制 CPU/内存/PID/网络，跑完不能留容器。
2. **取舍**：用 Docker 当隔离边界，而不是自己做内核模块；和实习里 E2B 评估后换 Cube 一样——先评估能不能交付，再压测。
3. **机制**：每次 `docker run --rm` + label；客户端超时后 `docker rm -f`；bench 结束再扫一遍残留。
4. **结果**：`ok` 负载下 leftover=0；`timeout` 负载下 status 为 timeout 且 leftover=0。数字以你机器上的 `reports/latest.json` 为准。
5. **没做的**：生产级逃逸防护、镜像构建缓存、K8s RuntimeClass。被问到就说下一步是 cgroup v2 指标和排队调度。

口述稿见 [INTERVIEW.md](INTERVIEW.md)。

## 和华为实习的关系（对外口径）

实习代码和内网 Wiki 不能开源。本仓库是 **同构的公开练习**：隔离规格、压测、残留，不出现内部产品名以外的一句背景。

## License

MIT
