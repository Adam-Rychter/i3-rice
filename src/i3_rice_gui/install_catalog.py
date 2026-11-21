"""Curated apt package detection and reviewable installation plans."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import shutil
import subprocess
from collections.abc import Callable, Iterable


class PackageState(str, Enum):
    INSTALLED = "installed"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PackageSpec:
    component: str
    package: str
    description: str


@dataclass(frozen=True)
class PackageStatus:
    spec: PackageSpec
    state: PackageState
    detail: str = ""


@dataclass(frozen=True)
class AptPlan:
    packages: tuple[str, ...]
    unsupported_components: tuple[str, ...]
    already_installed: tuple[str, ...]
    unknown_packages: tuple[str, ...]


def apt_catalog() -> tuple[PackageSpec, ...]:
    return (
        PackageSpec("i3", "i3", "i3 window manager"),
        PackageSpec("polybar", "polybar", "Polybar status bar"),
        PackageSpec("rofi", "rofi", "Rofi launcher"),
        PackageSpec("picom", "picom", "Picom compositor"),
        PackageSpec("dunst", "dunst", "Dunst notifications"),
        PackageSpec("wallpaper", "feh", "Wallpaper image viewer"),
        PackageSpec("st", "stterm", "st terminal package"),
        PackageSpec("fonts", "fonts-jetbrains-mono", "JetBrains Mono fonts"),
        PackageSpec("displays", "arandr", "Display arrangement editor"),
    )


def _package_status(package: str) -> tuple[PackageState, str]:
    query = shutil.which("dpkg-query")
    if query is None:
        return PackageState.UNKNOWN, "dpkg-query is not available"
    try:
        result = subprocess.run(
            [query, "-W", "-f=${Status}", package],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return PackageState.UNKNOWN, f"Could not query package status: {exc}"
    if result.returncode == 0 and result.stdout.strip() == "install ok installed":
        return PackageState.INSTALLED, result.stdout.strip()
    if result.returncode == 1 and not result.stdout.strip():
        return PackageState.MISSING, "Package is not installed"
    detail = (result.stderr or result.stdout).strip()
    return PackageState.UNKNOWN, detail or f"dpkg-query exited with {result.returncode}"


def detect_apt_packages(
    catalog: Iterable[PackageSpec] | None = None,
    query: Callable[[str], tuple[PackageState, str]] = _package_status,
) -> tuple[PackageStatus, ...]:
    """Detect package ownership using dpkg, never executable presence."""
    return tuple(
        PackageStatus(spec, *query(spec.package))
        for spec in (apt_catalog() if catalog is None else catalog)
    )


def build_apt_plan(
    selected_components: Iterable[str],
    statuses: Iterable[PackageStatus],
) -> AptPlan:
    selected = set(selected_components)
    by_component = {status.spec.component: status for status in statuses}
    packages: list[str] = []
    installed: list[str] = []
    unknown: list[str] = []
    unsupported: list[str] = []
    for component in selected:
        status = by_component.get(component)
        if status is None:
            unsupported.append(component)
        elif status.state is PackageState.INSTALLED:
            installed.append(status.spec.package)
        elif status.state is PackageState.MISSING:
            packages.append(status.spec.package)
        else:
            unknown.append(status.spec.package)
    return AptPlan(
        tuple(sorted(packages)),
        tuple(sorted(unsupported)),
        tuple(sorted(installed)),
        tuple(sorted(unknown)),
    )
