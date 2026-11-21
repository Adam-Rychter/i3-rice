"""Conservative inspection of literal feh wallpaper startup commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class WallpaperReference:
    mode: str
    path: str
    start: int
    end: int
    line: str


_COMMAND = re.compile(
    r"(?P<prefix>^[ \t]*(?:exec|exec_always)[ \t]+(?:--no-startup-id[ \t]+)?)"
    r"feh[ \t]+--bg-(?P<mode>scale|fill|tile|center)[ \t]+"
    r"(?P<quote>\"?)(?P<path>[^\"\s#]+)(?P=quote)"
    r"(?P<suffix>[ \t]*(?:#.*)?)$",
    re.MULTILINE,
)


def find_wallpapers(text: str) -> tuple[WallpaperReference, ...]:
    return tuple(
        WallpaperReference(
            match.group("mode"),
            match.group("path"),
            match.start(),
            match.end(),
            match.group(0),
        )
        for match in _COMMAND.finditer(text)
    )


def resolve_wallpaper(path: str, config_path: Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = config_path.parent / candidate
    return candidate
