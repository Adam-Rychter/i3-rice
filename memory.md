# Tiling WM Rice: Project Memory

Last updated: 2026-11-21

## GUI prototype development handoff

Current pushed HEAD: `fa3612e`.

Completed safe GUI milestones:

- Atomic apply with external-change detection, backups, permission preservation, and missing-file creation.
- Backup restore to disk with conflict checks and GUI confirmation.
- Curated apt package detection, review, and bounded `pkexec` execution.
- Workspace label editing with comment preservation.
- Read-only keybinding inspection, conflict detection, and safe command editing.
- Literal i3 variable inspection, reference counts, safe value editing, and include warnings.
- Read-only `xrandr` display inspection showing connected outputs and geometry.
- Read-only `feh --bg-*` wallpaper reference inspection with image existence status.

Validation:

- Latest local suite: `166 passed, 2 skipped`.
- VM checkout: `/home/iktai/i3-rice-vm-test`.
- VM validation is currently blocked because SSH to `iktai@192.168.241.135` returns `Permission denied (publickey,password)`. Do not collect or store the VM password; use an interactive SSH session or restore key-based access.

Next development priorities:

- Add safe included-file discovery and staged multi-file editing/validation.
- Expand component controls for fonts/scaling and additional wallpaper workflows.
- Implement shared palette propagation with an explicit affected-file review.
- Design the independent 30-second live-preview rollback/watchdog.
- Add profile import/export with conflict and asset-safety checks.
- Re-test the fresh VM checkout and perform the integrated i3 demonstration once SSH access is available.

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
| Terminal | st 0.9.3, built from source into `~/.local/bin/st` (kitty still installed at `~/.local/kitty.app`) |

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
- Debian's packaged **stterm** ignores Xresources for font and colors, so the script builds **st 0.9.3 from source** instead (Catppuccin colors compiled into `config.h`, font size derived from `--scale`).
- **HiDPI on X11** has no single global fractional-scale switch: fonts follow `Xft.dpi`, GTK widgets scale only by the integer part, and Firefox / VS Code / Steam each need their own setting.
- **Nerd Font**: the bar, Rofi, and st want glyphs from JetBrainsMono Nerd Font; the installer falls back to standard JetBrains Mono (then `monospace`) if it cannot be fetched.

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
| Terminal | kitty | st 0.9.3 (built from source) |

Extras installed: playerctl, pasystray, pavucontrol, network-manager-gnome (nm-applet), x11-xserver-utils, yad, libnotify-bin, arandr, lxappearance, unzip.

## What was generated

`install-i3-rice.sh` installs packages and writes these configs (existing ones are backed up as `*.bak-<timestamp>`):

- `~/.config/i3/config`
- `~/.config/polybar/config.ini` and `launch.sh`
- `~/.config/rofi/config.rasi` and `catppuccin-mocha.rasi`
- `~/.config/picom/picom.conf` (glx, vsync on, shadows, rounded corners, no blur; st at 20% transparency)
- `~/.config/dunst/dunstrc`
- `~/.config/i3/Xresources` (Xft.dpi, Xcursor.size)
- `~/.config/i3/scale.env` (GDK/Qt scaling env)
- `~/.local/bin/st` (built from source) plus `st.desktop` and the `st-256color` terminfo
- managed blocks in `~/.xprofile` / `~/.xsessionrc` (scaling) and `~/.profile` / `~/.bashrc` (PATH)
- wallpaper → `~/Pictures/wallpaper.jpg` (only if it does not already exist)

Palette: **Catppuccin Mocha** (base `#1e1e2e`, text `#cdd6f4`, blue `#89b4fa`, mauve `#cba6f7`, red `#f38ba8`). st also gets the full 16-color Mocha palette compiled in.

## Workspace layout

| Key | Workspace | Assigned class |
|---|---|---|
| Super+1 | term | st |
| Super+2 | code | Code |
| Super+3 | web | firefox / brave / chrome / chromium |
| Super+4 | games | steam, steam_app_* |
| Super+5 | media | vlc |

Steam popups (Friends List, News, Settings), pavucontrol, arandr, lxappearance, and the yad calendar float.

## Keybinds

Mod = Super.

- Super+Return: st
- Super+d: rofi launcher
- Super+c: calendar popup (yad)
- Super+a: audio mixer (pavucontrol)
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
- [ ] Test a Steam game and a VLC video for tearing or stutter
- [ ] If tearing: nvidia-settings, X Server Display Configuration, Advanced, Force Full Composition Pipeline
- [ ] Theme GTK apps with lxappearance (Catppuccin GTK theme and cursor)
- [ ] Optional later: picom blur, retry Sway when 1.10+ is available

## Notes

- Fallback: log out and choose the Cinnamon session at any time.
- Keep the palette hex codes identical across i3, polybar, rofi and dunst. If you switch to Gruvbox or Nord, change all four files — and rebuild st, since its palette is compiled into `config.h`.
- The installer adds the invoking user to the admin group (`sudo` on Debian/Ubuntu/Mint, `wheel` elsewhere); skip with `--no-admin-group`.
- HiDPI defaults to 200% for 4K; change it with `--scale` and log out/in for the GTK/Qt env to apply. Re-run the installer after changing scale so st is rebuilt at the right font size.
- The Nerd Font is downloaded to `~/.local/share/fonts`; Polybar icons fall back to text if it cannot be installed.
- Wallpaper is installed to `~/Pictures/wallpaper.jpg` only if that file does not already exist.
- `--build-from-source` clones and builds the tiling stack (i3, i3lock, xss-lock, polybar, rofi, picom, dunst,
  feh, slop, maim, xclip, playerctl, pasystray, lxappearance, yad) into `~/.local`; PulseAudio, nm-applet, the
  Xorg tools, arandr and libnotify stay as packages. The `build-deps` group is mapped fully only for apt.
- Mint-specific gaps in i3: no Cinnamon panel, no applets, no keyboard layout handling, no automatic display management. The script covers audio keys, nm-applet, lock, calendar, and the tray, but not everything.
