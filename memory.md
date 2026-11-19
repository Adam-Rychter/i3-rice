# Tiling WM Rice: Project Memory

Last updated: 2026-11-19

## Goal

Move from a Windows-style desktop (Cinnamon) to a minimal, tiling window manager setup with low resource usage, while keeping the stability of Linux Mint.

## System

| Item | Value |
|---|---|
| OS | Linux Mint 22.3 x86_64 (Ubuntu 24.04 "Noble" base) |
| Kernel | 7.0.0-43-generic |
| DE (current) | Cinnamon 6.6.9 (on Xorg) |
| CPU | AMD Ryzen 5 5600X (12 threads) |
| GPU | NVIDIA GeForce RTX 3070 Ti, driver 580.178.04 |
| RAM | 32 GB (about 5.5 GB used at idle on Cinnamon) |
| Terminal | kitty (already installed at `~/.local/kitty.app`) |

## Workflow

Mostly five apps, switched between full-screen:
1. Terminal (almost everything, agentic development)
2. VS Code (PR reviews)
3. Web browser
4. Steam (games)
5. VLC (movies and videos)

Plan: **one workspace per app**, with tiling used when two apps sit side by side (e.g. terminal + VS Code).

## Key findings

- **wlroots**: a library Sway is built on. Never installed or configured directly.
- **picom**: X11-only compositor. Irrelevant on Sway, relevant on i3.
- **drun**: a mode inside launchers (rofi, wofi, fuzzel), not a program.
- **quickshell / eww / AGS**: toolkits for fully custom shells. Skip until the basics are comfortable.
- Mint 22.3's repo ships **Sway 1.9-1build2** (wlroots 0.17), which lacks **explicit sync** (added in Sway 1.10 / wlroots 0.18). On Nvidia this can mean flicker or poor frame pacing, mostly in games and sometimes video.
- The Nvidia driver (580) is new enough. Still to verify: `cat /sys/module/nvidia_drm/parameters/modeset` should print `Y`.
- No verified Sway PPA for Noble. Building a newer Sway needs a newer wlroots too, and is real work.

## Decision

**Go with i3 on X11.** Reasons: stable on Nvidia, Steam works as it does now, you already run Xorg, and the config is nearly identical to Sway's. Cinnamon stays installed as a fallback session.

Sway remains an option for later. It is worth retrying once Mint or Ubuntu ships Sway 1.10 or newer.

## App stack

| Role | Sway version (not chosen) | i3 version (chosen) |
|---|---|---|
| Window manager | sway | i3 (4.23) |
| Bar | waybar | polybar |
| Launcher | fuzzel | rofi |
| Compositor | built in | picom |
| Notifications | mako | dunst |
| Wallpaper | swaybg | feh |
| Lock / idle | swaylock + swayidle | i3lock + xss-lock |
| Screenshots | grim + slurp | maim (+ xclip) |
| Displays | `output` blocks | xrandr / arandr |
| GTK theming | nwg-look | lxappearance |
| Terminal | kitty | kitty |

Extras installed: playerctl, pavucontrol, network-manager-gnome (nm-applet), x11-xserver-utils, fonts-jetbrains-mono.

## What was generated

`install-i3-rice.sh` installs packages and writes these configs (existing ones are backed up as `*.bak-<timestamp>`):

- `~/.config/i3/config`
- `~/.config/polybar/config.ini` and `launch.sh`
- `~/.config/rofi/config.rasi` and `catppuccin-mocha.rasi`
- `~/.config/picom/picom.conf` (glx, vsync on, shadows, rounded corners, no blur)
- `~/.config/dunst/dunstrc`

Palette: **Catppuccin Mocha** (base `#1e1e2e`, text `#cdd6f4`, blue `#89b4fa`, mauve `#cba6f7`, red `#f38ba8`).

## Workspace layout

| Key | Workspace | Assigned class |
|---|---|---|
| Super+1 | term | kitty |
| Super+2 | code | Code |
| Super+3 | web | firefox / brave / chrome / chromium |
| Super+4 | games | steam, steam_app_* |
| Super+5 | media | vlc |

Steam popups (Friends List, News, Settings), pavucontrol, arandr and lxappearance float.

## Keybinds

Mod = Super.

- Super+Return: kitty
- Super+d: rofi launcher
- Super+Tab: window switcher
- Super+q: close window
- Super+h/j/k/l (or arrows): focus. Add Shift to move the window.
- Super+b / Super+v: next split horizontal / vertical
- Super+f: fullscreen
- Super+Shift+Space: toggle floating
- Super+r: resize mode
- Super+Escape: lock screen
- Print / Super+Print: region screenshot to clipboard / to `~/Pictures`
- Super+Shift+c: reload config. Super+Shift+r: restart i3. Super+Shift+e: exit.

## Next steps / TODO

- [ ] Run `install-i3-rice.sh`, log out, pick "i3" at the login screen
- [ ] Confirm window classes with `xprop WM_CLASS` and fix any `assign` rules that don't match
- [ ] Set keyboard layout (uncomment the `setxkbmap` line in the i3 config)
- [ ] Set monitor mode and refresh rate (uncomment the `xrandr` line; get output name from `xrandr`)
- [ ] Add a wallpaper at `~/Pictures/wallpaper.jpg`
- [ ] Test a Steam game and a VLC video for tearing or stutter
- [ ] If tearing: nvidia-settings, X Server Display Configuration, Advanced, Force Full Composition Pipeline
- [ ] Theme GTK apps with lxappearance (Catppuccin GTK theme and cursor)
- [ ] Optional later: picom blur, polybar icons via a Nerd Font, retry Sway when 1.10+ is available

## Notes

- Fallback: log out and choose the Cinnamon session at any time.
- Keep the palette hex codes identical across i3, polybar, rofi and dunst. If you switch to Gruvbox or Nord, change all four files.
- Mint-specific gaps in i3: no Cinnamon panel, no applets, no keyboard layout handling, no automatic display management. The script covers audio keys, nm-applet and lock, but not everything.
