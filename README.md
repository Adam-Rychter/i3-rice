# i3 Rice — Catppuccin Mocha

A minimal, keyboard-driven tiling desktop for **X11**. It was built for **Linux Mint 22.3 on NVIDIA** as a
replacement for Cinnamon, but the installer detects the package manager and maps package names for
Debian/Ubuntu, Fedora, Arch, openSUSE, and Alpine, so it can be tested in VMs on other distributions.

The design goal is low idle resource use, one workspace per app, and a single consistent
[Catppuccin Mocha](https://github.com/catppuccin/catppuccin) palette across every component.

---

## Distro support

The installer is not tied to one distribution. It detects the first available package manager and installs
distro-specific package names for the same logical stack.

| Family | Manager | Detected by | Install command |
|---|---|---|---|
| Debian / Ubuntu / Mint | apt | `apt-get` | `apt-get install -y --no-install-recommends` |
| Fedora / RHEL | dnf | `dnf` | `dnf install -y` |
| Arch / Manjaro | pacman | `pacman` | `pacman -S --needed --noconfirm` |
| openSUSE | zypper | `zypper` | `zypper --non-interactive install --no-recommends` |
| Alpine | apk | `apk` | `apk add --no-cache` |

- Run `./install-i3-rice.sh --list-packages` to see the exact names that will be used on the current machine.
- Force a manager with `--package-manager apt|dnf|pacman|zypper|apk` or `I3_RICE_PM=...`.
- If the batch install fails (one package unavailable on that release), the script retries package by package
  and warns about anything it could not install. Configs are still written.
- The rice is **X11 only**. On Fedora/Arch/openSUSE make sure you log into an X11 session; the defaults on
  those distros are usually Wayland.
- Alpine works without systemd: `xss-lock`, `i3lock`, and the X11 tools do not require it.

### Admin group (Debian `sudo` / `wheel`)

When run as root or through `sudo`, the installer also makes sure the invoking user has administrative rights:

- **Debian / Ubuntu / Mint:** adds the user to the **`sudo`** group and installs the `sudo` package if it is missing.
- **Fedora / Arch / openSUSE / Alpine:** adds the user to the **`wheel`** group.

The user is resolved from `$SUDO_USER`, the controlling terminal login, or `$USER`, in that order. Override it with
`--user <name>` and skip the change entirely with `--no-admin-group`.

Group membership applies only after a new login (or `newgrp sudo`). On a fresh Debian VM where the user was not
given sudo rights, run the installer as root, then log out and back in.

```sh
# manual equivalent on Debian
usermod -aG sudo <username>
```

This is a privilege change; use `--no-admin-group` if you do not want it.

**`usermod` is not a package.** On Debian/Ubuntu it ships in **`passwd`** and lives at `/usr/sbin/usermod`, which
may not be on a non-root user's `PATH`. The installer resolves it by absolute path, falls back to `gpasswd`, and
adds the provider package (`passwd`, `shadow-utils`, or `shadow`) to the package list.

```sh
# Debian: the likely fix if apt could not find "usermod"
apt-get update && apt-get install -y passwd
/usr/sbin/usermod -aG sudo <username>
```

---

## Why i3 and not Sway?

Sway is the natural Wayland successor to i3, but Mint 22.3 ships **Sway 1.9 / wlroots 0.17**, which predates
**explicit sync** (added in Sway 1.10 / wlroots 0.18). On NVIDIA that can cause flicker and poor frame pacing,
especially in games and video. Building a newer Sway means building a newer wlroots too.

i3 on X11 was chosen instead because:

- it is stable with the NVIDIA 580 driver,
- Steam, VLC, and screen sharing behave as they do under Cinnamon today,
- the machine already runs Xorg,
- the config is nearly identical to Sway's, so moving later is cheap.

Revisit Sway when Mint or Ubuntu packages Sway 1.10 or newer.

---

## Tech stack

| Role | Choice | Package (Debian names) | Config |
|---|---|---|---|
| Window manager | i3 4.23 | `i3` | `~/.config/i3/config` |
| Status bar | Polybar | `polybar` | `~/.config/polybar/config.ini`, `launch.sh` |
| Launcher | Rofi (drun/run/window) | `rofi` | `~/.config/rofi/config.rasi`, `catppuccin-mocha.rasi` |
| Compositor | Picom (glx, vsync, small shadows, rounded corners, no blur; st at 80% transparency) | `picom` | `~/.config/picom/picom.conf` |
| Notifications | Dunst | `dunst` | `~/.config/dunst/dunstrc` |
| Wallpaper | 4K neural whale + feh | `feh` | `wallpapers/deepseek-neural-whale-4k.jpg` → `~/Pictures/wallpaper.jpg` |
| Lock / idle | i3lock + xss-lock | `i3lock`, `xss-lock` | i3 config |
| Screenshots | maim + xclip | `maim`, `xclip` | i3 config |
| Displays | xrandr / arandr | `x11-xserver-utils`, `arandr` | i3 config (commented) |
| Keyboard layout | setxkbmap | `x11-xkb-utils` | i3 config (commented) |
| GTK theming | LXAppearance | `lxappearance` | GUI |
| Terminal | st 0.9.3 (built from source) | build deps + `stterm` fallback | compiled `config.h` |
| Media keys | playerctl | `playerctl` | i3 config |
| Audio | PulseAudio tools + pavucontrol | `pavucontrol`, `pulseaudio-utils` | i3 config / GUI |
| Network applet | nm-applet | `network-manager-gnome` | started from the i3 config |
| Notifications helper | notify-send | `libnotify-bin` | — |
| Calendar popup | yad | `yad` | `$mod+c` / click the Polybar date |
| System tray | Polybar internal tray | `polybar` | right side of the bar |
| Font | JetBrainsMono Nerd Font | downloaded to `~/.local/share/fonts` (standard JetBrains Mono fallback) | Polybar, Rofi, Dunst, i3, st |

The package names above are the Debian/Ubuntu ones. The installer maps them to the equivalent names for each
supported family (see [Distro support](#distro-support)).

### Component notes

- **i3** owns layouts, workspaces, keybindings, and floating rules. It starts everything else.
- **Polybar** replaces i3bar (`bar { mode invisible }` in the i3 config) and shows workspaces, date, volume,
  RAM, and CPU. `launch.sh` starts one bar per connected monitor, so multi-monitor works without editing configs.
- **Rofi** is bound to `$mod+d` for apps (`drun`), plus `$mod+Tab` for switching windows.
- **Picom** provides compositing for shadows and rounded corners. Blur is deliberately off for performance.
- **Dunst** handles desktop notifications with Catppuccin-colored urgency levels.
- **xss-lock** ties the lock screen to suspend and idle; `$mod+Escape` locks manually.
- **maim** takes region screenshots; `Print` copies to the clipboard, `$mod+Print` saves to `~/Pictures`.
- **st** is the terminal: CPU-rendered and very light (~13 MB), built from source with Catppuccin Mocha colors
  and a font size derived from `--scale`. It installs to `~/.local/bin/st` with a matching `.desktop` entry.
- **Polybar tray** (`tray-position = right`) hosts `nm-applet` and other XEmbed tray icons on the right.
- **yad** provides a minimal calendar popup: click the Polybar date or press `$mod+c`.

Debian's packaged `stterm` ignores Xresources for font and colors, so the installer compiles st 0.9.3 itself.

### Terminal (st)

The installer builds st 0.9.3 from source into `~/.local/bin/st` with:

- **Catppuccin Mocha** colors compiled into `config.h`
- **font size** `pixelsize = 14 × scale / 100` (28 px at 200%)
- **border** scaled with the rest of the rice

It also writes `~/.local/share/applications/st.desktop` so Rofi launches the same binary, and installs the
`st-256color` terminfo entry under `~/.terminfo`. The distro `stterm`/`st` package is installed only as a
fallback if the build fails.

Run the installer **as your user**, not with `sudo`, so the build artifacts and configs are owned by you. It
elevates with `sudo` only for the package installation.

### Fonts (Nerd Font)

The rice uses **JetBrainsMono Nerd Font** everywhere: i3 titles, Polybar, Rofi, Dunst, and st.

- The installer downloads the patched regular and Mono families (Regular, Bold, Italic, BoldItalic) into
  `~/.local/share/fonts/JetBrainsMonoNerdFont` and runs `fc-cache`.
- st uses the **Mono** variant so terminal glyphs align correctly; the rest of the UI uses the normal Nerd Font.
- Polybar uses Nerd Font glyphs for the calendar, volume, memory, and CPU modules.
- If the Nerd Font cannot be installed, the installer falls back to standard JetBrains Mono (then `monospace`)
  and leaves the Polybar labels as text.

### Palette

Catppuccin Mocha, shared by i3, Polybar, Rofi, and Dunst:

| Name | Hex | Used for |
|---|---|---|
| Base | `#1e1e2e` | backgrounds, unfocused borders |
| Text | `#cdd6f4` | foreground text |
| Blue | `#89b4fa` | focused borders, primary accent |
| Mauve | `#cba6f7` | secondary accent |
| Red | `#f38ba8` | urgent windows, critical notifications |

If you switch to another palette (Gruvbox, Nord, …), change the hex values in **all four** config files,
not just one.

---

## Workspaces

One workspace per app. Rules are `assign` entries in `~/.config/i3/config`.

| Key | Workspace | Assigned classes |
|---|---|---|
| `Super+1` | `1:term` | `st` |
| `Super+2` | `2:code` | `Code` |
| `Super+3` | `3:web` | `firefox`, `LibreWolf`, `brave-browser`, `google-chrome`, `chromium` |
| `Super+4` | `4:games` | `steam`, `Steam`, `steam_app_*` |
| `Super+5` | `5:media` | `vlc` |

Steam popups (Friends List, News, Settings), `pavucontrol`, `arandr`, and `lxappearance` float instead of tiling.

---

## Applets and tray

The rice stays minimal by using Polybar modules instead of a desktop panel:

- **Calendar:** `yad --calendar` opens from `$mod+c` or by clicking the date module.
- **Right corner:** Polybar’s built-in tray (`tray-position = right`) holds XEmbed icons such as `nm-applet`.
- **Volume / memory / CPU:** Polybar’s `internal/pulseaudio`, `internal/memory`, and `internal/cpu` modules.

If you prefer standalone applets over panel modules:

| Need | Minimal option |
|---|---|
| Calendar | `gsimplecal`, `yad --calendar`, or `calcurse` in st |
| Volume tray | `pasystray` |
| Battery tray | `cbatticon` |
| Standalone tray | `stalonetray` or `trayer` |
| Bluetooth | `blueman-applet` |
| Network | `nm-applet` (already installed) |

Avoid GNOME/KDE applets here; they pull in large dependency stacks and do not fit a bare i3 session.

---

## Keybindings

`Mod` is **Super**.

| Key | Action |
|---|---|
| `Super+Return` | open st |
| `Super+d` | app launcher (Rofi drun) |
| `Super+c` | calendar popup (yad) |
| `Super+Tab` | window switcher |
| `Super+q` | close window |
| `Super+h/j/k/l` or arrows | focus left/down/up/right |
| `Super+Shift+h/j/k/l` or arrows | move window |
| `Super+b` / `Super+v` | split horizontal / vertical |
| `Super+f` | fullscreen |
| `Super+Shift+Space` | toggle floating |
| `Super+r` | resize mode (`hjkl`, then Enter/Escape) |
| `Super+Escape` | lock screen |
| `Print` | region screenshot → clipboard |
| `Super+Print` | region screenshot → `~/Pictures` |
| `Super+Shift+c` | reload i3 config |
| `Super+Shift+r` | restart i3 |
| `Super+Shift+e` | exit i3 |
| `Super+Shift+1..5` | move window to workspace |
| `XF86Audio*` | volume, mute, mic mute, play/next/previous |

---

## Repository contents

```text
i3-rice/
├── README.md              this file
├── memory.md              project decisions, findings, and TODO
├── install-i3-rice.sh     installer and config generator
└── wallpapers/
    ├── README.md
    ├── deepseek-neural-whale-4k.jpg
    └── generate.py        regenerates the wallpaper with Pillow
```

`install-i3-rice.sh` is the single source of truth for the dotfiles. It writes them from embedded heredocs,
so re-running it is the supported way to reset the setup.

---

## Install

Prerequisites: any Linux with an **X11** session, `bash`, and either root or `sudo`. Package names are mapped
automatically for apt, dnf, pacman, zypper, and apk.

```sh
cd ~/dev/projects/i3-rice
./install-i3-rice.sh --list-packages   # see resolved package names
./install-i3-rice.sh --dry-run         # inspect, change nothing
./install-i3-rice.sh                   # install packages + write configs
```

Run it as your normal user; it calls `sudo` only for package installation. Running the whole script with
`sudo` is not recommended because the st build and config files would be owned by root.

Useful flags:

| Flag | Effect |
|---|---|
| `--dry-run` | print every action, install and write nothing |
| `--no-packages` | write configs only, skip package installation |
| `--scale <percent>` | HiDPI scaling percent (default **200**) |
| `--list-packages` | print the package groups resolved for the detected manager |
| `--package-manager <pm>` | force `apt`, `dnf`, `pacman`, `zypper`, or `apk` (`I3_RICE_PM` also works) |
| `--user <name>` | user to add to the admin group (default: `$SUDO_USER`, login name, or `$USER`) |
| `--no-admin-group` | do not change `sudo`/`wheel` group membership |
| `--help` | usage |

What it changes:

1. Detects the distro's package manager and installs the mapped package set. If a name is unavailable it warns,
   retries package by package, and continues.
2. Builds st 0.9.3 from source into `~/.local/bin/st`, with Catppuccin Mocha colors and a font size derived from
   `--scale`. A distro `stterm`/`st` package is installed as a fallback.
3. Installs **JetBrainsMono Nerd Font** (regular and Mono, four styles) into `~/.local/share/fonts` and
   refreshes fontconfig. If that fails it falls back to standard JetBrains Mono, then `monospace`.
4. Adds the invoking user to the admin group (`sudo` on Debian/Ubuntu/Mint, `wheel` on the others), unless
   `--no-admin-group` is passed.
5. Backs up any existing config as `<file>.bak-<timestamp>`.
6. Writes i3, Polybar, Rofi, Picom, and Dunst configs under `~/.config/`.
7. Writes HiDPI resources (`~/.config/i3/Xresources`, `~/.config/i3/scale.env`) and wires them into
   `~/.xprofile` and `~/.xsessionrc` via a managed block. It also adds `~/.local/bin` to `PATH` through
   managed blocks in `~/.profile` and `~/.bashrc`.
8. Makes `~/.config/polybar/launch.sh` executable.
9. Installs the packaged 4K wallpaper to `~/Pictures/wallpaper.jpg` if that file does not exist, and applies
   it with feh when run inside the session.
10. Warns if `~/Pictures/wallpaper.jpg` is still missing.
11. Reports any commands or fonts that are still missing at the end.

It does **not** change your login session, GTK theme, or display configuration.

---

## After install

1. **Start i3**: choose it at your display manager. Without a display manager, put `exec i3` in `~/.xinitrc`
   and run `startx`. On Mint, Cinnamon remains available as a fallback session.
2. **Verify window classes** with `xprop WM_CLASS`, then correct any `assign` regexes that do not match
   (browser and editor classes vary by build).
3. **Set the keyboard layout**: edit `~/.config/i3/config`, uncomment and adjust
   `exec --no-startup-id setxkbmap us`.
4. **Set monitor mode and refresh rate**: run `xrandr --query`, then uncomment and adjust
   `exec --no-startup-id xrandr --output DP-1 --mode 2560x1440 --rate 144`.
5. **Wallpaper:** the installer places the packaged 4K art at `~/Pictures/wallpaper.jpg` (if you don't already
   have one); feh picks it up at login. Replace it with your own if you prefer.
6. **Theme GTK apps** with `lxappearance` (Catppuccin GTK theme and cursor).
7. **Test video and games.** On NVIDIA, if you see tearing, open `nvidia-settings` →
   X Server Display Configuration → Advanced → enable **Force Full Composition Pipeline**.
8. **In a VM or with software rendering**, if picom flickers or stutters, set
   `backend = "xrender"` and `vsync = false` in `~/.config/picom/picom.conf`.
9. Reload i3 with `Super+Shift+c` after each config edit.

---

## Scaling / HiDPI

The installer defaults to **200%**, intended for 4K displays. Change it with:

```sh
./install-i3-rice.sh --scale 200      # default, 2x widgets and text
./install-i3-rice.sh --scale 125      # 1.25x text, 1x GTK widgets
./install-i3-rice.sh --scale 100      # standard-density displays
```

Scaling is applied at three levels:

| What | How |
|---|---|
| Xft/Pango fonts (i3, Rofi, Dunst, GTK) | `Xft.dpi` in `~/.config/i3/Xresources` |
| Rice geometry | i3 gaps/borders, Polybar height/DPI, Rofi padding/border, Dunst size/padding, Picom shadows/corners |
| Toolkits | `~/.config/i3/scale.env` (GDK, Qt, cursor size) |

`scale.env` and `Xresources` are loaded from a managed block in `~/.xprofile` and `~/.xsessionrc`; i3 also merges
them at startup. **Log out of the X session and back in** after changing the scale. Restarting i3 alone re-reads
the i3 config, but GTK/Qt applications only get the new environment variables from a fresh login.

After logging back in, verify:

```sh
echo "$GDK_SCALE $GDK_DPI_SCALE $QT_SCALE_FACTOR"   # 200%: 2 0.50 2.00
xrdb -query | grep -i xft.dpi                        # Xft.dpi: 192
```

If `GDK_SCALE` is empty, the display manager is not sourcing `~/.xprofile`/`~/.xsessionrc`; check the
[Troubleshooting](#troubleshooting) table.

### Per-application notes

X11 does not have a single global fractional-scale switch, so a few apps need their own setting:

- **GTK3:** widgets scale by the integer part of the percentage. 200% → 2× widgets, 125% → 1× widgets with
  1.25× text. `GDK_SCALE` and `GDK_DPI_SCALE` are set automatically in `scale.env`.
- **Firefox:** `about:config` → `layout.css.devPixelsPerPx` = `2.0` for 200% (or `-1` to follow the system DPI).
- **VS Code:** launch with `--force-device-scale-factor=2`, or set `window.zoomLevel` to about `2`.
- **Steam:** add `-forcedesktopscaling 2` to the Steam launch options.
- **st:** rebuilt by the installer with `pixelsize` derived from `--scale`; rerun the installer after changing
  the scale.
- **NVIDIA:** make sure the monitor is running at its native 4K resolution so 2× is pixel-perfect.

---

## Wallpaper

The repo ships `wallpapers/deepseek-neural-whale-4k.jpg` (3840×2160): an original procedural illustration of a
whale made from neural-network nodes in DeepSeek blue. It contains no third-party assets, logos, or text.

The installer copies it to `~/Pictures/wallpaper.jpg` only if that file does not exist, so your own wallpaper is
never overwritten. When run inside the i3 session it also calls `feh --bg-fill` immediately; otherwise the i3
autostart applies it at login.

Replace it at any time:

```sh
cp your-wallpaper.jpg ~/Pictures/wallpaper.jpg
feh --bg-fill ~/Pictures/wallpaper.jpg
```

Regenerate or tweak the packaged art with:

```sh
python3 wallpapers/generate.py    # requires Pillow
```

---

## Customization

| Want to change… | Edit |
|---|---|
| Keybindings, gaps, borders, workspaces | `~/.config/i3/config` |
| Bar modules, colors, height | `~/.config/polybar/config.ini` |
| Launcher look | `~/.config/rofi/catppuccin-mocha.rasi` |
| Shadows, corner radius, st opacity, vsync, blur | `~/.config/picom/picom.conf` |
| Notification style and timeouts | `~/.config/dunst/dunstrc` |
| Palette | hex values in all four configs above |

**Polybar icons:** the bar uses JetBrainsMono Nerd Font glyphs for the calendar, volume, memory, and CPU
modules. If the Nerd Font cannot be installed, the installer omits the icons and the labels fall back to text.
To remove them manually, delete the `@ICON_*@` results from `~/.config/polybar/config.ini`.

**Blur:** set `blur-background = true` and choose a `blur-method` in `picom.conf`, then restart picom.
This costs GPU time and is off by default.

**st transparency:** the number in the `opacity-rule` is the *opacity* percentage, so `20` means **80% transparent**;
`80` would mean 20% transparent. st is excluded from shadows so the transparency stays clean.

---

## Troubleshooting

| Symptom | Try |
|---|---|
| No bar after login | `~/.config/polybar/launch.sh` in a terminal; check `pgrep -a polybar` |
| Bar on the wrong monitor | `xrandr --query`; `launch.sh` assigns one bar per connected output |
| Black background | check `~/Pictures/wallpaper.jpg` exists, then `feh --bg-fill ~/Pictures/wallpaper.jpg` |
| Screenshots fail | make sure `maim` and `xclip` are installed; `Print` needs `xclip` for the clipboard |
| Tearing in games/video | enable Force Full Composition Pipeline in `nvidia-settings` |
| VM / software rendering | set `backend = "xrender"` and `vsync = false` in `picom.conf`; disable shadows if still slow |
| Picom crashes or flickers | try `backend = "xrender"` or remove `glx-no-stencil` in `picom.conf` |
| i3 refuses to reload | run `i3 -C -c ~/.config/i3/config` to validate, or check `~/.xsession-errors` |
| Rofi shows no icons | install an icon theme or remove `show-icons` from `config.rasi` |
| Lock screen does not appear | check `xss-lock` is running: `pgrep -a xss-lock` |
| `usermod: command not found` | it is in `passwd` (Debian) / `shadow-utils` (Fedora) / `shadow` (others); use `/usr/sbin/usermod` or add `/usr/sbin` to `PATH` |
| st text still tiny | the distro `stterm` is being used; run `./install-i3-rice.sh` (without `--no-packages`) to build `~/.local/bin/st`, then check `command -v st` |
| `st` not found in a new shell | `~/.local/bin` is added by the installer; log out/in or run `source ~/.profile`. i3 and Rofi use the absolute path regardless. |
| st transparency not working | ensure picom is running (`pgrep -a picom`); `xprop WM_CLASS` on st should show `st-256color` — the rules match that class. Restart picom after editing `picom.conf`. |
| JetBrainsMono Nerd Font missing | rerun the installer (it downloads the patched TTFs to `~/.local/share/fonts`) or install standard JetBrains Mono |
| Tray icons missing | make sure `nm-applet` is running; Polybar’s tray is XEmbed-only, so SNI-only apps may need `xembedsniproxy` |
| Calendar does not open | check `yad` is installed and run `yad --calendar` in a terminal |
| Scaling env vars empty after login | the DM skipped `~/.xprofile`/`~/.xsessionrc`; source `~/.config/i3/scale.env` from your session startup, or start i3 via a wrapper that sources it |

---

## Notes and limitations

- **Fallback:** on Mint, log out and pick Cinnamon at any time; this setup does not remove it. On other distros,
  just log out or switch sessions.
- **Backups:** every overwritten config is kept as `*.bak-<timestamp>` next to the original.
- **Desktop-environment gaps:** a bare i3 session has no panel applets, no keyboard-layout handling, and no
  automatic display management. The installer covers audio keys, `nm-applet`, and locking, but not the rest.
- **Package coverage varies:** some releases do not package `polybar`, `picom`, or `xss-lock`. The installer
  warns and continues; use `--list-packages` to see exactly what it will try.
- **X11 only:** these configs target X11. Wayland sessions are not supported.
- **Wayland later:** keep this repo; the i3 config maps closely to Sway when explicit sync becomes available.
