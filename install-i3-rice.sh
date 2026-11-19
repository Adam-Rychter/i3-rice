#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WALLPAPER_SRC="$SCRIPT_DIR/wallpapers/deepseek-neural-whale-4k.jpg"

# install-i3-rice.sh — Catppuccin Mocha i3 rice
# Target: any Linux with X11; package names are mapped for apt, dnf, pacman,
# zypper, and apk. Developed against Linux Mint 22.3 on X11/NVIDIA.
#
# Installs the window manager stack and writes the configs described in
# memory.md. Existing config files are backed up as <file>.bak-<timestamp>.
#
# Usage:
#   ./install-i3-rice.sh                      # install packages and write configs
#   ./install-i3-rice.sh --dry-run            # show what would happen, change nothing
#   ./install-i3-rice.sh --no-packages        # write configs only
#   ./install-i3-rice.sh --scale 200           # HiDPI scaling percent (default 200)
#   ./install-i3-rice.sh --list-packages      # show resolved package names
#   ./install-i3-rice.sh --package-manager dnf
#   ./install-i3-rice.sh --user alice          # add alice to the sudo/wheel group
#   ./install-i3-rice.sh --no-admin-group      # leave group membership unchanged
#   ./install-i3-rice.sh --help
#
# After it finishes, start i3 from your display manager, or run `startx` with
# `exec i3` in ~/.xinitrc.

DRY_RUN=0
INSTALL_PACKAGES=1
LIST_PACKAGES=0
PM_OVERRIDE="${I3_RICE_PM:-}"
TARGET_USER="${I3_RICE_USER:-}"
SKIP_ADMIN_GROUP=0
SCALE=200

usage() {
  cat <<'EOF'
install-i3-rice.sh — Catppuccin Mocha i3 rice
Target: any Linux with X11; package names are mapped for apt, dnf, pacman,
zypper, and apk. Developed against Linux Mint 22.3 on X11/NVIDIA.

Installs the window manager stack and writes the configs described in
memory.md. Existing config files are backed up as <file>.bak-<timestamp>.

Usage:
  ./install-i3-rice.sh                      # install packages and write configs
  ./install-i3-rice.sh --dry-run            # show what would happen, change nothing
  ./install-i3-rice.sh --no-packages        # write configs only
  ./install-i3-rice.sh --scale 200           # HiDPI scaling percent (default 200)
  ./install-i3-rice.sh --list-packages      # show resolved package names
  ./install-i3-rice.sh --package-manager dnf
  ./install-i3-rice.sh --user alice          # add alice to the sudo/wheel group
  ./install-i3-rice.sh --no-admin-group      # leave group membership unchanged
  ./install-i3-rice.sh --help

After it finishes, start i3 from your display manager, or run `startx` with
`exec i3` in ~/.xinitrc.
EOF
  exit "${1:-1}"
}

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }
run()  { if [ "$DRY_RUN" = 1 ]; then printf '[dry-run]'; printf ' %q' "$@"; printf '\n'; else "$@"; fi; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --no-packages) INSTALL_PACKAGES=0 ;;
    --scale)
      [ $# -ge 2 ] || die "--scale needs a value"
      SCALE="$2"
      shift
      ;;
    --list-packages) LIST_PACKAGES=1 ;;
    --package-manager)
      [ $# -ge 2 ] || die "--package-manager needs a value"
      PM_OVERRIDE="$2"
      shift
      ;;
    --user)
      [ $# -ge 2 ] || die "--user needs a value"
      TARGET_USER="$2"
      shift
      ;;
    --no-admin-group) SKIP_ADMIN_GROUP=1 ;;
    -h|--help) usage 0 ;;
    *)
      echo "install-i3-rice: unknown option: $1" >&2
      usage 1
      ;;
  esac
  shift
done

case "$SCALE" in
  ''|*[!0-9]*) die "--scale must be a whole number such as 125" ;;
esac
if [ "$SCALE" -lt 100 ] || [ "$SCALE" -gt 300 ]; then
  die "--scale must be between 100 and 300"
fi

# Derived HiDPI values. Fonts use points and follow Xft.dpi; fixed pixel sizes
# are rounded to the nearest pixel.
DPI=$((96 * SCALE / 100))
SCALE_FACTOR=$(printf '%d.%02d' "$((SCALE / 100))" "$((SCALE % 100))")

# GTK can only scale windows by an integer. Use the integer part for widgets and
# cancel it in GDK_DPI_SCALE so text still follows Xft.dpi exactly.
GDK_SCALE_VALUE=$((SCALE / 100))
[ "$GDK_SCALE_VALUE" -ge 1 ] || GDK_SCALE_VALUE=1
case "$GDK_SCALE_VALUE" in
  1) GDK_DPI_SCALE="1.00" ;;
  2) GDK_DPI_SCALE="0.50" ;;
  3) GDK_DPI_SCALE="0.33" ;;
  *) GDK_DPI_SCALE="1.00" ;;
esac

spx() { echo $(( ($1 * SCALE + 50) / 100 )); }

CURSOR_SIZE=$(spx 24)
I3_GAP_INNER=2
I3_GAP_OUTER=2
I3_BORDER=2
BAR_HEIGHT=$(spx 28)
BAR_PADDING=$(spx 1)
BAR_MARGIN=$(spx 1)
ROFI_PAD=$(spx 12)
ROFI_BORDER=$(spx 2)
ROFI_RADIUS=$(spx 8)
ROFI_SMALL_RADIUS=$(spx 6)
ROFI_INPUT_PAD="$(spx 8)px $(spx 12)px"
ROFI_ELEMENT_PAD="$ROFI_INPUT_PAD"
DUNST_WIDTH=$(spx 320)
DUNST_HEIGHT=$(spx 120)
DUNST_OFFSET="$(spx 12)x$(spx 12)"
DUNST_FRAME=$(spx 2)
DUNST_RADIUS=$(spx 8)
DUNST_PADDING=$(spx 12)
DUNST_HPADDING=$(spx 14)
DUNST_ICON=$(spx 48)
PICOM_SHADOW_RADIUS=$(spx 4)
PICOM_SHADOW_OFFSET="-$(spx 4)"
PICOM_RADIUS=$(spx 8)
ST_FONT_PX=$(spx 14)

ST_VERSION="0.9.3"
ST_BIN="$HOME/.local/bin/st"
ST_BUILD_DIR="$HOME/.cache/i3-rice/st-$ST_VERSION"
JETBRAINS_VERSION="2.304"
NERD_FONT_VERSION="3.5.1"
FONT_FAMILY="JetBrains Mono"
ST_FONT_FAMILY="JetBrains Mono"

STAMP="$(date +%Y%m%d-%H%M%S)"

if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
  warn "do not run this via sudo; run ./install-i3-rice.sh as $SUDO_USER (it elevates only for packages)"
fi

# --- distro / package manager detection -------------------------------------

detect_pm() {
  local candidate
  for candidate in apt-get dnf pacman zypper apk; do
    if command -v "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  echo "unknown"
}

PM="${PM_OVERRIDE:-$(detect_pm)}"
case "$PM" in
  apt-get|apt) PM="apt" ;;
  dnf|pacman|zypper|apk) ;;
  *)
    if [ -n "$PM_OVERRIDE" ] && [ "$PM_OVERRIDE" != "unknown" ]; then
      die "unsupported package manager: $PM_OVERRIDE (use apt, dnf, pacman, zypper, or apk)"
    fi
    if [ "$INSTALL_PACKAGES" = 1 ] || [ "$LIST_PACKAGES" = 1 ]; then
      die "no supported package manager found (apt, dnf, pacman, zypper, apk); use --no-packages"
    fi
    PM="none"
    ;;
