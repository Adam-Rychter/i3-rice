"""Conservative editing of a literal Rofi window border radius."""

import re

from .config_lex import mask_comments_and_strings
from .settings import Setting


MAX_RADIUS = 100
_LINE = re.compile(
    r"(?P<prefix>[ \t]*border-radius[ \t]*:[ \t]*)"
    r"(?P<number>[0-9]+)(?P<suffix>px[ \t]*;[ \t]*)"
)
_PROPERTY = re.compile(r"(?<![\w-])border-radius[ \t\r\n]*:")


def parse_radius_line(line: str) -> int:
    match = _LINE.fullmatch(line)
    if not match:
        raise ValueError("Use a literal line such as 'border-radius: 8px;'.")
    value = int(match.group("number"))
    if not 0 <= value <= MAX_RADIUS:
        raise ValueError(f"Window radius must be between 0 and {MAX_RADIUS}.")
    return value


def find_radius(text: str) -> Setting[int]:
    masked = mask_comments_and_strings(
        text, hash_comments=False, single_quotes=True, nested_comments=True,
    )
    if re.search(r"@(import|theme|media)\b|@\s*\{", masked):
        raise ValueError("Imports, themes, and dynamic scopes need manual review.")
    blocks = []
    depth = 0
    previous_end = 0
    block_start = 0
    selector = ""
    for index, character in enumerate(masked):
        if character == "{":
            if depth == 0:
                selector = masked[previous_end:index].strip()
                if not selector:
                    raise ValueError("Unsupported theme syntax needs manual review.")
                block_start = index + 1
            depth += 1
        elif character == "}":
            depth -= 1
            if depth < 0:
                raise ValueError("Unbalanced theme needs manual review.")
            if depth == 0:
                blocks.append((selector, block_start, index))
                previous_end = index + 1
    if depth or masked[previous_end:].strip():
        raise ValueError("Unbalanced or unsupported theme syntax needs manual review.")
    for selector, _, _ in blocks:
        if selector != "window" and re.search(r"\bwindow\b", selector):
            raise ValueError("Additional window selectors need manual review.")
    windows = [(start, end) for selector, start, end in blocks if selector == "window"]
    if len(windows) != 1:
        raise ValueError("Exactly one window section is required.")
    start, end = windows[0]
    block = masked[start:end]
    if "{" in block or "}" in block:
        raise ValueError("Nested window sections need manual review.")
    matches = list(_PROPERTY.finditer(block))
    if len(matches) != 1:
        raise ValueError("Exactly one literal window border-radius is required.")
    position = start + matches[0].start()
    line_start = text.rfind("\n", 0, position) + 1
    line_end = text.find("\n", position)
    if line_end == -1:
        line_end = len(text)
    if line_end > line_start and text[line_end - 1] == "\r":
        line_end -= 1
    line = text[line_start:line_end]
    return Setting(
        line_start, line_end, line, parse_radius_line(line),
        "This edits the selected theme only; other theme files may override it.",
    )


def replace_radius_value(line: str, value: int) -> str:
    match = _LINE.fullmatch(line)
    if not match:
        raise ValueError("Window radius is not a supported literal.")
    if not 0 <= value <= MAX_RADIUS:
        raise ValueError(f"Window radius must be between 0 and {MAX_RADIUS}.")
    return f"{match.group('prefix')}{value}{match.group('suffix')}"
