"""Read-only inspection of conservative i3 keybinding syntax."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Keybinding:
    trigger: str
    command: str
    start: int
    end: int
    line: str


_LINE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)bindsym[ \t]+(?P<trigger>\S+)[ \t]+(?P<command>\S(?:.*\S)?)$"
)


def find_keybindings(text: str) -> tuple[Keybinding, ...]:
    return tuple(
        Keybinding(
            match.group("trigger"),
            match.group("command"),
            match.start(),
            match.end(),
            match.group(0),
        )
        for match in _LINE.finditer(text)
    )


def binding_conflicts(bindings: tuple[Keybinding, ...]) -> tuple[str, ...]:
    counts: dict[str, int] = {}
    for binding in bindings:
        counts[binding.trigger] = counts.get(binding.trigger, 0) + 1
    return tuple(sorted(trigger for trigger, count in counts.items() if count > 1))


def find_keybinding(text: str, trigger: str) -> Keybinding:
    matches = tuple(binding for binding in find_keybindings(text) if binding.trigger == trigger)
    if not matches:
        raise ValueError(f"Keybinding {trigger} was not found.")
    if len(matches) > 1:
        raise ValueError(f"Keybinding {trigger} is assigned more than once.")
    return matches[0]


def replace_keybinding_command(line: str, command: str) -> str:
    match = _LINE.fullmatch(line)
    if not match:
        raise ValueError("Expected one literal bindsym entry.")
    if not command.strip() or "\r" in command or "\n" in command:
        raise ValueError("Keybinding command must be non-empty and stay on one line.")
    return f"{match.group('indent')}bindsym {match.group('trigger')} {command.strip()}"
