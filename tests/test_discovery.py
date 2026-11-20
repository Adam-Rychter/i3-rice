from pathlib import Path
import os

import pytest

from i3_rice_gui.discovery import components, discover, read_config


def test_discovery_uses_xdg_config_and_reports_executable_and_missing_files(tmp_path):
    config = tmp_path / "custom-config"
    i3_config = config / "i3" / "config"
    i3_config.parent.mkdir(parents=True)
    i3_config.write_text("# existing config\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "i3"
    executable.write_text("")
    executable.chmod(0o755)
    env = {"XDG_CONFIG_HOME": str(config), "PATH": str(bin_dir), "DISPLAY": ":1"}

    result = discover(tmp_path, env)

    assert result.session == "X11"
    assert result.components[0].executables == (("i3", str(executable)),)
    assert result.components[0].configs == (
        (i3_config, "Found"), (tmp_path / ".i3/config", "Not found")
    )
    assert result.components[2].executables == (("polybar", None),)
    assert result.components[3].configs == (
        (config / "rofi/config.rasi", "Not found"),
        (config / "rofi/catppuccin-mocha.rasi", "Not found"),
    )
    assert i3_config.read_text() == "# existing config\n"


def test_relative_xdg_path_falls_back_to_home_and_wayland_is_reported(tmp_path):
    env = {"XDG_CONFIG_HOME": "relative", "WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}
    assert components(tmp_path, env)[0].configs[0] == tmp_path / ".config/i3/config"
    assert discover(tmp_path, env).session == "Wayland"


def test_read_config_reports_unreadable_content_and_size(tmp_path):
    path = tmp_path / "config"
    path.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="UTF-8"):
        read_config(path)
    path.write_bytes(b"12345")
    with pytest.raises(ValueError, match="preview limit"):
        read_config(path, max_bytes=4)
    with pytest.raises(FileNotFoundError):
        read_config(Path(tmp_path / "missing"))
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="regular"):
        read_config(fifo)
