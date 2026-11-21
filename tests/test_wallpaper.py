from pathlib import Path

from i3_rice_gui.wallpaper import find_wallpapers, resolve_wallpaper


def test_find_literal_feh_wallpaper_references():
    text = (
        "exec_always --no-startup-id feh --bg-scale ~/Pictures/wallpaper.jpg\n"
        "exec --no-startup-id feh --bg-fill /tmp/other.png # keep\n"
    )

    references = find_wallpapers(text)

    assert [(item.mode, item.path) for item in references] == [
        ("scale", "~/Pictures/wallpaper.jpg"),
        ("fill", "/tmp/other.png"),
    ]


def test_relative_wallpaper_paths_use_config_directory():
    assert resolve_wallpaper("wallpaper.jpg", Path("/home/user/.config/i3/config")) == (
        Path("/home/user/.config/i3/wallpaper.jpg")
    )