esac

DISTRO="unknown Linux"
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  DISTRO="${PRETTY_NAME:-${NAME:-unknown Linux}}"
fi

declare -A PKG_GROUPS=()
GROUP_ORDER=(
  wm terminal bar launcher compositor notifications wallpaper screenshot clipboard
  media audio-gui audio-cli network xutils kb xprop display-gui theming fonts notify calendar elevate
)

case "$PM" in
  apt)
    PM_LABEL="apt (Debian/Ubuntu/Mint)"
    REFRESH=(apt-get update)
    INSTALL=(apt-get install -y --no-install-recommends)
    PKG_GROUPS[wm]="i3 i3lock xss-lock"
    PKG_GROUPS[terminal]="stterm build-essential libx11-dev libxft-dev libfontconfig1-dev libfreetype-dev pkg-config ncurses-bin curl"
    PKG_GROUPS[bar]="polybar"
    PKG_GROUPS[launcher]="rofi"
    PKG_GROUPS[compositor]="picom"
    PKG_GROUPS[notifications]="dunst"
    PKG_GROUPS[wallpaper]="feh"
    PKG_GROUPS[screenshot]="maim"
    PKG_GROUPS[clipboard]="xclip"
    PKG_GROUPS[media]="playerctl"
    PKG_GROUPS[audio-gui]="pavucontrol pasystray"
    PKG_GROUPS[audio-cli]="pulseaudio-utils"
    PKG_GROUPS[network]="network-manager-gnome"
    PKG_GROUPS[xutils]="x11-xserver-utils"
    PKG_GROUPS[kb]="x11-xkb-utils"
    PKG_GROUPS[xprop]="x11-utils"
    PKG_GROUPS[display-gui]="arandr"
    PKG_GROUPS[theming]="lxappearance"
    PKG_GROUPS[fonts]="fonts-jetbrains-mono unzip"
    PKG_GROUPS[notify]="libnotify-bin"
    PKG_GROUPS[calendar]="yad"
    PKG_GROUPS[elevate]="sudo passwd"
    ;;
  dnf)
    PM_LABEL="dnf (Fedora/RHEL)"
    REFRESH=()
    INSTALL=(dnf install -y)
    PKG_GROUPS[wm]="i3 i3lock xss-lock"
    PKG_GROUPS[terminal]="st gcc make libX11-devel libXft-devel fontconfig-devel freetype-devel pkgconf-pkg-config ncurses curl"
    PKG_GROUPS[bar]="polybar"
    PKG_GROUPS[launcher]="rofi"
    PKG_GROUPS[compositor]="picom"
    PKG_GROUPS[notifications]="dunst"
    PKG_GROUPS[wallpaper]="feh"
    PKG_GROUPS[screenshot]="maim"
    PKG_GROUPS[clipboard]="xclip"
    PKG_GROUPS[media]="playerctl"
    PKG_GROUPS[audio-gui]="pavucontrol pasystray"
    PKG_GROUPS[audio-cli]="pulseaudio-utils"
    PKG_GROUPS[network]="network-manager-applet"
    PKG_GROUPS[xutils]="xorg-x11-server-utils xrandr"
    PKG_GROUPS[kb]="xorg-x11-xkb-utils"
    PKG_GROUPS[xprop]="xorg-x11-utils"
    PKG_GROUPS[display-gui]="arandr"
    PKG_GROUPS[theming]="lxappearance"
    PKG_GROUPS[fonts]="jetbrains-mono-fonts unzip"
    PKG_GROUPS[notify]="libnotify"
    PKG_GROUPS[calendar]="yad"
    PKG_GROUPS[elevate]="shadow-utils"
    ;;
  pacman)
    PM_LABEL="pacman (Arch/Manjaro)"
    REFRESH=()
    INSTALL=(pacman -S --needed --noconfirm)
    PKG_GROUPS[wm]="i3-wm i3lock xss-lock"
    PKG_GROUPS[terminal]="st gcc make pkgconf libx11 libxft fontconfig freetype2 ncurses curl"
    PKG_GROUPS[bar]="polybar"
    PKG_GROUPS[launcher]="rofi"
    PKG_GROUPS[compositor]="picom"
    PKG_GROUPS[notifications]="dunst"
    PKG_GROUPS[wallpaper]="feh"
    PKG_GROUPS[screenshot]="maim"
    PKG_GROUPS[clipboard]="xclip"
    PKG_GROUPS[media]="playerctl"
    PKG_GROUPS[audio-gui]="pavucontrol pasystray"
    PKG_GROUPS[audio-cli]="libpulse"
    PKG_GROUPS[network]="network-manager-applet"
    PKG_GROUPS[xutils]="xorg-xrandr xorg-xset"
    PKG_GROUPS[kb]="xorg-setxkbmap"
    PKG_GROUPS[xprop]="xorg-xprop"
    PKG_GROUPS[display-gui]="arandr"
    PKG_GROUPS[theming]="lxappearance"
    PKG_GROUPS[fonts]="ttf-jetbrains-mono unzip"
    PKG_GROUPS[notify]="libnotify"
    PKG_GROUPS[calendar]="yad"
    PKG_GROUPS[elevate]="shadow"
    ;;
  zypper)
    PM_LABEL="zypper (openSUSE)"
    REFRESH=(zypper --non-interactive refresh)
    INSTALL=(zypper --non-interactive install --no-recommends)
    PKG_GROUPS[wm]="i3 i3lock xss-lock"
    PKG_GROUPS[terminal]="st gcc make pkg-config libX11-devel libXft-devel fontconfig-devel freetype2-devel ncurses-utils curl"
    PKG_GROUPS[bar]="polybar"
    PKG_GROUPS[launcher]="rofi"
    PKG_GROUPS[compositor]="picom"
    PKG_GROUPS[notifications]="dunst"
    PKG_GROUPS[wallpaper]="feh"
    PKG_GROUPS[screenshot]="maim"
    PKG_GROUPS[clipboard]="xclip"
    PKG_GROUPS[media]="playerctl"
    PKG_GROUPS[audio-gui]="pavucontrol pasystray"
    PKG_GROUPS[audio-cli]="pulseaudio-utils"
    PKG_GROUPS[network]="NetworkManager-applet"
    PKG_GROUPS[xutils]="xrandr xset"
    PKG_GROUPS[kb]="setxkbmap"
    PKG_GROUPS[xprop]="xprop"
    PKG_GROUPS[display-gui]="arandr"
    PKG_GROUPS[theming]="lxappearance"
    PKG_GROUPS[fonts]="jetbrains-mono-fonts unzip"
    PKG_GROUPS[notify]="libnotify-tools"
    PKG_GROUPS[calendar]="yad"
    PKG_GROUPS[elevate]="shadow"
    ;;
  apk)
    PM_LABEL="apk (Alpine)"
    REFRESH=(apk update)
    INSTALL=(apk add --no-cache)
    PKG_GROUPS[wm]="i3wm i3lock xss-lock"
    PKG_GROUPS[terminal]="st build-base libx11-dev libxft-dev fontconfig-dev freetype-dev pkgconf ncurses curl"
    PKG_GROUPS[bar]="polybar"
    PKG_GROUPS[launcher]="rofi"
    PKG_GROUPS[compositor]="picom"
    PKG_GROUPS[notifications]="dunst"
    PKG_GROUPS[wallpaper]="feh"
    PKG_GROUPS[screenshot]="maim"
    PKG_GROUPS[clipboard]="xclip"
    PKG_GROUPS[media]="playerctl"
    PKG_GROUPS[audio-gui]="pavucontrol pasystray"
    PKG_GROUPS[audio-cli]="pulseaudio-utils"
    PKG_GROUPS[network]="network-manager-applet"
    PKG_GROUPS[xutils]="xrandr xset"
    PKG_GROUPS[kb]="setxkbmap"
    PKG_GROUPS[xprop]="xprop"
    PKG_GROUPS[display-gui]="arandr"
    PKG_GROUPS[theming]="lxappearance"
    PKG_GROUPS[fonts]="font-jetbrains-mono unzip"
    PKG_GROUPS[notify]="libnotify"
    PKG_GROUPS[calendar]="yad"
    PKG_GROUPS[elevate]="shadow"
    ;;
  none) ;;
