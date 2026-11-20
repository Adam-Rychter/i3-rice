"""Conservative editing of literal Dunst frame colors."""

import re
from typing import Literal

from .settings import Setting


ColorSection = Literal["global", "urgency_low", "urgency_normal", "urgency_critical"]
_SECTION = re.compile(r"^[ \t]*\[([^\[\]]+)\][ \t]*(?:#.*)?$")
_START = re.compile(r"^[ \t]*frame_color(?:[ \t]*=|[ \t]|$)")
_LINE = re.compile(
    r'(?P<prefix>[ \t]*frame_color[ \t]*=[ \t]*")'
    r'(?P<color>#[0-9a-fA-F]{6})(?P<suffix>"[ \t]*)'
)
_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


def parse_color_line(line: str) -> str:
    match = _LINE.fullmatch(line)
    if not match:
        raise ValueError('Use a literal line such as frame_color = "#89b4fa".')
    return match.group("color")


def find_color(text: str, section: ColorSection) -> Setting[str]:
    if section not in ("global", "urgency_low", "urgency_normal", "urgency_critical"):
        raise ValueError(f"Unsupported Dunst section: {section}")
    selected = False
    seen = False
    candidates = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", ";")):
            if stripped.startswith("["):
                match = _SECTION.fullmatch(line)
                if not match:
                    raise ValueError("Unsupported section syntax needs manual review.")
                selected = match.group(1).strip() == section
                if selected:
                    if seen:
                        raise ValueError(f"Duplicate [{section}] sections need manual review.")
                    seen = True
            elif re.match(r"^[ \t]*(?:@include|include-file|include-directory)\b", line):
                raise ValueError("Included files need manual review before using this control.")
            elif selected and _START.match(line):
                candidates.append((offset, line))
        offset += len(raw)
    if not seen or len(candidates) != 1:
        raise ValueError(f"Exactly one literal frame_color in [{section}] is required.")
    start, line = candidates[0]
    return Setting(
        start, start + len(line), line, parse_color_line(line),
        f"Only [{section}] changes. Other rules or drop-in files can override it.",
    )


def replace_color_value(line: str, value: str) -> str:
    match = _LINE.fullmatch(line)
    if not match:
        raise ValueError("Frame color is not a supported literal.")
    if not _COLOR.fullmatch(value):
        raise ValueError("Color must be a six-digit RGB hex value.")
    return f"{match.group('prefix')}{value}{match.group('suffix')}"
