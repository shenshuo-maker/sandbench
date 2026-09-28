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
    lat = report.latency_ms
    return (
        f"sandbench jobs={report.jobs} conc={report.concurrency} "
        f"workload={report.workload} leftover={report.leftover_after}\n"
        f"  {counts}\n"
        f"  latency_ms p50={lat['p50']} p95={lat['p95']} max={lat['max']}"
    )


def write_report(report: BenchReport, path: Path) -> None:
    """Write a JSON report. Latency samples stay out of the file to keep diffs small."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **report.as_dict(),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
