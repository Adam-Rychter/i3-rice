"""Conservative parsing and editing for literal i3 workspace labels."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .settings import Setting


@dataclass(frozen=True)
class WorkspaceLabel:
    number: int
    name: str
    setting: Setting[str]


_ASSIGNMENT = re.compile(
    r"(?m)^(?P<prefix>[ \t]*set[ \t]+\$ws(?P<number>[1-9][0-9]*)[ \t]+)"
    r"(?P<quote>\"?)(?P<name>[^\"\r\n#]*)(?P=quote)(?P<suffix>[ \t]*(?:#.*)?)$"
)
_UNSUPPORTED = re.compile(r"(?m)^[ \t]*set[ \t]+\$ws[1-9][0-9]*[ \t]+")


def _matches(text: str) -> list[re.Match[str]]:
    matches = list(_ASSIGNMENT.finditer(text))
    for match in matches:
        if not match.group("quote"):
            raise ValueError("Workspace labels must use quoted literal values.")
    covered = {match.start() for match in matches}
    unsupported = next(
        (match for match in _UNSUPPORTED.finditer(text) if match.start() not in covered),
        None,
    )
    if unsupported is not None:
        raise ValueError(
            f"Workspace assignment at character {unsupported.start()} is unsupported."
        )
    return matches


def find_workspace_labels(text: str) -> tuple[WorkspaceLabel, ...]:
    matches = _matches(text)
    labels = []
    seen: set[int] = set()
    for match in matches:
        number = int(match.group("number"))
        if number in seen:
            raise ValueError(f"Workspace ${number} is assigned more than once.")
        seen.add(number)
        name = match.group("name")
        start = match.start()
        end = match.end()
        labels.append(
            WorkspaceLabel(
                number,
                name,
                Setting(start, end, match.group(0), name, f"workspace ${number}"),
            )
        )
    return tuple(sorted(labels, key=lambda label: label.number))


def find_workspace(text: str, number: int) -> Setting[str]:
    if number < 1:
        raise ValueError("Workspace number must be positive.")
    for label in find_workspace_labels(text):
        if label.number == number:
            return label.setting
    raise ValueError(f"Workspace ${number} was not found.")


def parse_workspace_line(line: str) -> tuple[int, str]:
    matches = _matches(line)
    if len(matches) != 1 or matches[0].group(0) != line:
        raise ValueError("Expected one quoted workspace assignment.")
    match = matches[0]
    return int(match.group("number")), match.group("name")


def replace_workspace_label(line: str, name: str) -> str:
    number, _ = parse_workspace_line(line)
    if not name or '"' in name or "\r" in name or "\n" in name or "#" in name:
        raise ValueError("Workspace label must be non-empty and contain no quotes, comments, or newlines.")
    return f'set $ws{number} "{name}"'
