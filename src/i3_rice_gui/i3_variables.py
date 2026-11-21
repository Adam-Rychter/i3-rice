"""Conservative inspection of literal i3 ``set`` variables."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .settings import Setting


@dataclass(frozen=True)
class I3Variable:
    name: str
    value: str
    setting: Setting[str]


_ASSIGNMENT = re.compile(
    r"(?m)^(?P<prefix>[ \t]*set[ \t]+\$(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]+)"
    r"(?P<quote>\"?)(?P<value>[^\"\r\n#]*?)(?P=quote)(?P<suffix>[ \t]*(?:#.*)?)$"
)
_REFERENCE = re.compile(r"\$(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_INCLUDE = re.compile(r"^[ \t]*include(?:[ \t]|$)", re.MULTILINE)


def _matches(text: str) -> list[re.Match[str]]:
    return list(_ASSIGNMENT.finditer(text))


def find_variables(text: str) -> tuple[I3Variable, ...]:
    variables: list[I3Variable] = []
    seen: set[str] = set()
    for match in _matches(text):
        name = match.group("name")
        if name in seen:
            raise ValueError(f"Variable ${name} is assigned more than once.")
        seen.add(name)
        variables.append(
            I3Variable(
                name,
                match.group("value"),
                Setting(
                    match.start(), match.end(), match.group(0), match.group("value"),
                    f"variable ${name}",
                ),
            )
        )
    return tuple(variables)


def find_variable(text: str, name: str) -> Setting[str]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("Invalid i3 variable name.")
    matches = [variable for variable in find_variables(text) if variable.name == name]
    if not matches:
        raise ValueError(f"Variable ${name} was not found.")
    return matches[0].setting


def variable_references(text: str, name: str) -> tuple[int, ...]:
    """Return reference offsets excluding the variable's own assignment."""
    setting = find_variable(text, name)
    return tuple(
        match.start() for match in _REFERENCE.finditer(text)
        if match.group("name") == name
        and not setting.start <= match.start() < setting.end
    )


def has_includes(text: str) -> bool:
    return any(
        _INCLUDE.match(line) and not line.lstrip().startswith("#")
        for line in text.splitlines()
    )


def replace_variable_value(line: str, value: str) -> str:
    matches = _matches(line)
    if len(matches) != 1 or matches[0].group(0) != line:
        raise ValueError("Expected one literal i3 variable assignment.")
    if not value or '"' in value or "\r" in value or "\n" in value or "#" in value:
        raise ValueError("Variable value must be non-empty and contain no quotes, comments, or newlines.")
    match = matches[0]
    quote = match.group("quote")
    return f'{match.group("prefix")}{quote}{value}{quote}{match.group("suffix")}'
