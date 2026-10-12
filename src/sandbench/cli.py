"""CLI: run one job, run a bench, or list leftovers."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .bench import BenchReport, run_bench
from .dockerutil import host_facts, leftover_containers, prune_leftovers
from .report import render_matrix_md, render_text, write_report
from .runner import IsolationSpec, run_isolated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sandbench",
        description="Isolated container runner and lifecycle / load bench.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="run one isolated command")
    run_p.add_argument("command", nargs=argparse.REMAINDER, help="command after --")
    run_p.add_argument("--image", default="busybox")
    run_p.add_argument("--memory", default="64m")
    run_p.add_argument("--timeout", type=float, default=3.0)

    bench_p = sub.add_parser("bench", help="concurrent create/exec/destroy")
    bench_p.add_argument("--jobs", type=int, default=20)
    bench_p.add_argument("--concurrency", type=int, default=5)
    bench_p.add_argument("--workload", choices=("ok", "timeout", "oom"), default="ok")
    bench_p.add_argument("--image", default="busybox")
    bench_p.add_argument("--out", type=Path, default=Path("reports/latest.json"))

    matrix_p = sub.add_parser("matrix", help="bench concurrency 1,10,50 and print a table")
    matrix_p.add_argument("--jobs", type=int, default=50)
    matrix_p.add_argument("--concurrency", default="1,10,50")
    matrix_p.add_argument("--workload", choices=("ok", "timeout", "oom"), default="ok")
    matrix_p.add_argument("--image", default="busybox")
    matrix_p.add_argument("--out", type=Path, default=Path("reports/matrix.json"))

    sub.add_parser("leftover", help="list sandbench containers still present")
    sub.add_parser("prune", help="force-remove leftover sandbench containers")

    args = parser.parse_args(argv)
    if args.cmd == "run":
        command = args.command
        if command[:1] == ["--"]:
            command = command[1:]
        if not command:
            command = ["sh", "-c", "echo sandbench-ok"]
        spec = IsolationSpec(image=args.image, memory=args.memory, timeout_s=args.timeout)
        result = run_isolated(command, spec)
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        return 0 if result.ok else 1
    if args.cmd == "bench":
        spec = IsolationSpec(image=args.image)
        report = run_bench(args.jobs, args.concurrency, args.workload, spec)
        write_report(report, args.out)
        print(render_text(report))
        print(f"wrote {args.out}")
        return 0 if report.leftover_after == 0 else 2
    if args.cmd == "matrix":
        try:
            levels = [int(part) for part in args.concurrency.split(",") if part.strip()]
        except ValueError:
            print("concurrency must be comma-separated integers", file=sys.stderr)
            return 2
        if not levels or any(level < 1 for level in levels):
            print("concurrency must be >= 1", file=sys.stderr)
            return 2
        spec = IsolationSpec(image=args.image)
        reports: list[BenchReport] = []
        for level in levels:
            reports.append(run_bench(args.jobs, level, args.workload, spec))
        host = host_facts()
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "host": host,
            "workload": args.workload,
            "rows": [item.as_dict() for item in reports],
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        table = render_matrix_md(host, reports)
        args.out.with_suffix(".md").write_text(table, encoding="utf-8")
        print(table)
        print(f"wrote {args.out}")
        failed = [item for item in reports if item.leftover_after != 0 or item.success_rate < 1]
        return 0 if not failed else 2
    if args.cmd == "leftover":
        ids = leftover_containers()
        print("\n".join(ids) if ids else "(none)")
        return 0
    if args.cmd == "prune":
        removed = prune_leftovers()
        print(f"removed {len(removed)}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
