from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import stat

import pytest

from i3_rice_gui.backups import (
    BackupConflict, BackupError, BackupRecord, BackupStore, default_backup_root,
)
from i3_rice_gui.document import ConfigDocument


def test_backup_stores_original_privately_not_unsaved_draft(tmp_path):
    source = tmp_path / "config"
    source.write_bytes(b"gaps inner 5\r\n")
    document = ConfigDocument.open(source)
    document.replace(11, 12, "5", "8")
    store = BackupStore(tmp_path / "backups")

    result = store.create(document)

    bucket = store._bucket(source)
    backup = bucket / result.record.identifier
    assert store.read(result.record) == b"gaps inner 5\r\n"
    assert source.read_bytes() == b"gaps inner 5\r\n"
    assert stat.S_IMODE(bucket.stat().st_mode) == 0o700
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert store.list(source) == [result.record]
    assert store.versions(source)[0].text == "gaps inner 5\r\n"


def test_changed_source_is_not_backed_up(tmp_path):
    source = tmp_path / "config"
    source.write_text("before\n")
    document = ConfigDocument.open(source)
    source.write_text("external\n")
    root = tmp_path / "backups"
    with pytest.raises(BackupConflict):
        BackupStore(root).create(document)
    assert not root.exists()
    assert source.read_text() == "external\n"


def test_listing_missing_backups_does_not_create_storage(tmp_path):
    root = tmp_path / "backups"
    assert BackupStore(root).list(tmp_path / "config") == []
    assert BackupStore(root).versions(tmp_path / "config") == []
    assert not root.exists()
    forged = BackupRecord("../outside", tmp_path / "config", 0, "", 0)
    with pytest.raises(BackupError, match="identifier"):
        BackupStore(root).read(forged)
    assert not root.exists()


def test_replaced_non_regular_source_is_rejected_without_blocking(tmp_path):
    source = tmp_path / "config"
    source.write_text("before\n")
    document = ConfigDocument.open(source)
    source.unlink()
    os.mkfifo(source)
    with pytest.raises(BackupError, match="regular"):
        BackupStore(tmp_path / "backups").create(document)
    assert document.changed_externally()


def test_missing_baseline_cannot_backup_new_empty_file(tmp_path):
    source = tmp_path / "config"
    document = ConfigDocument.for_missing(source)
    source.write_text("")
    with pytest.raises(BackupConflict, match="No original"):
        BackupStore(tmp_path / "backups").create(document)


def test_retention_keeps_most_recent_backups_per_source(tmp_path):
    source = tmp_path / "config"
    other = tmp_path / "other"
    other.write_text("other\n")
    store = BackupStore(tmp_path / "backups", limit=2)
    other_record = store.create(ConfigDocument.open(other)).record
    results = []
    for text in ("one", "two", "three"):
        source.write_text(text)
        results.append(store.create(ConfigDocument.open(source)))
    assert results[-1].pruned == (results[0].record.identifier,)
    assert [record.identifier for record in store.list(source)] == [
        results[2].record.identifier, results[1].record.identifier
    ]
    assert store.list(other) == [other_record]
    assert not (store._bucket(source) / results[0].record.identifier).exists()


def test_default_retention_keeps_twenty(tmp_path):
    source = tmp_path / "config"
    source.write_text("unchanged")
    store = BackupStore(tmp_path / "backups")
    document = ConfigDocument.open(source)
    first = store.create(document)
    for _ in range(20):
        latest = store.create(document)
    assert latest.pruned == (first.record.identifier,)
    assert len(store.list(source)) == 20


def test_corrupt_backup_prevents_pruning_and_new_backup(tmp_path):
    source = tmp_path / "config"
    source.write_text("original")
    store = BackupStore(tmp_path / "backups", limit=1)
    first = store.create(ConfigDocument.open(source))
    payload = store._bucket(source) / first.record.identifier
    payload.write_text("tampered")
    with pytest.raises(BackupError, match="Cannot verify"):
        store.create(ConfigDocument.open(source))
    assert payload.read_text() == "tampered"


def test_retention_failure_preserves_old_backup_and_reports_new_one(tmp_path, monkeypatch):
    source = tmp_path / "config"
    source.write_text("original")
    store = BackupStore(tmp_path / "backups", limit=1)
    original = store.create(ConfigDocument.open(source)).record
    old_path = store._bucket(source) / original.identifier
    original_unlink = Path.unlink

    def unlink(path, *args, **kwargs):
        if path == old_path:
            raise PermissionError("cannot remove old backup")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    with pytest.raises(BackupError, match="was created, but retention failed"):
        store.create(ConfigDocument.open(source))
    assert store.read(original) == b"original"
    assert len(store.list(source)) == 2


def test_incomplete_backup_blocks_pruning_and_is_preserved(tmp_path):
    source = tmp_path / "config"
    source.write_text("original")
    store = BackupStore(tmp_path / "backups")
    store.create(ConfigDocument.open(source))
    pending = store._bucket(source) / (".pending-" + "a" * 32)
    pending.write_text("incomplete")
    with pytest.raises(BackupError, match="Incomplete backup"):
        store.create(ConfigDocument.open(source))
    assert pending.read_text() == "incomplete"


def test_private_storage_rejects_symlink_and_insecure_directory(tmp_path):
    source = tmp_path / "config"
    source.write_text("original")
    document = ConfigDocument.open(source)
    insecure = tmp_path / "insecure"
    insecure.mkdir(mode=0o755)
    insecure.chmod(0o755)
    with pytest.raises(BackupError, match="private"):
        BackupStore(insecure).create(document)
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(BackupError, match="private"):
        BackupStore(link).create(document)


def test_concurrent_backups_respect_retention(tmp_path):
    source = tmp_path / "config"
    source.write_text("same contents")
    document = ConfigDocument.open(source)
    store = BackupStore(tmp_path / "backups", limit=3)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: store.create(document), range(6)))
    assert len({result.record.identifier for result in results}) == 6
    assert len(store.list(source)) == 3
    assert source.read_text() == "same contents"


def test_default_backup_root_uses_absolute_xdg_path(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert default_backup_root() == tmp_path / "i3-rice/backups"
    monkeypatch.setenv("XDG_STATE_HOME", "relative")
    assert default_backup_root() == Path.home() / ".local/state/i3-rice/backups"
