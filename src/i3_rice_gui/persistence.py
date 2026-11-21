"""Safely persist a configuration document after conflict checks."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat
import tempfile

from .backups import BackupError, BackupResult, BackupStore, BackupVersion
from .document import ConfigDocument


class ApplyError(Exception):
    """A configuration could not be applied safely."""


class ApplyConflict(ApplyError):
    """The configuration changed after it was opened."""


@dataclass(frozen=True)
class ApplyResult:
    path: Path
    backup: BackupResult | None


def _mode(path: Path) -> int:
    try:
        info = path.stat()
    except FileNotFoundError:
        return 0o600
    if not stat.S_ISREG(info.st_mode):
        raise ApplyError("Only regular configuration files can be applied.")
    return stat.S_IMODE(info.st_mode)


def _atomic_write(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
        temporary = None
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        raise ApplyError(f"Unable to write configuration: {exc}") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass


def apply_document(
    document: ConfigDocument, backup_store: BackupStore | None = None,
) -> ApplyResult:
    """Back up and atomically apply a dirty document.

    The document baseline is rechecked immediately before the backup/write.
    Existing files are backed up before replacement; new files are created with
    private permissions.
    """
    if not document.is_dirty:
        raise ApplyError("There are no draft changes to apply.")
    try:
        if document.changed_externally():
            raise ApplyConflict("The configuration changed externally; reload before applying.")
        document.editor_text()
        content = document.draft.encode("utf-8")
    except ApplyConflict:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise ApplyError(f"Draft cannot be applied: {exc}") from exc

    backup = None
    store = backup_store or BackupStore()
    if document.baseline_exists:
        try:
            backup = store.create(document)
        except (BackupError, OSError) as exc:
            raise ApplyError(f"Unable to back up configuration: {exc}") from exc

    if document.changed_externally():
        raise ApplyConflict("The configuration changed externally; reload before applying.")
    _atomic_write(document.path, content, _mode(document.path))
    document.mark_applied()
    return ApplyResult(document.path, backup)


def restore_backup(
    document: ConfigDocument, version: BackupVersion, backup_store: BackupStore | None = None,
) -> ApplyResult:
    """Restore a verified backup, preserving the current file as a new backup."""
    if version.record.source != document.path.absolute():
        raise ApplyError("The selected backup belongs to a different configuration file.")
    try:
        if document.changed_externally():
            raise ApplyConflict("The configuration changed externally; reload before restoring.")
    except ApplyConflict:
        raise
    except OSError as exc:
        raise ApplyError(f"Unable to check the configuration before restoring: {exc}") from exc
    store = backup_store or BackupStore()
    try:
        content = store.read(version.record)
    except BackupError as exc:
        raise ApplyError(f"Unable to verify selected backup: {exc}") from exc
    try:
        text = content.decode("utf-8")
    except UnicodeError as exc:
        raise ApplyError("The selected backup is not valid UTF-8.") from exc
    if text != version.text:
        raise ApplyError("The selected backup changed; review backups again.")
    candidate = ConfigDocument(
        path=document.path,
        baseline=document.baseline,
        draft=text,
        baseline_digest=document.baseline_digest,
        baseline_exists=document.baseline_exists,
        editor_newline=document.editor_newline,
    )
    result = apply_document(candidate, store)
    document.load_draft(text)
    document.mark_applied()
    return result
