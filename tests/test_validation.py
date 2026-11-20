from pathlib import Path
import shutil
import subprocess

import pytest

from i3_rice_gui.validation import ValidationStatus, validate_i3


def test_missing_validator_is_reported(monkeypatch):
    monkeypatch.setattr("i3_rice_gui.validation.shutil.which", lambda name: None)
    result = validate_i3("gaps inner 10\n")
    assert result.status == ValidationStatus.UNAVAILABLE
    assert "not available" in result.summary


def test_include_is_not_checked_against_unstaged_files(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("validator must not run")

    monkeypatch.setattr("i3_rice_gui.validation.subprocess.run", forbidden)
    for config in ("include ~/.config/i3/extra\n", "set $x include\n$x foo\n", "$command value\n"):
        assert validate_i3(config).status == ValidationStatus.UNAVAILABLE


def test_oversized_draft_is_not_executed(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("validator must not run")

    monkeypatch.setattr("i3_rice_gui.validation.subprocess.run", forbidden)
    assert validate_i3("a" * (1024 * 1024 + 1)).status == ValidationStatus.UNAVAILABLE


def test_validator_receives_staged_content_and_reports_invalid(monkeypatch):
    monkeypatch.setattr("i3_rice_gui.validation.shutil.which", lambda name: "/usr/bin/i3")

    def run(args, **kwargs):
        assert args[:3] == ["/usr/bin/i3", "-C", "-c"]
        assert Path(args[3]).read_text() == "gaps inner bad\n"
        assert kwargs["timeout"] == 10.0
        return subprocess.CompletedProcess(args, 1, "", "ERROR: CONFIG: bad syntax")

    monkeypatch.setattr("i3_rice_gui.validation.subprocess.run", run)
    result = validate_i3("gaps inner bad\n")
    assert result.status == ValidationStatus.INVALID
    assert "bad syntax" in result.details


def test_unexpected_failure_and_timeout_are_not_reported_as_invalid(monkeypatch):
    monkeypatch.setattr("i3_rice_gui.validation.shutil.which", lambda name: "/usr/bin/i3")
    monkeypatch.setattr(
        "i3_rice_gui.validation.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "display error"),
    )
    assert validate_i3("gaps inner 10\n").status == ValidationStatus.UNAVAILABLE

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 10)

    monkeypatch.setattr("i3_rice_gui.validation.subprocess.run", timeout)
    assert "timed out" in validate_i3("gaps inner 10\n").summary


@pytest.mark.skipif(shutil.which("i3") is None, reason="i3 is not installed")
def test_real_i3_validator_checks_syntax_without_running_exec(tmp_path):
    sentinel = tmp_path / "must-not-exist"
    valid = f"gaps inner 10\nexec touch {sentinel}\n"
    assert validate_i3(valid).status == ValidationStatus.VALID
    assert not sentinel.exists()
    invalid = validate_i3("gaps inner not-a-number\n")
    assert invalid.status == ValidationStatus.INVALID
    assert invalid.details
