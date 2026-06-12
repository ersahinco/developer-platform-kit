from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import Callable

from scripts.platform.local_kubernetes.constants import ROOT


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[[list[str]], CommandResult]


class ProofError(RuntimeError):
    pass


def run_command(command: list[str]) -> CommandResult:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return CommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def checked(command: list[str], runner: CommandRunner = run_command) -> CommandResult:
    result = runner(command)
    if result.returncode != 0:
        raise ProofError(
            "command failed: "
            + " ".join(command)
            + f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result