esac

case "$PM" in
  apt) ADMIN_GROUP="sudo" ;;
  dnf|pacman|zypper|apk) ADMIN_GROUP="wheel" ;;
  *) ADMIN_GROUP="" ;;
esac

PACKAGES=()
for group in "${GROUP_ORDER[@]}"; do
  for pkg in ${PKG_GROUPS[$group]:-}; do
    PACKAGES+=("$pkg")
  done
done

if [ "$LIST_PACKAGES" = 1 ]; then
  echo "distro:  $DISTRO"
  echo "manager: $PM_LABEL"
  echo "admin group: ${ADMIN_GROUP:-(none)}"
  for group in "${GROUP_ORDER[@]}"; do
    printf '%-12s %s\n' "$group" "${PKG_GROUPS[$group]:-(none)}"
  done
  exit 0
fi

log "distro: $DISTRO"
[ "$PM" = "none" ] || log "package manager: $PM_LABEL"
log "scale: ${SCALE}% (Xft.dpi $DPI, cursor $CURSOR_SIZE px)"

SUDO=()
if [ "$INSTALL_PACKAGES" = 1 ] && [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || die "run as root, install sudo, or use --no-packages"
  SUDO=(sudo)
fi

write_config() {
  local target="$1"
  if [ "$DRY_RUN" = 1 ]; then
    cat >/dev/null
    log "[dry-run] would write $target"
    return 0
  fi
  mkdir -p "$(dirname "$target")"
  if [ -e "$target" ]; then
    cp -a "$target" "$target.bak-$STAMP"
    log "backed up $target -> $target.bak-$STAMP"
  fi
  cat > "$target"
  log "wrote $target"
}

update_managed_block() {
  local file="$1" content="$2" name="${3:-scaling}"
  local begin="# >>> i3-rice $name >>>"
  local end="# <<< i3-rice $name <<<"
  local tmp

  if [ "$DRY_RUN" = 1 ]; then
    log "[dry-run] would update the $name block in $file"
    return 0
  fi

  mkdir -p "$(dirname "$file")"
  touch "$file"
  if [ -s "$file" ]; then
    cp -a "$file" "$file.bak-$STAMP"
  fi

  tmp="$(mktemp)"
  awk -v b="$begin" -v e="$end" '
    $0 == b { skip = 1; next }
    $0 == e { skip = 0; next }
    !skip { print }
  ' "$file" > "$tmp"

  {
    cat "$tmp"
    printf '%s\n%s\n%s\n' "$begin" "$content" "$end"
  } > "$file"

  rm -f "$tmp"
  log "updated the $name block in $file"
}

apply_scaling() {
  [ "$DRY_RUN" = 1 ] && return 0

  local file
  for file in \
    "$HOME/.config/i3/config" \
    "$HOME/.config/polybar/config.ini" \
    "$HOME/.config/rofi/config.rasi" \
    "$HOME/.config/rofi/catppuccin-mocha.rasi" \
    "$HOME/.config/picom/picom.conf" \
    "$HOME/.config/dunst/dunstrc"; do
    [ -f "$file" ] || continue
    sed -i \
      -e "s|@SCALE_DPI@|$DPI|g" \
      -e "s|@ST_TERM@|$ST_TERM|g" \
      -e "s|@FONT_FAMILY@|$FONT_FAMILY|g" \
      -e "s|@ICON_CALENDAR@|$ICON_CALENDAR|g" \
      -e "s|@ICON_VOLUME@|$ICON_VOLUME|g" \
      -e "s|@ICON_MEMORY@|$ICON_MEMORY|g" \
      -e "s|@ICON_CPU@|$ICON_CPU|g" \
      -e "s|@I3_GAP_INNER@|$I3_GAP_INNER|g" \
      -e "s|@I3_GAP_OUTER@|$I3_GAP_OUTER|g" \
      -e "s|@I3_BORDER@|$I3_BORDER|g" \
      -e "s|@BAR_HEIGHT@|$BAR_HEIGHT|g" \
      -e "s|@BAR_PADDING@|$BAR_PADDING|g" \
      -e "s|@BAR_MARGIN@|$BAR_MARGIN|g" \
      -e "s|@ROFI_BORDER@|$ROFI_BORDER|g" \
      -e "s|@ROFI_RADIUS@|$ROFI_RADIUS|g" \
      -e "s|@ROFI_SMALL_RADIUS@|$ROFI_SMALL_RADIUS|g" \
      -e "s|@ROFI_PAD@|$ROFI_PAD|g" \
      -e "s|@ROFI_INPUT_PAD@|$ROFI_INPUT_PAD|g" \
      -e "s|@ROFI_ELEMENT_PAD@|$ROFI_ELEMENT_PAD|g" \
      -e "s|@DUNST_WIDTH@|$DUNST_WIDTH|g" \
      -e "s|@DUNST_HEIGHT@|$DUNST_HEIGHT|g" \
      -e "s|@DUNST_OFFSET@|$DUNST_OFFSET|g" \
      -e "s|@DUNST_FRAME@|$DUNST_FRAME|g" \
      -e "s|@DUNST_RADIUS@|$DUNST_RADIUS|g" \
      -e "s|@DUNST_PADDING@|$DUNST_PADDING|g" \
      -e "s|@DUNST_HPADDING@|$DUNST_HPADDING|g" \
      -e "s|@DUNST_ICON@|$DUNST_ICON|g" \
      -e "s|@PICOM_SHADOW_RADIUS@|$PICOM_SHADOW_RADIUS|g" \
      -e "s|@PICOM_SHADOW_OFFSET@|$PICOM_SHADOW_OFFSET|g" \
      -e "s|@PICOM_RADIUS@|$PICOM_RADIUS|g" \
      "$file"
  done

  log "applied ${SCALE}% scaling to the configs"
}

install_packages() {
  if [ "$PM" = "none" ]; then
    warn "no supported package manager; skipping package installation"
    return 0
  fi

  log "installing ${#PACKAGES[@]} packages with $PM_LABEL"

  if [ ${#REFRESH[@]} -gt 0 ]; then
    run "${SUDO[@]}" "${REFRESH[@]}" || warn "package index refresh failed; continuing"
  fi

  if run "${SUDO[@]}" "${INSTALL[@]}" "${PACKAGES[@]}"; then
    log "package installation finished"
    return 0
  fi

  warn "batch install failed; retrying one package at a time"
  local failed=()
  local pkg
  for pkg in "${PACKAGES[@]}"; do
    if run "${SUDO[@]}" "${INSTALL[@]}" "$pkg"; then
      :
    else
      failed+=("$pkg")
      warn "could not install $pkg"
    fi
  done
  if [ ${#failed[@]} -gt 0 ]; then
    warn "packages not installed: ${failed[*]}"
    warn "configs are still written; missing commands are listed after the install"
  fi
}

detect_target_user() {
  if [ -n "$TARGET_USER" ]; then
    printf '%s\n' "$TARGET_USER"
    return 0
  fi
  if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
    printf '%s\n' "$SUDO_USER"
    return 0
  fi
  local login
  login="$(logname 2>/dev/null || true)"
  if [ -n "$login" ] && [ "$login" != "root" ]; then
    printf '%s\n' "$login"
    return 0
  fi
  if [ -n "${USER:-}" ] && [ "$USER" != "root" ] && id "$USER" >/dev/null 2>&1; then
    printf '%s\n' "$USER"
    return 0
  fi
  printf '\n'
}

find_tool() {
  local name="$1" candidate
  if candidate="$(command -v "$name" 2>/dev/null)" && [ -n "$candidate" ]; then
    printf '%s\n' "$candidate"
    return 0
  fi
  for candidate in "/usr/sbin/$name" "/sbin/$name" "/usr/bin/$name" "/bin/$name"; do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

admin_tool_hint() {
  case "$PM" in
    apt) echo "apt-get install -y passwd" ;;
    dnf) echo "dnf install -y shadow-utils" ;;
    pacman) echo "pacman -S shadow" ;;
    zypper) echo "zypper install shadow" ;;
    apk) echo "apk add shadow" ;;
    *) echo "install your distro's passwd/shadow package" ;;
  esac
}

