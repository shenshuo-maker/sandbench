"""Thin Docker CLI wrapper. The daemon is the isolation boundary, not this module."""

from __future__ import annotations

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


def prune_leftovers() -> list[str]:
    """Force-remove leftover sandbench containers. Returns the IDs removed."""
    ids = leftover_containers()
    if not ids:
        return []
    proc = run_docker(["rm", "-f", *ids], timeout_s=30)
    if proc.returncode != 0:
        raise DockerError(proc.stderr.strip() or "docker rm failed")
    return ids
