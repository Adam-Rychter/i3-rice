"""In-memory configuration drafts with external-change detection."""

from dataclasses import dataclass
import difflib
import hashlib
from pathlib import Path

from .discovery import read_config


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

    def changed_externally(self) -> bool:
        try:
            with self.path.open("rb") as file:
                digest = hashlib.sha256()
                for chunk in iter(lambda: file.read(65536), b""):
                    digest.update(chunk)
        except FileNotFoundError:
            return True
        return digest.digest() != self.baseline_digest

    def diff(self) -> str:
        lines = difflib.unified_diff(
            self.baseline.splitlines(keepends=True),
            self.draft.splitlines(keepends=True),
            fromfile=f"{self.path} (original)",
            tofile=f"{self.path} (draft)",
        )
        return "".join(line if line.endswith("\n") else f"{line}\n\\ No newline at end of file\n"
                       for line in lines)
