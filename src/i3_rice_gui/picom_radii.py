"""Conservative editing of literal global Picom radius settings."""

import re
from typing import Literal

from .config_lex import mask_comments_and_strings
from .settings import Setting


RadiusKind = Literal["corner-radius", "shadow-radius"]
MAX_RADIUS = 100


def minimum_radius(kind: RadiusKind) -> int:
    if kind == "corner-radius":
        return 0
    if kind == "shadow-radius":
        return 1
    raise ValueError(f"Unsupported Picom setting: {kind}")


def _line_pattern(kind: RadiusKind) -> re.Pattern[str]:
    minimum_radius(kind)
    return re.compile(
        rf"(?P<prefix>[ \t]*{re.escape(kind)}[ \t]*=[ \t]*)"
        r"(?P<number>[0-9]+)(?P<suffix>[ \t]*;?[ \t]*)"
    )


def parse_radius_line(line: str, kind: RadiusKind) -> int:
    match = _line_pattern(kind).fullmatch(line)
    if not match:
        raise ValueError(f"Use a literal line such as '{kind} = 8;'.")
    value = int(match.group("number"))
    minimum = minimum_radius(kind)
    if not minimum <= value <= MAX_RADIUS:
        raise ValueError(f"{kind} must be between {minimum} and {MAX_RADIUS}.")
    return value


def find_radius(text: str, kind: RadiusKind) -> Setting[int]:
    minimum_radius(kind)
    masked = mask_comments_and_strings(text, hash_comments=True)
    if re.search(r"@include\b", masked):
        raise ValueError("Included files need manual review before using this control.")
    pattern = re.compile(rf"(?<![\w-]){re.escape(kind)}[ \t\r\n]*=")
    matches = list(pattern.finditer(masked))
    if len(matches) != 1:
        raise ValueError(f"Exactly one global literal '{kind}' setting is required.")
    start = matches[0].start()
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    depth_at_setting = None
    for index, character in enumerate(masked):
        if index == start:
            depth_at_setting = len(stack)
        if character in "([{":
            stack.append(character)
        elif character in pairs:
            if not stack or stack.pop() != pairs[character]:
                raise ValueError("Unbalanced configuration requires manual review.")
    if stack:
        raise ValueError("Unbalanced configuration requires manual review.")
    if depth_at_setting != 0:
        raise ValueError("Nested or per-window settings need manual review.")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end == -1:
        line_end = len(text)
    if line_end > line_start and text[line_end - 1] == "\r":
        line_end -= 1
    line = text[line_start:line_end]
    return Setting(
        line_start, line_end, line, parse_radius_line(line, kind),
        "Global setting; window exclusions and rules may override it.",
    )


def replace_radius_value(line: str, value: int, kind: RadiusKind) -> str:
    match = _line_pattern(kind).fullmatch(line)
    if not match:
        raise ValueError(f"{kind} is not a supported literal.")
    minimum = minimum_radius(kind)
    if not minimum <= value <= MAX_RADIUS:
        raise ValueError(f"{kind} must be between {minimum} and {MAX_RADIUS}.")
    return f"{match.group('prefix')}{value}{match.group('suffix')}"
