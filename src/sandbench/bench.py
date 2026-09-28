"""Concurrent lifecycle bench: create / exec / destroy, then check leftovers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from .dockerutil import leftover_containers, prune_leftovers
from .runner import IsolationSpec, RunResult, run_isolated
from .spec import Status


WORKLOADS: dict[str, list[str]] = {
    "ok": ["sh", "-c", "echo sandbench-ok"],
    "timeout": ["sh", "-c", "sleep 30"],
    "oom": ["sh", "-c", "dd if=/dev/zero of=/tmp/blob bs=1M count=256"],
}


@dataclass
class BenchReport:
    jobs: int
    concurrency: int
    workload: str
    leftover_after: int
    counts: dict[str, int]
    latency_ms: dict[str, float]
    results: list[RunResult]

    def as_dict(self) -> dict[str, Any]:
        return {
            "jobs": self.jobs,
            "concurrency": self.concurrency,
            "workload": self.workload,
            "leftover_after": self.leftover_after,
            "counts": self.counts,
            "latency_ms": self.latency_ms,
        }


def percentile(values: list[float], p: float) -> float:
    """Linear interpolation percentile. Empty list returns 0."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if p <= 0:
        return float(ordered[0])
    if p >= 100:
        return float(ordered[-1])
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (p / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return float(ordered[low] + (ordered[high] - ordered[low]) * weight)


def run_bench(
    jobs: int,
    concurrency: int,
    workload: str = "ok",
    spec: IsolationSpec | None = None,
) -> BenchReport:
    """Fire `jobs` isolated runs at `concurrency`. Always prune leftovers first.

    @param jobs: total sandbox lifecycles
    @param concurrency: in-flight containers
    @param workload: ok | timeout | oom
    @param spec: isolation spec; timeout/oom workloads override timeout_s / memory
    @returns: counts, latency percentiles, leftover count after the batch
    """
    if jobs < 1:
        raise ValueError("jobs must be >= 1")
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    if workload not in WORKLOADS:
        raise ValueError(f"unknown workload: {workload}")

    spec = spec or IsolationSpec()
    if workload == "timeout":
        spec = IsolationSpec(**{**spec.as_dict(), "timeout_s": min(spec.timeout_s, 1.0)})
    if workload == "oom":
        spec = IsolationSpec(**{**spec.as_dict(), "memory": "16m", "read_only": True})

    prune_leftovers()
    command = WORKLOADS[workload]
    results: list[RunResult] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = [pool.submit(run_isolated, command, spec) for _ in range(jobs)]
        for fut in as_completed(futs):
            results.append(fut.result())

    leftover = leftover_containers()
    prune_leftovers()
    latencies = [item.latency_ms for item in results]
    counts: dict[str, int] = {key: 0 for key in ("ok", "timeout", "oom", "error")}
    for item in results:
        counts[item.status] = counts.get(item.status, 0) + 1
    return BenchReport(
        jobs=jobs,
        concurrency=concurrency,
        workload=workload,
        leftover_after=len(leftover),
        counts=counts,
        latency_ms={
            "p50": round(percentile(latencies, 50), 2),
            "p95": round(percentile(latencies, 95), 2),
            "max": round(max(latencies) if latencies else 0.0, 2),
        },
        results=results,
    )


def summarize_status(results: list[RunResult]) -> dict[Status, int]:
    counts: dict[Status, int] = {"ok": 0, "timeout": 0, "oom": 0, "error": 0}
    for item in results:
        counts[item.status] += 1
    return counts
