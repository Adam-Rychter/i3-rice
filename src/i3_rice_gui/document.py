"""In-memory configuration drafts with external-change detection."""

from dataclasses import dataclass
import difflib
import hashlib
import os
from pathlib import Path
import stat

from .discovery import MAX_CONFIG_BYTES, read_config


class StaleEditError(ValueError):
    """A proposed edit no longer matches the current draft."""


@dataclass
class ConfigDocument:
    path: Path
    baseline: str
    draft: str
    baseline_digest: bytes

    @classmethod
    def open(cls, path: Path) -> "ConfigDocument":
        content = read_config(path)
        digest = hashlib.sha256(content.encode("utf-8")).digest()
        return cls(path=path, baseline=content, draft=content, baseline_digest=digest)

    @property
    def is_dirty(self) -> bool:
        return self.draft != self.baseline

    def replace(self, start: int, end: int, expected: str, replacement: str) -> None:
        if not 0 <= start <= end <= len(self.draft):
            raise ValueError("Edit range is outside the draft")
        if self.draft[start:end] != expected:
            raise StaleEditError("Edit no longer matches the current draft")
        self.draft = self.draft[:start] + replacement + self.draft[end:]

    def discard(self) -> None:
        self.draft = self.baseline

    def editor_text(self) -> str:
        normalized = self.draft.replace("\r\n", "\n")
        if "\r" in normalized or ("\r\n" in self.draft and "\n" in
                                    self.draft.replace("\r\n", "")):
            raise ValueError("Mixed or unsupported line endings require read-only inspection.")
        if "\u2029" in normalized:
            raise ValueError("This file contains a character the editor cannot preserve safely.")
        return normalized

    def set_editor_text(self, text: str) -> None:
        newline = "\r\n" if "\r\n" in self.baseline else "\n"
        self.draft = text.replace("\n", newline)

    def changed_externally(self) -> bool:
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as file:
                if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                    return True
                current = file.read(MAX_CONFIG_BYTES + 1)
        except FileNotFoundError:
            return True
        return (len(current) > MAX_CONFIG_BYTES
                or hashlib.sha256(current).digest() != self.baseline_digest)

    def diff(self) -> str:
        lines = difflib.unified_diff(
            self.baseline.splitlines(keepends=True),
            self.draft.splitlines(keepends=True),
            fromfile=f"{self.path} (original)",
            tofile=f"{self.path} (draft)",
        )
        return "".join(line if line.endswith("\n") else f"{line}\n\\ No newline at end of file\n"
                       for line in lines)
