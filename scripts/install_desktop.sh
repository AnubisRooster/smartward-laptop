#!/bin/bash
# Installs SmartWard's launcher entry and icons for the current user (no sudo):
#   scripts/install_desktop.sh            use the native window  (resources/smartward-ui-bin/smartward)
#   scripts/install_desktop.sh --browser  use the browser launcher (bin/start_smartward.sh)
set -e
APP="$(cd "$(dirname "$0")/.." && pwd)"
ID="com.mikefink.smartward"
ICONS="$HOME/.local/share/icons/hicolor"
APPS="$HOME/.local/share/applications"

if [ "$1" = "--browser" ]; then EXEC="$APP/bin/start_smartward.sh"; else EXEC="$APP/resources/smartward-ui-bin/smartward"; fi
[ -x "$EXEC" ] || { echo "Missing $EXEC (build it with scripts/build_native.sh)" >&2; exit 1; }

mkdir -p "$ICONS/scalable/apps" "$APPS"
cp "$APP/resources/icons/smartward.svg" "$ICONS/scalable/apps/$ID.svg"
for pair in "32:32x32.png" "64:64x64.png" "128:128x128.png" "256:128x128@2x.png" "512:icon.png"; do
  size="${pair%%:*}"; file="${pair#*:}"
  mkdir -p "$ICONS/${size}x${size}/apps"
  cp "$APP/frontend/src-tauri/icons/$file" "$ICONS/${size}x${size}/apps/$ID.png"
done

# The menu entry from before this one would show a second "SmartWard": set it aside.
[ -f "$APPS/smartward.desktop" ] && mv "$APPS/smartward.desktop" "$APPS/smartward.desktop.old"

cat > "$APPS/$ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=SmartWard
GenericName=Research strategist
Comment=Local-first research strategist: follow sources, search, ask, listen
Exec=$EXEC
Icon=$ID
Terminal=false
Categories=Office;
Keywords=AI;Research;Reading;Knowledge;Graph;RSS;
StartupNotify=true
StartupWMClass=$ID
Actions=refresh;

[Desktop Action refresh]
Name=Refresh sources now
Exec=curl -s -m 10 -X POST -H "Content-Type: application/json" -d {} http://127.0.0.1:8000/api/refresh
EOF
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -f -t "$ICONS" 2>/dev/null || true
echo "Installed $APPS/$ID.desktop (launches $EXEC)"
