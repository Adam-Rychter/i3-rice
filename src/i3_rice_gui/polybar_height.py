"""Conservative draft editing of the shipped Polybar main bar height."""

import re

from .settings import Setting


MIN_HEIGHT = 1
MAX_HEIGHT = 200
_SECTION = re.compile(r"^[ \t]*\[([A-Za-z0-9_/-]+)\][ \t]*$")
_KEY = re.compile(r"^[ \t]*([A-Za-z0-9_/-]+)[ \t]*=(.*)$")
_HEIGHT = re.compile(
    r"(?P<prefix>[ \t]*height[ \t]*=[ \t]*)(?P<number>[0-9]+)(?P<suffix>[ \t]*)"
)
_HEIGHT_REFERENCE = re.compile(r"\$\{[^}]*\.height(?:[:}]|$)")


def parse_height_line(line: str) -> int:
    match = _HEIGHT.fullmatch(line)
    if not match:
        raise ValueError("Use a literal line such as 'height = 28'.")
    value = int(match.group("number"))
    if not MIN_HEIGHT <= value <= MAX_HEIGHT:
        raise ValueError(f"Bar height must be between {MIN_HEIGHT} and {MAX_HEIGHT}.")
    return value


def find_height(text: str) -> Setting[int]:
    sections: dict[str, dict[str, list[tuple[int, str, str]]]] = {}
    section = None
    offset = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            offset += len(raw)
            continue
        header = _SECTION.fullmatch(line)
        if header:
            section = header.group(1)
            if section in sections:
                raise ValueError("Duplicate sections need manual review.")
            sections[section] = {}
        else:
            assignment = _KEY.fullmatch(line)
            if not assignment or section is None:
                raise ValueError("Unsupported Polybar syntax needs manual review.")
            key, value = assignment.group(1), assignment.group(2).strip()
            if key in ("include-file", "include-directory"):
                raise ValueError("Included files need manual review before using this control.")
            if _HEIGHT_REFERENCE.search(value):
                raise ValueError("References to height need manual review before using this control.")
            sections[section].setdefault(key, []).append((offset, line, value))
        offset += len(raw)

    main = sections.get("bar/main")
    if main is None or len(main.get("height", [])) != 1:
        raise ValueError("Exactly one literal height in [bar/main] is required.")
    affected = ["bar/main"]
    for name, keys in sections.items():
        inherits = keys.get("inherit", [])
        if len(inherits) > 1:
            raise ValueError("Duplicate inheritance needs manual review.")
        if inherits:
            if name == "bar/main" or inherits[0][2] != "bar/main":
                raise ValueError("Complex inheritance needs manual review.")
            heights = keys.get("height", [])
            if len(heights) > 1:
                raise ValueError("Duplicate inherited heights need manual review.")
            if heights and not _HEIGHT.fullmatch(heights[0][1]):
                raise ValueError("Inherited height overrides need manual review.")
            if not heights:
                affected.append(name)
    start, line, _ = main["height"][0]
    return Setting(
        start, start + len(line), line, parse_height_line(line),
        "Affected sections: " + ", ".join(affected) + ".",
    )


def replace_height_value(line: str, value: int) -> str:
    match = _HEIGHT.fullmatch(line)
    if not match:
        raise ValueError("Bar height is not a supported literal.")
    if not MIN_HEIGHT <= value <= MAX_HEIGHT:
        raise ValueError(f"Bar height must be between {MIN_HEIGHT} and {MAX_HEIGHT}.")
    return f"{match.group('prefix')}{value}{match.group('suffix')}"
