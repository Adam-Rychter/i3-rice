"""Private, bounded backups of configuration files."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import base64
import binascii
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

from .discovery import MAX_CONFIG_BYTES
from .document import ConfigDocument


BACKUP_LIMIT = 20
_IDENTIFIER = re.compile(r"[0-9a-f]{32}\Z")


class BackupError(Exception):
    """A backup operation could not be completed safely."""


class BackupConflict(BackupError):
    """The source file no longer matches the opened baseline."""


@dataclass(frozen=True)
class BackupRecord:
    identifier: str
    source: Path
    created_ns: int
    digest: str
    source_mode: int


@dataclass(frozen=True)
class BackupResult:
    record: BackupRecord
    pruned: tuple[str, ...]


@dataclass(frozen=True)
class BackupVersion:
    record: BackupRecord
    text: str


def default_backup_root() -> Path:
    state = Path(os.environ.get("XDG_STATE_HOME", ""))
    if not state.is_absolute():
        state = Path.home() / ".local/state"
    return state / "i3-rice/backups"


def _check_private_directory(path: Path) -> None:
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise BackupError(f"Backup directory must be private and owned by the current user: {path}")


def _private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    _check_private_directory(path)


def _write_private(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())


class BackupStore:
    def __init__(self, root: Path | None = None, limit: int = BACKUP_LIMIT) -> None:
        if limit < 1:
            raise ValueError("Backup limit must be at least one")
        self.root = default_backup_root() if root is None else root
        self.limit = limit

    def _bucket(self, source: Path) -> Path:
        absolute = os.path.abspath(source)
        return self.root / hashlib.sha256(os.fsencode(absolute)).hexdigest()

    @contextmanager
    def _locked_bucket(self, source: Path, create: bool = True):
        bucket = self._bucket(source)
        if create:
            _private_directory(self.root)
            _private_directory(bucket)
        else:
            try:
                _check_private_directory(self.root)
                _check_private_directory(bucket)
            except FileNotFoundError:
                yield None
                return
        flags = os.O_RDWR | os.O_NOFOLLOW
        if create:
            flags |= os.O_CREAT
        fd = os.open(bucket / ".lock", flags, 0o600)
        try:
            with os.fdopen(fd, "r+b") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                try:
                    yield bucket
                finally:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        except OSError as exc:
            raise BackupError(f"Backup operation failed: {exc}") from exc

    def _read_record(self, path: Path, source: Path) -> tuple[BackupRecord, bytes]:
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as file:
                if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                    raise ValueError("backup is not a regular file")
                metadata_bytes = file.read(2 * MAX_CONFIG_BYTES + 1)
            if len(metadata_bytes) > 2 * MAX_CONFIG_BYTES:
                raise ValueError("backup is too large")
            metadata = json.loads(metadata_bytes.decode("utf-8"))
            if not isinstance(metadata, dict):
                raise ValueError("metadata is not an object")
            identifier = metadata["id"]
            original = metadata["source"]
            created_ns = metadata["created_ns"]
            digest = metadata["sha256"]
            source_mode = metadata["source_mode"]
            data = base64.b64decode(metadata["content"], validate=True)
            if (metadata.get("version") != 1
                    or identifier != path.name or original != os.path.abspath(source)
                    or not isinstance(created_ns, int) or isinstance(created_ns, bool)
                    or created_ns < 0
                    or not isinstance(source_mode, int) or isinstance(source_mode, bool)
                    or not 0 <= source_mode <= 0o7777
                    or len(data) > MAX_CONFIG_BYTES or not isinstance(digest, str)
                    or hashlib.sha256(data).hexdigest() != digest):
                raise ValueError("backup metadata or content does not match")
            return BackupRecord(identifier, Path(original), created_ns, digest, source_mode), data
        except (OSError, UnicodeError, binascii.Error, json.JSONDecodeError,
                KeyError, TypeError, ValueError) as exc:
            raise BackupError(f"Cannot verify backup {path}: {exc}") from exc

    def _list(self, bucket: Path, source: Path) -> list[BackupRecord]:
        records = []
        for entry in bucket.iterdir():
            if entry.name.startswith(".pending-") and _IDENTIFIER.fullmatch(entry.name[9:]):
                raise BackupError(f"Incomplete backup requires manual review: {entry}")
            if _IDENTIFIER.fullmatch(entry.name):
                record, _ = self._read_record(entry, source)
                records.append(record)
        return sorted(records, key=lambda record: (record.created_ns, record.identifier), reverse=True)

    def list(self, source: Path) -> list[BackupRecord]:
        with self._locked_bucket(source, create=False) as bucket:
            if bucket is None:
                return []
            return self._list(bucket, source)

    def read(self, record: BackupRecord) -> bytes:
        if not _IDENTIFIER.fullmatch(record.identifier):
            raise BackupError("Invalid backup identifier.")
        with self._locked_bucket(record.source, create=False) as bucket:
            if bucket is None:
                raise BackupError("The selected backup no longer exists.")
            current, content = self._read_record(bucket / record.identifier, record.source)
            if current != record:
                raise BackupError("Backup metadata changed since it was selected.")
            return content

    def versions(self, source: Path) -> list[BackupVersion]:
        with self._locked_bucket(source, create=False) as bucket:
            if bucket is None:
                return []
            versions = []
            for record in self._list(bucket, source):
                current, content = self._read_record(bucket / record.identifier, source)
                if current != record:
                    raise BackupError("Backup metadata changed while loading.")
                try:
                    text = content.decode("utf-8")
                except UnicodeError as exc:
                    raise BackupError(f"Backup is not valid UTF-8: {record.identifier}") from exc
                versions.append(BackupVersion(record, text))
            return versions

    def create(self, document: ConfigDocument) -> BackupResult:
        if not document.baseline_exists:
            raise BackupConflict("No original configuration exists to back up.")
        try:
            fd = os.open(document.path, os.O_RDONLY | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as file:
                info = os.fstat(file.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise BackupError("Only regular configuration files can be backed up.")
                content = file.read(MAX_CONFIG_BYTES + 1)
        except OSError as exc:
            raise BackupError(f"Cannot read configuration: {exc}") from exc
        digest = hashlib.sha256(content).digest()
        if len(content) > MAX_CONFIG_BYTES or digest != document.baseline_digest:
            raise BackupConflict("The configuration changed externally; reload before backing up.")

        with self._locked_bucket(document.path) as bucket:
            existing = self._list(bucket, document.path)
            record = BackupRecord(
                uuid.uuid4().hex,
                Path(os.path.abspath(document.path)),
                time.time_ns(),
                digest.hex(),
                stat.S_IMODE(info.st_mode),
            )
            metadata = {
                "version": 1,
                "id": record.identifier,
                "source": str(record.source),
                "created_ns": record.created_ns,
                "sha256": record.digest,
                "source_mode": record.source_mode,
                "content": base64.b64encode(content).decode("ascii"),
            }
            pending = bucket / f".pending-{record.identifier}"
            final = bucket / record.identifier
            created = False
            try:
                _write_private(pending, json.dumps(metadata, ensure_ascii=True).encode("utf-8"))
                os.link(pending, final, follow_symlinks=False)
                created = True
                pending.unlink()
            except OSError as exc:
                try:
                    pending.unlink(missing_ok=True)
                except OSError as cleanup:
                    raise BackupError(
                        f"Backup cleanup failed for {pending}: {cleanup}"
                    ) from exc
                if created:
                    raise BackupError(
                        f"Backup {record.identifier} was created, but cleanup failed: {exc}"
                    ) from exc
                raise

            pruned = []
            for old in existing[self.limit - 1:]:
                old_path = bucket / old.identifier
                try:
                    self._read_record(old_path, document.path)
                    old_path.unlink()
                except (BackupError, OSError) as exc:
                    raise BackupError(
                        f"Backup {record.identifier} was created, but retention failed: {exc}"
                    ) from exc
                pruned.append(old.identifier)
            return BackupResult(record, tuple(pruned))
