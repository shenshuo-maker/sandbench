"""Create, execute, and destroy one isolated container."""

from __future__ import annotations

import subprocess
import time
import uuid

from .dockerutil import LABEL, DockerError, run_docker
from .spec import IsolationSpec, RunResult, Status

# 137 is SIGKILL, which is what the cgroup OOM killer sends.
# 139 is SIGSEGV and stays an error so a crash is not reported as OOM.
_OOM_EXITS = {137}


def classify(exit_code: int | None, timed_out: bool) -> Status:
    if timed_out:
        return "timeout"
    if exit_code == 0:
        return "ok"
    if exit_code in _OOM_EXITS:
        return "oom"
    return "error"


def build_run_args(name: str, spec: IsolationSpec, command: list[str]) -> list[str]:
    """Arguments after the docker binary for `run -d`.

    No `--rm`: destroy is timed separately with `docker rm -f`.
    """
    args = [
        "run",
        "-d",
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
        args.extend(
            ["--read-only", "--tmpfs", f"/tmp:rw,noexec,nosuid,size={spec.tmpfs_size}"]
        )
    if not spec.network:
        args.extend(["--network", "none"])
    args.append(spec.image)
    args.extend(command)
    return args


def run_isolated(command: list[str], spec: IsolationSpec | None = None) -> RunResult:
    """Run `command` inside a fresh container, then remove it.

    Phases, each timed on the client:
    create = `docker run -d` (create + start),
    exec = `docker wait` until the process exits or `timeout_s` fires,
    destroy = `docker rm -f`.

    @param command: container argv, not a shell string
    @param spec: isolation limits; defaults are offline-style (no network, tight RAM)
    @returns: classified result with per-phase latency
    """
    spec = spec or IsolationSpec()
    name = f"sandbench-{uuid.uuid4().hex[:12]}"
    create_ms = exec_ms = destroy_ms = 0.0
    started = time.perf_counter()

    try:
        create_started = time.perf_counter()
        created = run_docker(build_run_args(name, spec, command), timeout_s=30)
        create_ms = (time.perf_counter() - create_started) * 1000
    except (DockerError, subprocess.TimeoutExpired) as exc:
        destroy_ms = _force_rm(name)
        return _finish(
            name=name,
            status="error",
            exit_code=None,
            create_ms=create_ms,
            exec_ms=0.0,
            destroy_ms=destroy_ms,
            stdout="",
            stderr=str(exc),
            wall_started=started,
        )

    if created.returncode != 0:
        destroy_ms = _force_rm(name)
        return _finish(
            name=name,
            status="error",
            exit_code=created.returncode,
            create_ms=create_ms,
            exec_ms=0.0,
            destroy_ms=destroy_ms,
            stdout=created.stdout[-2000:],
            stderr=(created.stderr or "docker run -d failed")[-2000:],
            wall_started=started,
        )

    exit_code, timed_out, exec_ms, wait_err = _wait_or_kill(name, spec.timeout_s)
    logs_out, logs_err = _logs(name)
    if wait_err:
        logs_err = f"{logs_err}\n{wait_err}".strip()
    destroy_ms = _force_rm(name)
    status = classify(exit_code, timed_out)
    return _finish(
        name=name,
        status=status,
        exit_code=exit_code,
        create_ms=create_ms,
        exec_ms=exec_ms,
        destroy_ms=destroy_ms,
        stdout=logs_out[-4000:],
        stderr=logs_err[-4000:],
        wall_started=started,
    )


def _wait_or_kill(name: str, timeout_s: float) -> tuple[int | None, bool, float, str]:
    """Wait up to timeout_s. On expiry, SIGKILL the container and reap it."""
    started = time.perf_counter()
    try:
        proc = run_docker(["wait", name], timeout_s=timeout_s)
    except subprocess.TimeoutExpired:
        _kill(name)
        try:
            proc = run_docker(["wait", name], timeout_s=10)
        except (DockerError, subprocess.TimeoutExpired) as exc:
            exec_ms = (time.perf_counter() - started) * 1000
            return None, True, exec_ms, str(exc)
        exec_ms = (time.perf_counter() - started) * 1000
        return _parse_exit(proc.stdout), True, exec_ms, ""
    except DockerError as exc:
        exec_ms = (time.perf_counter() - started) * 1000
        return None, False, exec_ms, str(exc)

    exec_ms = (time.perf_counter() - started) * 1000
    if proc.returncode != 0:
        return None, False, exec_ms, proc.stderr.strip() or "docker wait failed"
    return _parse_exit(proc.stdout), False, exec_ms, ""


def _parse_exit(stdout: str) -> int | None:
    text = stdout.strip().splitlines()
    if not text:
        return None
    try:
        return int(text[-1])
    except ValueError:
        return None


def _logs(name: str) -> tuple[str, str]:
    try:
        proc = run_docker(["logs", name], timeout_s=10)
    except (DockerError, subprocess.TimeoutExpired):
        return "", ""
    return proc.stdout or "", proc.stderr or ""


def _kill(name: str) -> None:
    try:
        run_docker(["kill", name], timeout_s=10)
    except (DockerError, subprocess.TimeoutExpired):
        return


def _force_rm(name: str) -> float:
    started = time.perf_counter()
    try:
        run_docker(["rm", "-f", name], timeout_s=15)
    except (DockerError, subprocess.TimeoutExpired):
        # Leftover detection after the bench catches a daemon that ignored rm.
        return (time.perf_counter() - started) * 1000
    return (time.perf_counter() - started) * 1000


def _finish(
    *,
    name: str,
    status: Status,
    exit_code: int | None,
    create_ms: float,
    exec_ms: float,
    destroy_ms: float,
    stdout: str,
    stderr: str,
    wall_started: float,
) -> RunResult:
    return RunResult(
        ok=status == "ok",
        status=status,
        exit_code=exit_code,
        latency_ms=round((time.perf_counter() - wall_started) * 1000, 2),
        create_ms=round(create_ms, 2),
        exec_ms=round(exec_ms, 2),
        destroy_ms=round(destroy_ms, 2),
        stdout=stdout,
        stderr=stderr,
        name=name,
    )
