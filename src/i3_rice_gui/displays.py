"""Read-only parsing of connected X11 displays."""

from __future__ import annotations

from dataclasses import dataclass
import re
import shutil
import subprocess


@dataclass(frozen=True)
class Display:
    name: str
    status: str
    geometry: str | None


_DISPLAY = re.compile(
    r"^(?P<name>\S+)\s+(?P<status>connected|disconnected)"
    r"(?:\s+(?:primary\s+)?(?P<geometry>\d+x\d+\+\d+\+\d+))?"
)


def parse_xrandr(text: str) -> tuple[Display, ...]:
    displays = []
    for line in text.splitlines():
        match = _DISPLAY.match(line)
        if match:
            displays.append(Display(
                match.group("name"), match.group("status"), match.group("geometry"),
            ))
    return tuple(displays)


def inspect_displays() -> tuple[Display, ...]:
    executable = shutil.which("xrandr")
    if not executable:
        raise ValueError("xrandr is not available in PATH.")
    try:
        result = subprocess.run(
            [executable, "--query"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Unable to inspect displays: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit {result.returncode}"
        raise ValueError(f"xrandr failed: {detail}")
    return parse_xrandr(result.stdout)
