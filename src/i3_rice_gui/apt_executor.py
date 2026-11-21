"""Bounded apt execution for an already reviewed package plan."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence

from .install_catalog import AptPlan


class InstallState(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class InstallOperation:
    package: str
    state: InstallState
    detail: str


@dataclass(frozen=True)
class AptExecutionResult:
    refreshed: bool
    refresh_detail: str
    operations: tuple[InstallOperation, ...]


class AptExecutionError(Exception):
    """The reviewed apt plan cannot be executed safely."""


_PACKAGE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9+.-]*\Z")


def _validate_plan(plan: AptPlan) -> tuple[str, ...]:
    if plan.unsupported_components:
        raise AptExecutionError(
            "Cannot install unsupported components: "
            + ", ".join(plan.unsupported_components)
        )
    if plan.unknown_packages:
        raise AptExecutionError(
            "Cannot install packages with unknown status: "
            + ", ".join(plan.unknown_packages)
        )
    packages = tuple(dict.fromkeys(plan.packages))
    invalid = [package for package in packages if not _PACKAGE_NAME.fullmatch(package)]
    if invalid:
        raise AptExecutionError("Invalid apt package name: " + ", ".join(invalid))
    return packages


def execute_apt_plan(
    plan: AptPlan,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
    timeout: float = 900,
) -> AptExecutionResult:
    """Execute only the package operations represented by an approved plan."""
    packages = _validate_plan(plan)
    if not packages:
        return AptExecutionResult(True, "No missing packages.", ())
    pkexec = which("pkexec")
    apt_get = which("apt-get")
    if pkexec is None:
        raise AptExecutionError("pkexec is unavailable; package installation was not attempted.")
    if apt_get is None:
        raise AptExecutionError("apt-get is unavailable; package installation was not attempted.")

    refresh = runner(
        [pkexec, apt_get, "update"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    refresh_detail = _output(refresh)
    if refresh.returncode != 0:
        return AptExecutionResult(
            False, refresh_detail or f"apt index refresh failed with exit {refresh.returncode}.",
            tuple(
                InstallOperation(package, InstallState.SKIPPED, "Skipped because apt refresh failed.")
                for package in packages
            ),
        )

    operations = []
    for package in packages:
        result = runner(
            [pkexec, apt_get, "install", "-y", "--no-install-recommends", package],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        detail = _output(result)
        if result.returncode == 0:
            operations.append(InstallOperation(package, InstallState.SUCCEEDED, detail))
        else:
            operations.append(
                InstallOperation(
                    package, InstallState.FAILED,
                    detail or f"apt install failed with exit {result.returncode}.",
                )
            )
    return AptExecutionResult(True, refresh_detail, tuple(operations))


def _output(result: subprocess.CompletedProcess[str]) -> str:
    detail = "\n".join(
        part.strip() for part in (result.stdout, result.stderr) if part and part.strip()
    )
    return detail[-16000:]
