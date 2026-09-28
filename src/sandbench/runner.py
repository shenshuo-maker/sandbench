"""Create, execute, and destroy one isolated container."""

from __future__ import annotations

import subprocess
import time
import uuid

from .dockerutil import LABEL, DockerError, run_docker
from .spec import IsolationSpec, RunResult, Status

_OOM_EXITS = {137, 139}


def classify(exit_code: int | None, timed_out: bool) -> Status:
    if timed_out:
        return "timeout"
    if exit_code == 0:
        return "ok"
    if exit_code in _OOM_EXITS:
        return "oom"
    return "error"


def run_isolated(command: list[str], spec: IsolationSpec | None = None) -> RunResult:
    """Run `command` inside a fresh container, then remove it.

    @param command: argv executed as the container PID 1 via `sh -c` join, or raw argv
    @param spec: isolation limits; defaults are offline-style (no network, tight RAM)
    @returns: classified result with wall-clock latency
    """
    spec = spec or IsolationSpec()
    name = f"sandbench-{uuid.uuid4().hex[:12]}"
    args = _docker_run_args(name, spec, command)
    client_timeout = spec.timeout_s + 8.0
    started = time.perf_counter()
    timed_out = False
    try:
        proc = run_docker(args, timeout_s=client_timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _force_rm(name)
        latency_ms = (time.perf_counter() - started) * 1000
        return RunResult(
            ok=False,
            status="timeout",
            exit_code=None,
            latency_ms=round(latency_ms, 2),
            stdout="",
            stderr="client-side timeout; container force-removed",
            name=name,
        )
    except DockerError as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return RunResult(
            ok=False,
            status="error",
            exit_code=None,
            latency_ms=round(latency_ms, 2),
            stdout="",
            stderr=str(exc),
            name=name,
        )

    latency_ms = (time.perf_counter() - started) * 1000
    status = classify(proc.returncode, timed_out=False)
    return RunResult(
        ok=status == "ok",
        status=status,
        exit_code=proc.returncode,
        latency_ms=round(latency_ms, 2),
        stdout=proc.stdout[-4000:],
        stderr=proc.stderr[-4000:],
        name=name,
    )


def _docker_run_args(name: str, spec: IsolationSpec, command: list[str]) -> list[str]:
    args = [
        "run",
        "--rm",
        "--name",
        name,
        "--label",
        LABEL,
        "--memory",
        spec.memory,
        "--memory-swap",
        spec.memory,
        "--cpus",
        spec.cpus,
        "--pids-limit",
        str(spec.pids_limit),
        "--user",
        spec.user,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
    ]
    if spec.read_only:
        args.extend(["--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m"])
    if not spec.network:
        args.extend(["--network", "none"])
    args.append(spec.image)
    args.extend(command)
    return args


def _force_rm(name: str) -> None:
    try:
        run_docker(["rm", "-f", name], timeout_s=10)
    except (DockerError, subprocess.TimeoutExpired):
        # Best-effort cleanup after a hung daemon call; leftover detection catches the rest.
        return
