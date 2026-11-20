"""Shared types for conservative configuration controls."""

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar


Value = TypeVar("Value")


@dataclass(frozen=True)
class Setting(Generic[Value]):
    start: int
    end: int
    line: str
    value: Value
    context: str = ""


@dataclass(frozen=True)
class NumericSetting:
    component: str
    label: str
    minimum: int
    maximum: int
    find: Callable[[str], Setting[int]]
    parse: Callable[[str], int]
    replace: Callable[[str, int], str]


@dataclass(frozen=True)
class ColorSetting:
    component: str
    label: str
    find: Callable[[str], Setting[str]]
    parse: Callable[[str], str]
    replace: Callable[[str, str], str]
