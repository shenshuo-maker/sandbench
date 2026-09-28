"""Docker-backed tests. Skip when the daemon is missing."""

from __future__ import annotations

import shutil

import pytest

from sandbench.dockerutil import leftover_containers
from sandbench.runner import IsolationSpec, run_isolated
from sandbench.bench import run_bench

docker = shutil.which("docker")
pytestmark = pytest.mark.skipif(docker is None, reason="docker not on PATH")


def test_ok_run() -> None:
    result = run_isolated(["sh", "-c", "echo sandbench-ok"], IsolationSpec(timeout_s=8))
    assert result.status == "ok"
    assert "sandbench-ok" in result.stdout


def test_timeout_run() -> None:
    spec = IsolationSpec(timeout_s=1.0)
    result = run_isolated(["sh", "-c", "sleep 30"], spec)
    assert result.status == "timeout"
    assert leftover_containers() == []


def test_bench_ok_no_leftover() -> None:
    report = run_bench(jobs=4, concurrency=2, workload="ok")
    assert report.counts["ok"] == 4
    assert report.leftover_after == 0
    assert report.latency_ms["p50"] > 0