ensure_admin_group() {
  if [ "$SKIP_ADMIN_GROUP" = 1 ]; then
    log "skipping admin group changes (--no-admin-group)"
    return 0
  fi
  [ -n "$ADMIN_GROUP" ] || return 0

  local user tool
  user="$(detect_target_user)"
  if [ -z "$user" ]; then
    warn "could not determine which user to add to the $ADMIN_GROUP group"
    warn "rerun with --user <username>, or run: usermod -aG $ADMIN_GROUP <username>"
    return 0
  fi
  if ! id "$user" >/dev/null 2>&1; then
    warn "user '$user' does not exist; skipping $ADMIN_GROUP group membership"
    return 0
  fi
  if id -nG "$user" 2>/dev/null | tr ' ' '\n' | grep -qx "$ADMIN_GROUP"; then
    log "$user is already in the $ADMIN_GROUP group"
    return 0
  fi
  if ! grep -q "^${ADMIN_GROUP}:" /etc/group 2>/dev/null; then
    warn "group '$ADMIN_GROUP' does not exist; create it or add $user manually"
    return 0
  fi

  log "adding $user to the $ADMIN_GROUP group"

  # usermod lives in /usr/sbin on most distros and is often missing from PATH.
  if tool="$(find_tool usermod)"; then
    if run "${SUDO[@]}" "$tool" -aG "$ADMIN_GROUP" "$user"; then
      log "log out and back in (or run 'newgrp $ADMIN_GROUP') for the new group to apply"
      return 0
    fi
    warn "usermod failed: $tool -aG $ADMIN_GROUP $user"
  fi

  # gpasswd is a portable fallback and does the same group edit.
  if tool="$(find_tool gpasswd)"; then
    if run "${SUDO[@]}" "$tool" -a "$user" "$ADMIN_GROUP"; then
      log "log out and back in (or run 'newgrp $ADMIN_GROUP') for the new group to apply"
      return 0
    fi
    warn "gpasswd failed: $tool -a $user $ADMIN_GROUP"
  fi

  warn "neither usermod nor gpasswd is available"
  warn "install the provider package first: $(admin_tool_hint)"
  warn "then run: usermod -aG $ADMIN_GROUP $user"
}

