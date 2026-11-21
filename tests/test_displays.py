import pytest

from i3_rice_gui.displays import Display, inspect_displays, parse_xrandr


def test_parse_xrandr_connected_and_disconnected_outputs():
    displays = parse_xrandr(
        "Screen 0: minimum 8 x 8\n"
        "DP-1 connected primary 1920x1080+0+0\n"
        "HDMI-1 disconnected (normal left inverted right x axis y axis)\n"
    )

    assert displays == (
        Display("DP-1", "connected", "1920x1080+0+0"),
        Display("HDMI-1", "disconnected", None),
    )


def test_missing_xrandr_is_reported(monkeypatch):
    monkeypatch.setattr("i3_rice_gui.displays.shutil.which", lambda _: None)
    with pytest.raises(ValueError, match="not available"):
        inspect_displays()
