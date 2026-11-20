"""Conservative recognition of a single literal i3 inner-gap setting."""

from dataclasses import dataclass
import re


_GAP_START = re.compile(r"^[ \t]*gaps[ \t]+inner(?:[ \t]|$)")
_INCLUDE = re.compile(r"^[ \t]*include(?:[ \t]|$)")
_GAP_LINE = re.compile(
    r"(?P<prefix>[ \t]*gaps[ \t]+inner[ \t]+)"
    r"(?P<number>[0-9]+)(?P<suffix>[ \t]*)"
)
MAX_GAP = 200


@dataclass(frozen=True)
class GapSetting:
    start: int
    end: int
    line: str
    value: int


def parse_gap_line(line: str) -> int:
    match = _GAP_LINE.fullmatch(line)
    if not match:
        raise ValueError("Use a literal line such as 'gaps inner 10'.")
    value = int(match.group("number"))
    if value > MAX_GAP:
        raise ValueError(f"Inner gap must be between 0 and {MAX_GAP}.")
    return value


def find_inner_gap(text: str) -> GapSetting:
    candidates = []
    offset = 0
    prior_braces = False
    includes = False
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            includes |= bool(_INCLUDE.match(line))
            if _GAP_START.match(line):
                candidates.append((offset, line, prior_braces))
            if "{" in line or "}" in line:
                prior_braces = True
        offset += len(raw)
    if includes:
        raise ValueError("Included files need manual review before this control can be used.")
    if len(candidates) != 1:
        raise ValueError("Exactly one literal 'gaps inner' directive is required.")
    start, line, scoped = candidates[0]
    if scoped:
        raise ValueError("Configuration scope is ambiguous before this directive.")
    return GapSetting(start, start + len(line), line, parse_gap_line(line))


def replace_gap_value(line: str, value: int) -> str:
    match = _GAP_LINE.fullmatch(line)
    if not match:
        raise ValueError("The gap directive is not a supported literal.")
    if not 0 <= value <= MAX_GAP:
        raise ValueError(f"Inner gap must be between 0 and {MAX_GAP}.")
    return f"{match.group('prefix')}{value}{match.group('suffix')}"