install_st() {
  log "building st $ST_VERSION with Catppuccin Mocha and ${SCALE}% font"

  if [ "$DRY_RUN" = 1 ]; then
    log "[dry-run] would build st $ST_VERSION to $ST_BIN (pixelsize=$ST_FONT_PX)"
    return 0
  fi

  local missing=() tool
  for tool in cc make pkg-config; do
    command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
  done
  if [ ${#missing[@]} -gt 0 ]; then
    warn "skipping st build; missing tools: ${missing[*]}"
    warn "install the 'terminal' package group (build dependencies), then rerun"
    return 0
  fi

  local downloader=""
  if command -v curl >/dev/null 2>&1; then
    downloader="curl"
  elif command -v wget >/dev/null 2>&1; then
    downloader="wget"
  else
    warn "skipping st build; install curl or wget"
    return 0
  fi

  mkdir -p "$HOME/.cache/i3-rice" "$HOME/.local/bin"

  local tarball="$HOME/.cache/i3-rice/st-$ST_VERSION.tar.gz"
  local url="https://dl.suckless.org/st/st-$ST_VERSION.tar.gz"

  if [ ! -s "$tarball" ]; then
    log "downloading $url"
    if [ "$downloader" = "curl" ]; then
      curl -fsSL "$url" -o "$tarball" || { warn "could not download st source"; return 0; }
    else
      wget -qO "$tarball" "$url" || { warn "could not download st source"; return 0; }
    fi
  fi

  rm -rf "$ST_BUILD_DIR"
  mkdir -p "$ST_BUILD_DIR"
  if ! tar -xzf "$tarball" -C "$ST_BUILD_DIR" --strip-components=1; then
    warn "could not extract st source"
    return 0
  fi

  # Start from upstream defaults, replace the palette, then patch appearance.
  awk '
    /^static const char \*colorname\[\] = \{/ {
      print "static const char *colorname[] = {"
      print "\t/* Catppuccin Mocha */"
      print "\t\"#45475a\", \"#f38ba8\", \"#a6e3a1\", \"#f9e2af\","
      print "\t\"#89b4fa\", \"#f5c2e7\", \"#94e2d5\", \"#bac2de\","
      print "\t\"#585b70\", \"#f38ba8\", \"#a6e3a1\", \"#f9e2af\","
      print "\t\"#89b4fa\", \"#f5c2e7\", \"#94e2d5\", \"#a6adc8\","
      print ""
      print "\t[255] = 0,"
      print ""
      print "\t\"#f5e0dc\", /* cursor */"
      print "\t\"#1e1e2e\", /* reverse cursor */"
      print "\t\"#cdd6f4\", /* default foreground */"
      print "\t\"#1e1e2e\", /* default background */"
      print "};"
      skip = 1
      next
    }
    skip && /^};/ { skip = 0; next }
    !skip { print }
  ' "$ST_BUILD_DIR/config.def.h" > "$ST_BUILD_DIR/config.h"

  sed -i \
    -e "s|^static char \*font = .*|static char *font = \"$ST_FONT_FAMILY:pixelsize=$ST_FONT_PX:antialias=true:autohint=true\";|" \
    -e "s|^static int borderpx = .*|static int borderpx = $I3_BORDER;|" \
    -e "s|^unsigned int defaultfg = .*|unsigned int defaultfg = 258;|" \
    -e "s|^unsigned int defaultbg = .*|unsigned int defaultbg = 259;|" \
    -e "s|^unsigned int defaultcs = .*|unsigned int defaultcs = 256;|" \
    -e "s|^static unsigned int defaultrcs = .*|static unsigned int defaultrcs = 257;|" \
    "$ST_BUILD_DIR/config.h"

  local build_log="$HOME/.cache/i3-rice/st-build.log"
  if ! ( cd "$ST_BUILD_DIR" || exit 1; { make clean >/dev/null 2>&1 || true; }; make ) >"$build_log" 2>&1; then
    warn "st build failed; see $build_log"
    return 0
  fi

  install -m 0755 "$ST_BUILD_DIR/st" "$ST_BIN"
  mkdir -p "$HOME/.local/share/man/man1" "$HOME/.terminfo"
  sed "s/VERSION/$ST_VERSION/g" "$ST_BUILD_DIR/st.1" > "$HOME/.local/share/man/man1/st.1"
  if command -v tic >/dev/null 2>&1; then
    tic -x -o "$HOME/.terminfo" "$ST_BUILD_DIR/st.info" >/dev/null 2>&1 \
      || warn "could not install the st-256color terminfo entry"
  else
    warn "tic not found; install ncurses-bin/terminfo for st-256color"
  fi

  mkdir -p "$HOME/.local/share/applications"
  cat > "$HOME/.local/share/applications/st.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=st
GenericName=Terminal
Comment=Simple terminal (Catppuccin Mocha)
Exec=$ST_BIN
Icon=terminal
Terminal=false
Categories=System;TerminalEmulator;
Keywords=shell;prompt;command;commandline;
DESKTOP

  log "installed $ST_BIN"
}

font_available() {
  local needle="$1"
  command -v fc-list >/dev/null 2>&1 || return 1
  local families
  families="$(fc-list : family 2>/dev/null || true)"
  grep -qi "$needle" <<< "$families"
}

install_nerd_font() {
  local downloader="" file url
  if command -v curl >/dev/null 2>&1; then
    downloader="curl"
  elif command -v wget >/dev/null 2>&1; then
    downloader="wget"
  else
    warn "cannot download the Nerd Font; install curl or wget"
    return 1
  fi

  local dest="$HOME/.local/share/fonts/JetBrainsMonoNerdFont"
  local cache="$HOME/.cache/i3-rice/nerd-fonts"
  local base="https://raw.githubusercontent.com/ryanoasis/nerd-fonts/v$NERD_FONT_VERSION/patched-fonts/JetBrainsMono/Ligatures"
  mkdir -p "$dest" "$cache"

  for file in \
    JetBrainsMonoNerdFont-Regular.ttf \
    JetBrainsMonoNerdFont-Bold.ttf \
    JetBrainsMonoNerdFont-Italic.ttf \
    JetBrainsMonoNerdFont-BoldItalic.ttf \
    JetBrainsMonoNerdFontMono-Regular.ttf \
    JetBrainsMonoNerdFontMono-Bold.ttf \
    JetBrainsMonoNerdFontMono-Italic.ttf \
    JetBrainsMonoNerdFontMono-BoldItalic.ttf; do
    url="$base/$file"
    if [ ! -s "$cache/$file" ]; then
      if [ "$downloader" = "curl" ]; then
        curl -fsSL "$url" -o "$cache/$file" || return 1
      else
        wget -qO "$cache/$file" "$url" || return 1
      fi
    fi
    cp -f "$cache/$file" "$dest/$file" || return 1
  done

  if command -v fc-cache >/dev/null 2>&1; then
    fc-cache -f "$HOME/.local/share/fonts" >/dev/null 2>&1 || true
  fi
  return 0
}

install_font() {
  FONT_FAMILY="JetBrains Mono"
  ST_FONT_FAMILY="JetBrains Mono"

  if font_available 'JetBrainsMono Nerd Font'; then
    FONT_FAMILY="JetBrainsMono Nerd Font"
    ST_FONT_FAMILY="JetBrainsMono Nerd Font Mono"
    log "JetBrainsMono Nerd Font is available"
    return 0
  fi

  log "JetBrainsMono Nerd Font not found; installing it under ~/.local/share/fonts"

  if [ "$DRY_RUN" = 1 ]; then
    log "[dry-run] would install JetBrainsMono Nerd Font $NERD_FONT_VERSION"
    return 0
  fi

  if install_nerd_font && font_available 'JetBrainsMono Nerd Font'; then
    FONT_FAMILY="JetBrainsMono Nerd Font"
    ST_FONT_FAMILY="JetBrainsMono Nerd Font Mono"
    log "installed JetBrainsMono Nerd Font under ~/.local/share/fonts"
    return 0
  fi

  warn "could not install JetBrainsMono Nerd Font; trying standard JetBrains Mono"

  if font_available 'JetBrains Mono'; then
    log "using standard JetBrains Mono"
    return 0
  fi

  local downloader="" extractor="" zip url extract
  if command -v curl >/dev/null 2>&1; then
    downloader="curl"
  elif command -v wget >/dev/null 2>&1; then
    downloader="wget"
  else
    warn "cannot download JetBrains Mono; using monospace"
    FONT_FAMILY="monospace"
    ST_FONT_FAMILY="monospace"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    extractor="python3"
  elif command -v unzip >/dev/null 2>&1; then
    extractor="unzip"
  else
    warn "cannot extract JetBrains Mono; using monospace"
    FONT_FAMILY="monospace"
    ST_FONT_FAMILY="monospace"
    return 0
  fi

  mkdir -p "$HOME/.cache/i3-rice" "$HOME/.local/share/fonts/JetBrainsMono"

  zip="$HOME/.cache/i3-rice/JetBrainsMono-$JETBRAINS_VERSION.zip"
  url="https://github.com/JetBrains/JetBrainsMono/releases/download/v$JETBRAINS_VERSION/JetBrainsMono-$JETBRAINS_VERSION.zip"

  if [ ! -s "$zip" ]; then
    log "downloading $url"
    if [ "$downloader" = "curl" ]; then
      curl -fsSL "$url" -o "$zip" || { warn "font download failed"; FONT_FAMILY="monospace"; ST_FONT_FAMILY="monospace"; return 0; }
    else
      wget -qO "$zip" "$url" || { warn "font download failed"; FONT_FAMILY="monospace"; ST_FONT_FAMILY="monospace"; return 0; }
    fi
  fi

  extract="$HOME/.cache/i3-rice/JetBrainsMono-$JETBRAINS_VERSION"
  rm -rf "$extract"
  mkdir -p "$extract"
  if [ "$extractor" = "python3" ]; then
    python3 -m zipfile -e "$zip" "$extract" || { warn "font extraction failed"; FONT_FAMILY="monospace"; ST_FONT_FAMILY="monospace"; return 0; }
  else
    unzip -q "$zip" -d "$extract" || { warn "font extraction failed"; FONT_FAMILY="monospace"; ST_FONT_FAMILY="monospace"; return 0; }
  fi

  find "$extract" -type f -name '*.ttf' -exec cp -f {} "$HOME/.local/share/fonts/JetBrainsMono/" \;

  if command -v fc-cache >/dev/null 2>&1; then
    fc-cache -f "$HOME/.local/share/fonts" >/dev/null 2>&1 || warn "fc-cache failed"
  fi

  if font_available 'JetBrains Mono'; then
    log "installed standard JetBrains Mono under ~/.local/share/fonts"
  else
    warn "JetBrains Mono is still not visible; using monospace"
    FONT_FAMILY="monospace"
    ST_FONT_FAMILY="monospace"
  fi
}

if [ "$INSTALL_PACKAGES" = 1 ]; then
  install_packages
  ensure_admin_group
else
  log "skipping package installation (--no-packages)"
fi

install_font
install_st

# Nerd Font icons for Polybar (left empty when only the standard font is available).
if [[ "$FONT_FAMILY" == *Nerd* ]]; then
  ICON_CALENDAR="$(printf '\uf073')"
  ICON_VOLUME="$(printf '\uf028')"
  ICON_MEMORY="$(printf '\uf538')"
  ICON_CPU="$(printf '\uf2db')"
else
  ICON_CALENDAR=""
  ICON_VOLUME=""
  ICON_MEMORY=""
  ICON_CPU=""
fi

if [ "$DRY_RUN" = 1 ]; then
  ST_TERM="$ST_BIN"
elif [ -x "$ST_BIN" ]; then
  ST_TERM="$ST_BIN"
else
  ST_TERM="st"
  warn "st was not built; i3 and Rofi will use 'st' from PATH"
  warn "install the build dependencies and rerun without --no-packages"
fi

log "writing i3 config"
write_config "$HOME/.config/i3/config" <<'I3CONF'
# i3 config — Catppuccin Mocha
# Generated by install-i3-rice.sh. Reload with $mod+Shift+c, restart with $mod+Shift+r.

set $mod Mod4
set $term @ST_TERM@
set $menu --no-startup-id rofi -dpi @SCALE_DPI@ -show drun

set $ws1 "1:term"
set $ws2 "2:code"
set $ws3 "3:web"
set $ws4 "4:games"
set $ws5 "5:media"

set $base   #1e1e2e
set $text   #cdd6f4
set $blue   #89b4fa
set $mauve  #cba6f7
set $red    #f38ba8

font pango:@FONT_FAMILY@ 10

# Look and feel
default_border pixel @I3_BORDER@
default_floating_border pixel @I3_BORDER@
hide_edge_borders smart
smart_borders on
gaps inner @I3_GAP_INNER@
gaps outer @I3_GAP_OUTER@
smart_gaps on

client.focused          $blue $base $text $blue $blue
client.focused_inactive $base $base $text $base $base
client.unfocused        $base $base $text $base $base
client.urgent           $red  $base $text $red  $red
client.placeholder      $base $base $text $base $base
client.background       $base

# Workspaces: one per app
assign [class="^(st|St)"] $ws1
assign [class="^(Code|code)$"] $ws2
assign [class="^(firefox|LibreWolf|brave-browser|google-chrome|chromium|Chromium)$"] $ws3
assign [class="^(steam|Steam)$"] $ws4
assign [class="^steam_app_"] $ws4
assign [class="^vlc$"] $ws5

# Floating windows
for_window [window_type="dialog"] floating enable
for_window [class="^(pavucontrol|Lxappearance|Arandr)$"] floating enable
for_window [class="^(Yad|yad)$"] floating enable, move position center, focus
for_window [class="^Steam$" title="^(Friends List|Steam - News|Settings|Steam Settings)$"] floating enable

bindsym $mod+1 workspace $ws1
bindsym $mod+2 workspace $ws2
bindsym $mod+3 workspace $ws3
bindsym $mod+4 workspace $ws4
bindsym $mod+5 workspace $ws5
bindsym $mod+Shift+1 move container to workspace $ws1
bindsym $mod+Shift+2 move container to workspace $ws2
bindsym $mod+Shift+3 move container to workspace $ws3
bindsym $mod+Shift+4 move container to workspace $ws4
bindsym $mod+Shift+5 move container to workspace $ws5

# Launch and manage windows
bindsym $mod+Return exec --no-startup-id $term
bindsym $mod+d exec $menu
bindsym $mod+c exec --no-startup-id yad --calendar --title=Calendar --undecorated --center --fixed --skip-taskbar --on-top
bindsym $mod+a exec --no-startup-id pavucontrol
bindsym $mod+Tab exec --no-startup-id rofi -dpi @SCALE_DPI@ -show window
bindsym $mod+q kill

# Focus (vimmer style, arrows also work)
bindsym $mod+h focus left
bindsym $mod+j focus down
bindsym $mod+k focus up
bindsym $mod+l focus right
bindsym $mod+Left focus left
bindsym $mod+Down focus down
bindsym $mod+Up focus up
bindsym $mod+Right focus right

# Move windows
bindsym $mod+Shift+h move left
bindsym $mod+Shift+j move down
bindsym $mod+Shift+k move up
bindsym $mod+Shift+l move right
bindsym $mod+Shift+Left move left
bindsym $mod+Shift+Down move down
bindsym $mod+Shift+Up move up
bindsym $mod+Shift+Right move right

# Layout
bindsym $mod+b split h
bindsym $mod+v split v
bindsym $mod+f fullscreen toggle
bindsym $mod+Shift+space floating toggle
bindsym $mod+r mode "resize"

# Session
bindsym $mod+Escape exec --no-startup-id i3lock -n -c 1e1e2e
bindsym $mod+Shift+c reload
bindsym $mod+Shift+r restart
bindsym $mod+Shift+e exec --no-startup-id i3-nagbar -t warning -m 'Exit i3?' -B 'Yes, exit' 'i3-msg exit'

# Screenshots (region selection)
bindsym Print exec --no-startup-id sh -c 'maim -s | xclip -selection clipboard -t image/png'
bindsym $mod+Print exec --no-startup-id sh -c 'mkdir -p ~/Pictures && maim -s ~/Pictures/screenshot-$(date +%Y%m%d-%H%M%S).png'

# Audio and media keys
bindsym XF86AudioRaiseVolume exec --no-startup-id pactl set-sink-volume @DEFAULT_SINK@ +5%
bindsym XF86AudioLowerVolume exec --no-startup-id pactl set-sink-volume @DEFAULT_SINK@ -5%
bindsym XF86AudioMute exec --no-startup-id pactl set-sink-mute @DEFAULT_SINK@ toggle
bindsym XF86AudioMicMute exec --no-startup-id pactl set-source-mute @DEFAULT_SOURCE@ toggle
bindsym XF86AudioPlay exec --no-startup-id playerctl play-pause
bindsym XF86AudioNext exec --no-startup-id playerctl next
bindsym XF86AudioPrev exec --no-startup-id playerctl previous

mode "resize" {
    bindsym h resize shrink width 10 px or 10 ppt
    bindsym j resize grow height 10 px or 10 ppt
    bindsym k resize shrink height 10 px or 10 ppt
    bindsym l resize grow width 10 px or 10 ppt
    bindsym Left resize shrink width 10 px or 10 ppt
    bindsym Down resize grow height 10 px or 10 ppt
    bindsym Up resize shrink height 10 px or 10 ppt
    bindsym Right resize grow width 10 px or 10 ppt
    bindsym Return mode "default"
    bindsym Escape mode "default"
}

# i3bar is disabled; polybar draws the bar.
bar {
    mode invisible
}

# Autostart
# HiDPI: the session also merges this from ~/.xprofile before i3 starts.
exec --no-startup-id sh -c 'xrandr --dpi @SCALE_DPI@ 2>/dev/null || true'
exec --no-startup-id sh -c 'xrdb -merge ~/.config/i3/Xresources 2>/dev/null || true'
exec_always --no-startup-id ~/.config/polybar/launch.sh
exec --no-startup-id picom --config ~/.config/picom/picom.conf
exec --no-startup-id dunst
exec --no-startup-id nm-applet
exec --no-startup-id pasystray
exec --no-startup-id xss-lock --transfer-sleep-lock -- i3lock -n -c 1e1e2e
exec --no-startup-id sh -c '[ -f ~/Pictures/wallpaper.jpg ] && feh --bg-fill ~/Pictures/wallpaper.jpg'

# Uncomment and adjust after install:
# exec --no-startup-id setxkbmap us
# exec --no-startup-id xrandr --output DP-1 --mode 2560x1440 --rate 144
I3CONF

log "writing polybar config"
write_config "$HOME/.config/polybar/config.ini" <<'POLYBARCONF'
[colors]
background = #1e1e2e
background-alt = #313244
foreground = #cdd6f4
foreground-alt = #6c7086
primary = #89b4fa
secondary = #cba6f7
alert = #f38ba8

[bar/main]
monitor = ${env:MONITOR:}
width = 100%
height = @BAR_HEIGHT@
dpi = @SCALE_DPI@
radius = 0
fixed-center = true
background = ${colors.background}
foreground = ${colors.foreground}
line-size = 2
line-color = ${colors.primary}
padding-left = @BAR_PADDING@
padding-right = @BAR_PADDING@
module-margin-left = @BAR_MARGIN@
module-margin-right = @BAR_MARGIN@
font-0 = @FONT_FAMILY@:size=10;2
modules-left = i3
modules-center = date
modules-right = pulseaudio memory cpu

tray-position = right
tray-padding = 6
tray-maxsize = 24
tray-background = ${colors.background}
tray-foreground = ${colors.foreground}

[bar/secondary]
inherit = bar/main
tray-position = none

[module/i3]
type = internal/i3
format = <label-state> <label-mode>
label-mode-padding = 2
label-mode-foreground = ${colors.background}
label-mode-background = ${colors.primary}
label-focused = %name%
label-focused-background = ${colors.primary}
label-focused-foreground = ${colors.background}
label-focused-underline = ${colors.primary}
label-focused-padding = 2
label-unfocused = %name%
label-unfocused-padding = 2
label-visible = %name%
label-visible-underline = ${colors.secondary}
label-visible-padding = 2
label-urgent = %name%
label-urgent-background = ${colors.alert}
label-urgent-foreground = ${colors.background}
label-urgent-padding = 2

[module/date]
type = internal/date
interval = 5
date = %Y-%m-%d
time = %H:%M
label = @ICON_CALENDAR@  %date%  %time%
click-left = yad --calendar --title=Calendar --undecorated --center --fixed --skip-taskbar --on-top
label-foreground = ${colors.foreground}

[module/pulseaudio]
type = internal/pulseaudio
format-volume = <label-volume>
label-volume = @ICON_VOLUME@ %percentage%%
label-muted = @ICON_VOLUME@ MUTED
label-muted-foreground = ${colors.foreground-alt}
click-left = pactl set-sink-mute @DEFAULT_SINK@ toggle
click-right = pavucontrol
scroll-up = pactl set-sink-volume @DEFAULT_SINK@ +5%
scroll-down = pactl set-sink-volume @DEFAULT_SINK@ -5%

[module/memory]
type = internal/memory
interval = 5
format = @ICON_MEMORY@ <label>
label = %percentage_used%%
label-foreground = ${colors.foreground}

[module/cpu]
type = internal/cpu
interval = 2
format = @ICON_CPU@ <label>
label = %percentage%%
label-foreground = ${colors.foreground}

[settings]
screenchange-reload = true
compositing-background = source
compositing-foreground = over
POLYBARCONF

log "writing polybar launcher"
write_config "$HOME/.config/polybar/launch.sh" <<'POLYBARLAUNCH'
#!/usr/bin/env bash
set -euo pipefail

# Kill existing bars, then launch one per connected monitor.
pkill -x polybar 2>/dev/null || true
while pgrep -u "$UID" -x polybar >/dev/null 2>&1; do
  sleep 0.2
done

if ! command -v xrandr >/dev/null 2>&1; then
  polybar --reload main &
  exit 0
fi

monitors=$(xrandr --query 2>/dev/null | awk '/ connected/ { print $1 }') || monitors=""

if [ -z "$monitors" ]; then
  polybar --reload main &
else
  primary=$(xrandr --query 2>/dev/null | awk '/ primary / { print $1; exit }')
  if [ -z "$primary" ]; then
    primary=$(printf '%s\n' "$monitors" | head -n1)
  fi

  while IFS= read -r monitor; do
    [ -n "$monitor" ] || continue
    if [ "$monitor" = "$primary" ]; then
      MONITOR="$monitor" polybar --reload main &
    else
      MONITOR="$monitor" polybar --reload secondary &
    fi
  done <<< "$monitors"
fi
POLYBARLAUNCH

log "writing rofi config"
write_config "$HOME/.config/rofi/config.rasi" <<'ROFICONF'
configuration {
    modi: "drun,run,window";
    show-icons: true;
    terminal: "@ST_TERM@";
    drun-display-format: "{name}";
    display-drun: "Apps";
    display-run: "Run";
    display-window: "Windows";
    font: "@FONT_FAMILY@ 11";
}

@import "catppuccin-mocha.rasi"
ROFICONF

write_config "$HOME/.config/rofi/catppuccin-mocha.rasi" <<'ROFITHEME'
* {
    bg: #1e1e2e;
    bg-alt: #313244;
    fg: #cdd6f4;
    fg-alt: #6c7086;
    accent: #89b4fa;
    urgent: #f38ba8;

    background-color: transparent;
    text-color: @fg;
    border: 0;
    margin: 0;
    padding: 0;
    spacing: 0;
}

window {
    width: 40%;
    background-color: @bg;
    border: @ROFI_BORDER@px;
    border-color: @accent;
    border-radius: @ROFI_RADIUS@px;
    padding: @ROFI_PAD@px;
}

mainbox {
    children: [inputbar, listview];
    spacing: 8px;
}

inputbar {
    background-color: @bg-alt;
    border-radius: @ROFI_SMALL_RADIUS@px;
    padding: @ROFI_INPUT_PAD@;
    children: [prompt, entry];
}

prompt {
    text-color: @accent;
    margin: 0 8px 0 0;
}

entry {
    text-color: @fg;
    placeholder: "Search...";
    placeholder-color: @fg-alt;
}

listview {
    lines: 8;
    columns: 1;
    spacing: 4px;
    scrollbar: false;
}

element {
    padding: @ROFI_ELEMENT_PAD@;
    border-radius: @ROFI_SMALL_RADIUS@px;
    background-color: transparent;
    text-color: @fg;
}

element selected {
    background-color: @accent;
    text-color: @bg;
}

element-text {
    vertical-align: 0.5;
}

element-icon {
    size: 1.2em;
}
ROFITHEME

log "writing picom config"
write_config "$HOME/.config/picom/picom.conf" <<'PICOMCONF'
# Catppuccin Mocha picom — glx, vsync, shadows, rounded corners, no blur.
backend = "glx";
vsync = true;

shadow = true;
shadow-radius = @PICOM_SHADOW_RADIUS@;
shadow-opacity = 0.30;
shadow-offset-x = @PICOM_SHADOW_OFFSET@;
shadow-offset-y = @PICOM_SHADOW_OFFSET@;
shadow-exclude = [
  "window_type = 'dock'",
  "window_type = 'desktop'",
  "class_g = 'Polybar'",
  "class_g = 'st'",
  "class_g = 'St'",
  "class_g = 'st-256color'",
  "class_g = 'St-256color'",
];

corner-radius = @PICOM_RADIUS@;
rounded-corners-exclude = [
  "window_type = 'dock'",
  "window_type = 'desktop'",
  "class_g = 'Polybar'",
];

frame-opacity = 1.0;
inactive-opacity = 1.0;
active-opacity = 1.0;

blur-background = false;
blur-method = "none";

# Slightly translucent terminal windows.
opacity-rule = [
  "80:class_g = 'st'",
  "80:class_g = 'St'",
  "80:class_g = 'st-256color'",
  "80:class_g = 'St-256color'",
];

focus-exclude = [
  "class_g = 'Steam'",
  "class_g = 'i3lock'",
];

# Reduce flicker on some NVIDIA/X11 setups. Remove if it causes artifacts.
glx-no-stencil = true;
PICOMCONF

log "writing dunst config"
write_config "$HOME/.config/dunst/dunstrc" <<'DUNSTCONF'
[global]
    monitor = 0
    follow = mouse
    width = @DUNST_WIDTH@
    height = @DUNST_HEIGHT@
    origin = top-right
    offset = @DUNST_OFFSET@
    frame_width = @DUNST_FRAME@
    frame_color = "#89b4fa"
    separator_color = frame
    font = @FONT_FAMILY@ 10
    corner_radius = @DUNST_RADIUS@
    background = "#1e1e2e"
    foreground = "#cdd6f4"
    timeout = 8
    transparency = 0
    padding = @DUNST_PADDING@
    horizontal_padding = @DUNST_HPADDING@
    icon_position = left
    max_icon_size = @DUNST_ICON@
    markup = full

[urgency_low]
    background = "#1e1e2e"
    foreground = "#cdd6f4"
    frame_color = "#6c7086"
    timeout = 5

[urgency_normal]
    background = "#1e1e2e"
    foreground = "#cdd6f4"
    frame_color = "#89b4fa"
    timeout = 8

[urgency_critical]
    background = "#1e1e2e"
    foreground = "#f38ba8"
    frame_color = "#f38ba8"
    timeout = 0
DUNSTCONF

log "writing HiDPI resources"
write_config "$HOME/.config/i3/Xresources" <<XRES
Xft.dpi: $DPI
Xcursor.size: $CURSOR_SIZE
XRES

log "writing session scaling environment"
write_config "$HOME/.config/i3/scale.env" <<ENV
# Generated by install-i3-rice.sh for ${SCALE}% scaling.
# GTK: integer window scale; GDK_DPI_SCALE cancels text double-scaling.
export GDK_SCALE=$GDK_SCALE_VALUE
export GDK_DPI_SCALE=$GDK_DPI_SCALE
export QT_AUTO_SCREEN_SCALE_FACTOR=0
export QT_FONT_DPI=96
export QT_SCALE_FACTOR=$SCALE_FACTOR
export XCURSOR_SIZE=$CURSOR_SIZE

# st is installed in ~/.local/bin; keep it on PATH.
case ":\$PATH:" in
  *":\$HOME/.local/bin:"*) ;;
  *) export PATH="\$HOME/.local/bin:\$PATH" ;;
