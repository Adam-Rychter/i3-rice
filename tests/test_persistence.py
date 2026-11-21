import stat

import pytest

from i3_rice_gui.backups import BackupStore
from i3_rice_gui.document import ConfigDocument
from i3_rice_gui.persistence import ApplyConflict, ApplyError, apply_document, restore_backup


def test_apply_creates_backup_and_updates_document(tmp_path):
    source = tmp_path / "config"
    source.write_bytes(b"gaps inner 5\r\n")
    source.chmod(0o640)
    document = ConfigDocument.open(source)
    document.replace(11, 12, "5", "8")

    result = apply_document(document, BackupStore(tmp_path / "backups"))

    assert result.backup is not None
    assert source.read_bytes() == b"gaps inner 8\r\n"
    assert stat.S_IMODE(source.stat().st_mode) == 0o640
    assert not document.is_dirty
    assert not document.changed_externally()
    assert result.backup.record.source == source.resolve()


def test_apply_blocks_external_change_without_overwriting(tmp_path):
    source = tmp_path / "config"
    source.write_text("before\n")
    document = ConfigDocument.open(source)
    document.load_draft("draft\n")
    source.write_text("external\n")

    with pytest.raises(ApplyConflict):
        apply_document(document, BackupStore(tmp_path / "backups"))

    assert source.read_text() == "external\n"
    assert document.draft == "draft\n"


def test_apply_creates_missing_file_with_private_mode(tmp_path):
    source = tmp_path / "nested/config"
    document = ConfigDocument.for_missing(source)
    document.load_draft("new config\n")

    result = apply_document(document, BackupStore(tmp_path / "backups"))

    assert result.backup is None
    assert source.read_text() == "new config\n"
    assert stat.S_IMODE(source.stat().st_mode) == 0o600
    assert not document.is_dirty


def test_apply_rejects_clean_document(tmp_path):
    source = tmp_path / "config"
    source.write_text("unchanged\n")

    with pytest.raises(ApplyError, match="no draft changes"):
        apply_document(ConfigDocument.open(source), BackupStore(tmp_path / "backups"))


def test_restore_backup_backs_up_current_file_and_updates_document(tmp_path):
    source = tmp_path / "config"
    source.write_text("before\n")
    store = BackupStore(tmp_path / "backups")
    original = store.create(ConfigDocument.open(source))
    source.write_text("current\n")
    document = ConfigDocument.open(source)

    result = restore_backup(document, store.versions(source)[0], store)

    assert result.backup is not None
    assert source.read_text() == "before\n"
    assert document.draft == "before\n"
    assert not document.is_dirty
    assert len(store.list(source)) == 2
    assert store.read(original.record) == b"before\n"


def test_restore_backup_rejects_external_change(tmp_path):
    source = tmp_path / "config"
    source.write_text("before\n")
    store = BackupStore(tmp_path / "backups")
    store.create(ConfigDocument.open(source))
    document = ConfigDocument.open(source)
    source.write_text("external\n")

    with pytest.raises(ApplyConflict):
        restore_backup(document, store.versions(source)[0], store)

    assert source.read_text() == "external\n"
