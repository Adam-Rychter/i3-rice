"""Read-only discovery of the desktop and component configuration."""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import stat
from typing import Mapping


MAX_CONFIG_BYTES = 1024 * 1024


@dataclass(frozen=True)
class Component:
    key: str
    title: str
    description: str
    commands: tuple[str, ...]
    configs: tuple[Path, ...]


@dataclass(frozen=True)
class ComponentStatus:
    component: Component
    executables: tuple[tuple[str, str | None], ...]
    configs: tuple[tuple[Path, str], ...]


@dataclass(frozen=True)
class DesktopStatus:
    session: str
    desktop: str
    components: tuple[ComponentStatus, ...]


def components(home: Path, environ: Mapping[str, str]) -> tuple[Component, ...]:
    config_dir = Path(environ.get("XDG_CONFIG_HOME", ""))
    if not config_dir.is_absolute():
        config_dir = home / ".config"
    i3 = (config_dir / "i3/config", home / ".i3/config")
    return (
        Component("i3", "i3", "Window layout, gaps and borders", ("i3",), i3),
        Component("workspaces", "Workspaces & keys", "Workspaces and keyboard shortcuts", ("i3",), i3),
        Component("polybar", "Polybar", "Status bar and modules", ("polybar",),
                  (config_dir / "polybar/config.ini", config_dir / "polybar/config")),
        Component("rofi", "Rofi", "Application launcher", ("rofi",),
                  (config_dir / "rofi/config.rasi", config_dir / "rofi/catppuccin-mocha.rasi")),
        Component("picom", "Picom", "Compositing, shadows and opacity", ("picom",),
                  (config_dir / "picom/picom.conf", config_dir / "picom.conf")),
        Component("dunst", "Dunst", "Desktop notifications", ("dunst",),
                  (config_dir / "dunst/dunstrc",)),
        Component("wallpaper", "Wallpaper", "Background image and startup", ("feh",), i3),
        Component("st", "st terminal", "Terminal font and colors", ("st",),
                  (home / ".cache/i3-rice/st-0.9.3/config.h",)),
        Component("fonts", "Fonts & scaling", "Fonts and display scaling", ("fc-list",),
                  (config_dir / "i3/Xresources", config_dir / "i3/scale.env",
                   home / ".Xresources")),
        Component("displays", "Displays", "Monitor detection and arrangement", ("xrandr",), i3),
    )


def config_status(path: Path) -> str:
    try:
        info = path.stat()
    except FileNotFoundError:
        return "Not found"
    except OSError as exc:
        return f"Unavailable: {exc.strerror or exc}"
    if not stat.S_ISREG(info.st_mode):
        return "Not a regular file"
    return "Found"


def discover(home: Path | None = None, environ: Mapping[str, str] | None = None) -> DesktopStatus:
    env = os.environ if environ is None else environ
    home = Path.home() if home is None else home
    if env.get("WAYLAND_DISPLAY"):
        session = "Wayland"
    elif env.get("DISPLAY"):
        session = "X11"
    else:
        session = "Not detected"
    desktop = env.get("XDG_CURRENT_DESKTOP") or env.get("DESKTOP_SESSION") or "Not detected"
    statuses = []
    for component in components(home, env):
        executables = tuple((name, shutil.which(name, path=env.get("PATH", "")))
                            for name in component.commands)
        configs = tuple((path, config_status(path)) for path in component.configs)
        statuses.append(ComponentStatus(component, executables, configs))
    return DesktopStatus(session, desktop, tuple(statuses))


def read_config(path: Path, max_bytes: int = MAX_CONFIG_BYTES) -> str:
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as file:
        if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
            raise ValueError("Configuration is not a regular file")
        content = file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise ValueError(f"File exceeds the {max_bytes // 1024} KiB preview limit")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("File is not valid UTF-8") from exc