esac
ENV

SCALE_BLOCK='[ -f "$HOME/.config/i3/scale.env" ] && . "$HOME/.config/i3/scale.env"
[ -f "$HOME/.config/i3/Xresources" ] && xrdb -merge "$HOME/.config/i3/Xresources"'
PATH_BLOCK='case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac'
log "wiring scaling into the X session"
update_managed_block "$HOME/.xprofile" "$SCALE_BLOCK"
update_managed_block "$HOME/.xsessionrc" "$SCALE_BLOCK"
update_managed_block "$HOME/.profile" "$PATH_BLOCK" path
update_managed_block "$HOME/.bashrc" "$PATH_BLOCK" path

apply_scaling

if [ -f "$WALLPAPER_SRC" ]; then
  if [ "$DRY_RUN" = 1 ]; then
    log "[dry-run] would install the packaged wallpaper to ~/Pictures/wallpaper.jpg"
  else
    mkdir -p "$HOME/Pictures"
    if [ ! -f "$HOME/Pictures/wallpaper.jpg" ]; then
      cp "$WALLPAPER_SRC" "$HOME/Pictures/wallpaper.jpg"
      log "installed wallpaper -> ~/Pictures/wallpaper.jpg"
    else
      log "keeping existing ~/Pictures/wallpaper.jpg"
    fi
    if [ "$(id -u)" -ne 0 ] && command -v feh >/dev/null 2>&1 && [ -n "${DISPLAY:-}" ]; then
      feh --bg-fill "$HOME/Pictures/wallpaper.jpg" >/dev/null 2>&1 || true
    fi
  fi
