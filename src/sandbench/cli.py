"""CLI: run one job, run a bench, or list leftovers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .bench import run_bench
from .dockerutil import leftover_containers, prune_leftovers
from .report import render_text, write_report
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
