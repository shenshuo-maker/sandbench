"""Isolation knobs and run records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Status = Literal["ok", "timeout", "oom", "error"]


@dataclass(frozen=True)
class IsolationSpec:
    """Resource and security limits applied to every run.

    This is the public contract. Keep it explicit: callers must not rely on
    Docker daemon defaults for memory, CPU, PIDs, or network.
    """

    image: str = "busybox"
    memory: str = "64m"
    cpus: str = "0.50"
    pids_limit: int = 64
    timeout_s: float = 3.0
    network: bool = False
    read_only: bool = True
    user: str = "65534:65534"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunResult:
    """One sandbox lifecycle: create, exec, destroy."""

    ok: bool
    status: Status
    exit_code: int | None
    latency_ms: float
    stdout: str
    stderr: str
    name: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
