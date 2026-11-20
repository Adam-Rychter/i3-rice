"""Conservative recognition of literal i3 appearance settings."""

from dataclasses import dataclass
import re
from typing import Literal

from .settings import Setting


SettingKind = Literal["inner", "outer", "pixel_border"]
_INCLUDE = re.compile(r"^[ \t]*include(?:[ \t]|$)")
MAX_GAP = 200
MAX_BORDER = 20


@dataclass(frozen=True)
class SettingDefinition:
    label: str
    start: re.Pattern[str]
    line: re.Pattern[str]
    minimum: int
    maximum: int
    example: str


def setting_definition(kind: SettingKind) -> SettingDefinition:
    if kind == "inner":
        label, start, prefix = "Inner gap", r"gaps[ \t]+inner", r"gaps[ \t]+inner"
        minimum, maximum = 0, MAX_GAP
        example = "gaps inner 10"
    elif kind == "outer":
        label, start, prefix = "Outer gap", r"gaps[ \t]+outer", r"gaps[ \t]+outer"
        minimum, maximum = -MAX_GAP, MAX_GAP
        example = "gaps outer -10"
    elif kind == "pixel_border":
        label, start, prefix = "Pixel border", r"default_border", r"default_border[ \t]+pixel"
        minimum, maximum = 0, MAX_BORDER
        example = "default_border pixel 2"
    else:
        raise ValueError(f"Unsupported setting kind: {kind}")
    number = r"-?[0-9]+" if minimum < 0 else r"[0-9]+"
    start_pattern = re.compile(rf"^[ \t]*{start}(?:[ \t]|$)")
    line = re.compile(
        rf"(?P<prefix>[ \t]*{prefix}[ \t]+)"
        rf"(?P<number>{number})(?P<suffix>[ \t]*)"
    )
    return SettingDefinition(label, start_pattern, line, minimum, maximum, example)


def parse_setting_line(line: str, kind: SettingKind) -> int:
    definition = setting_definition(kind)
    match = definition.line.fullmatch(line)
    if not match:
        raise ValueError(f"Use a literal line such as '{definition.example}'.")
    value = int(match.group("number"))
    if not definition.minimum <= value <= definition.maximum:
        raise ValueError(
            f"{definition.label} must be between {definition.minimum} and {definition.maximum}."
        )
    return value


def find_setting(text: str, kind: SettingKind) -> Setting[int]:
    definition = setting_definition(kind)
    candidates = []
    offset = 0
    prior_braces = False
    includes = False
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            includes |= bool(_INCLUDE.match(line))
            if definition.start.match(line):
                candidates.append((offset, line, prior_braces))
            if "{" in line or "}" in line:
                prior_braces = True
        offset += len(raw)
    if includes:
        raise ValueError("Included files need manual review before this control can be used.")
    if len(candidates) != 1:
        raise ValueError(f"Exactly one literal '{definition.example}' directive is required.")
    start, line, scoped = candidates[0]
    if scoped:
        raise ValueError("Configuration scope is ambiguous before this directive.")
    return Setting(start, start + len(line), line, parse_setting_line(line, kind))


def replace_setting_value(line: str, value: int, kind: SettingKind) -> str:
    definition = setting_definition(kind)
    match = definition.line.fullmatch(line)
    if not match:
        raise ValueError(f"{definition.label} is not a supported literal.")
    if not definition.minimum <= value <= definition.maximum:
        raise ValueError(
            f"{definition.label} must be between {definition.minimum} and {definition.maximum}."
        )
    return f"{match.group('prefix')}{value}{match.group('suffix')}"
