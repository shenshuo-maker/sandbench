"""Thin Docker CLI wrapper. The daemon is the isolation boundary, not this module."""

from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Sequence

LABEL = "sandbench=1"


class DockerError(RuntimeError):
    """Docker CLI failed before a container produced an exit code."""


def docker_bin() -> str:
    path = shutil.which("docker")
    if path is None:
        raise DockerError("docker not found on PATH")
    return path


def run_docker(args: Sequence[str], timeout_s: float) -> subprocess.CompletedProcess[str]:
    """Run a docker subcommand and capture text output.

    @param args: arguments after the docker binary
    @param timeout_s: client-side timeout, including daemon round-trip
    @returns: completed process with stdout/stderr as str
    """
    return subprocess.run(
        [docker_bin(), *args],
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )


def leftover_containers() -> list[str]:
    """Return container IDs still labeled as sandbench after a bench."""
    proc = run_docker(
        ["ps", "-aq", "--filter", f"label={LABEL}"],
        timeout_s=15,
    )
    if proc.returncode != 0:
        raise DockerError(proc.stderr.strip() or "docker ps failed")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def host_facts() -> dict[str, str | int]:
    """Machine and daemon facts recorded next to a benchmark table."""
    version = run_docker(["version", "--format", "{{.Server.Version}}"], timeout_s=15)
    info = run_docker(
        [
            "info",
            "--format",
            "{{.OperatingSystem}}|{{.Architecture}}|{{.NCPU}}|{{.MemTotal}}",
        ],
        timeout_s=15,
    )
    os_name, arch, ncpu, mem = ("", "", "", "")
    if info.returncode == 0 and "|" in info.stdout:
        os_name, arch, ncpu, mem = (info.stdout.strip().split("|") + ["", "", "", ""])[:4]
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "docker": version.stdout.strip() if version.returncode == 0 else "unknown",
        "docker_os": os_name,
        "arch": arch,
        "ncpu": ncpu,
        "mem_bytes": mem,
    }


def prune_leftovers() -> list[str]:
    """Force-remove leftover sandbench containers. Returns the IDs removed."""
    ids = leftover_containers()
    if not ids:
        return []
    proc = run_docker(["rm", "-f", *ids], timeout_s=30)
    if proc.returncode != 0:
        raise DockerError(proc.stderr.strip() or "docker rm failed")
    return ids