fi

if [ "$DRY_RUN" = 0 ]; then
  chmod +x "$HOME/.config/polybar/launch.sh"
fi

if [ "$DRY_RUN" = 0 ] && [ ! -f "$HOME/Pictures/wallpaper.jpg" ]; then
  warn "no wallpaper at ~/Pictures/wallpaper.jpg — the background will stay black"
  [ -f "$WALLPAPER_SRC" ] || warn "packaged wallpaper not found at $WALLPAPER_SRC"
fi

if [ "$DRY_RUN" = 0 ]; then
  missing=()
  for cmd in i3 polybar rofi picom dunst feh i3lock xss-lock maim xclip pactl nm-applet yad pasystray; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  if [ ! -x "$ST_BIN" ] && ! command -v st >/dev/null 2>&1; then
    missing+=("st")
  fi
  if [ ${#missing[@]} -gt 0 ]; then
    warn "missing commands: ${missing[*]}"
    warn "install them with your package manager, or edit the configs that use them"
  fi
  if command -v fc-list >/dev/null 2>&1; then
    font_families="$(fc-list : family 2>/dev/null || true)"
    if ! grep -Eqi 'JetBrainsMono Nerd Font|JetBrains Mono' <<< "$font_families"; then
      warn "JetBrainsMono Nerd Font / JetBrains Mono is not installed; Pango/Polybar will fall back"
    fi
  fi
fi

log "done"
printf '\nScaling: %s%% (Xft.dpi %s, cursor %s px).\n' "$SCALE" "$DPI" "$CURSOR_SIZE"
printf 'If i3 titlebars look small on first login, restart i3 with $mod+Shift+r.\n'
printf 'Use --scale 100 for standard-density displays.\n'
cat <<'NEXT'

Next steps:
  1. Start i3: choose it at your display manager, or put `exec i3` in ~/.xinitrc and run `startx`.
  2. Verify window classes: xprop WM_CLASS, then fix assign rules in ~/.config/i3/config.
  3. Set your keyboard layout: edit ~/.config/i3/config, uncomment the setxkbmap line.
  4. Set monitor mode/rate: xrandr --query, then uncomment the xrandr line.
  5. The packaged wallpaper is at ~/Pictures/wallpaper.jpg; replace it if you like.
  6. Theme GTK apps with lxappearance (Catppuccin GTK theme and cursor).
  7. Test video/games. On NVIDIA tearing, enable Force Full Composition Pipeline in nvidia-settings.
  8. In a VM or with software rendering, if picom flickers or crashes, set
     backend = "xrender" and vsync = false in ~/.config/picom/picom.conf.

Reload i3 with $mod+Shift+c after editing its config.
NEXT
