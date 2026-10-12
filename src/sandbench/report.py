"""JSON + stdout reports for a bench run."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .bench import BenchReport, percentile

# Re-export for callers that imported percentile from this module.
__all__ = ["percentile", "write_report", "render_text"]


def render_text(report: BenchReport) -> str:
    counts = " ".join(f"{k}={v}" for k, v in report.counts.items())
    return (
        f"sandbench jobs={report.jobs} conc={report.concurrency} "
        f"workload={report.workload} leftover={report.leftover_after} "
        f"success_rate={report.success_rate}\n"
        f"  {counts}\n"
        f"  create_ms p50={report.create_ms['p50']} p95={report.create_ms['p95']}\n"
        f"  exec_ms p50={report.exec_ms['p50']} p95={report.exec_ms['p95']}\n"
        f"  destroy_ms p50={report.destroy_ms['p50']} p95={report.destroy_ms['p95']}\n"
        f"  total_ms p50={report.latency_ms['p50']} p95={report.latency_ms['p95']}"
    )


def render_matrix_md(host: dict, reports: list[BenchReport]) -> str:
    """Markdown table of one workload across concurrency levels."""
    mem = host.get("mem_bytes") or ""
    mem_gib = ""
    if str(mem).isdigit():
        mem_gib = f"{int(mem) / (1024 ** 3):.1f} GiB"
    lines = [
        f"- 机器：`{host.get('platform', '')}`",
        f"- Docker：{host.get('docker', '')}，{host.get('docker_os', '')}，"
        f"{host.get('arch', '')}，{host.get('ncpu', '')} CPU，{mem_gib or mem}",
        f"- Python：{host.get('python', '')}",
        "",
        "| 并发 | jobs | 成功率 | 创建 p50 (ms) | 创建 p95 (ms) | 执行 p50 (ms) | 销毁 p50 (ms) | 残留 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for report in reports:
        lines.append(
            f"| {report.concurrency} | {report.jobs} | {report.success_rate:.0%} | "
            f"{report.create_ms['p50']} | {report.create_ms['p95']} | "
            f"{report.exec_ms['p50']} | {report.destroy_ms['p50']} | "
            f"{report.leftover_after} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_report(report: BenchReport, path: Path) -> None:
    """Write a JSON report. Latency samples stay out of the file to keep diffs small."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **report.as_dict(),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
