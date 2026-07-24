#!/bin/bash
# build_app.sh — build "Analiza Kolarska.app" for the macOS Dock.
#
# Run once on your Mac:
#     cd ~/Documents/Analiza_Kolarska && bash build_app.sh
#
# Builds an AppleScript applet (via osacompile) whose only job is to launch
# this repo's launcher.sh in the background. An applet is a real macOS app
# that LaunchServices starts cleanly — unlike a raw shell-script executable,
# it neither hangs ("not responding") nor gets its background child reaped.
# The app stays in sync with the code because it calls launcher.sh from the repo.

set -euo pipefail

APP_NAME="Analiza Kolarska"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCHER="$SCRIPT_DIR/launcher.sh"
ICON_PNG="$SCRIPT_DIR/icon.png"
BUNDLE_ID="com.wielkikrzych.analiza-kolarska"

# --- Choose target: /Applications if writable, else ~/Applications ----------
if touch "/Applications/.ak_write_test" 2>/dev/null; then
  rm -f "/Applications/.ak_write_test"
  APP_DIR="/Applications/$APP_NAME.app"
else
  mkdir -p "$HOME/Applications"
  APP_DIR="$HOME/Applications/$APP_NAME.app"
fi
echo "Target: $APP_DIR"

# --- Ensure icon + launcher are ready ---------------------------------------
if [ ! -f "$ICON_PNG" ]; then
  echo "icon.png missing — generating (needs Pillow)..."
  python3 "$SCRIPT_DIR/make_icon.py" || { echo "Install Pillow: pip3 install Pillow"; exit 1; }
fi
chmod 755 "$LAUNCHER"

echo "=== Building $APP_NAME.app ==="

# --- 1. Compile the AppleScript applet --------------------------------------
rm -rf "$APP_DIR"
WORK="$(mktemp -d)"
SCPT="$WORK/applet.applescript"
cat > "$SCPT" <<APPLEEOF
on run
	do shell script "nohup " & quoted form of "$LAUNCHER" & " > /dev/null 2>&1 &"
end run
APPLEEOF
osacompile -o "$APP_DIR" "$SCPT"
echo "  -> applet compiled"

# --- 2. Icon: replace the applet's icns with ours ---------------------------
ICONSET="$WORK/AppIcon.iconset"
mkdir -p "$ICONSET"
for sz in 16 32 64 128 256 512 1024; do
  sips -z "$sz" "$sz" "$ICON_PNG" --out "$ICONSET/icon_${sz}x${sz}.png" >/dev/null
done
cp "$ICONSET/icon_32x32.png"     "$ICONSET/icon_16x16@2x.png"
cp "$ICONSET/icon_64x64.png"     "$ICONSET/icon_32x32@2x.png"
cp "$ICONSET/icon_256x256.png"   "$ICONSET/icon_128x128@2x.png"
cp "$ICONSET/icon_512x512.png"   "$ICONSET/icon_256x256@2x.png"
cp "$ICONSET/icon_1024x1024.png" "$ICONSET/icon_512x512@2x.png"
# Write the .icns as BOTH names osacompile/AppKit may use, and as AppIcon.icns
iconutil -c icns "$ICONSET" -o "$APP_DIR/Contents/Resources/applet.icns"
cp "$APP_DIR/Contents/Resources/applet.icns" "$APP_DIR/Contents/Resources/AppIcon.icns"
echo "  -> icns installed"

# --- 3. Info.plist tweaks (name, id, agent app) -----------------------------
PLIST="$APP_DIR/Contents/Info.plist"
PB=/usr/libexec/PlistBuddy
$PB -c "Set :CFBundleName $APP_NAME"        "$PLIST" 2>/dev/null || $PB -c "Add :CFBundleName string $APP_NAME" "$PLIST"
$PB -c "Set :CFBundleDisplayName $APP_NAME" "$PLIST" 2>/dev/null || $PB -c "Add :CFBundleDisplayName string $APP_NAME" "$PLIST"
$PB -c "Set :CFBundleIdentifier $BUNDLE_ID" "$PLIST" 2>/dev/null || $PB -c "Add :CFBundleIdentifier string $BUNDLE_ID" "$PLIST"
$PB -c "Set :CFBundleIconFile applet"       "$PLIST" 2>/dev/null || $PB -c "Add :CFBundleIconFile string applet" "$PLIST"
$PB -c "Set :LSUIElement true"              "$PLIST" 2>/dev/null || $PB -c "Add :LSUIElement bool true" "$PLIST"
echo "  -> Info.plist patched"

# --- 4. De-quarantine, adhoc sign -------------------------------------------
xattr -dr com.apple.quarantine "$APP_DIR" 2>/dev/null || true
codesign --force --deep --sign - "$APP_DIR" 2>/dev/null || true

# --- 5. Force a real custom Finder icon via AppKit (authoritative override) --
# osacompile applets otherwise keep the default white "script" icon; setting
# the icon through NSWorkspace writes the custom-icon resource that Finder and
# the Dock actually read. Done AFTER signing so it isn't stripped.
osascript - "$ICON_PNG" "$APP_DIR" >/dev/null 2>&1 <<'OSA' || echo "  (custom-icon step skipped)"
use framework "AppKit"
use scripting additions
on run argv
	set imgPath to item 1 of argv
	set appPath to item 2 of argv
	set img to current application's NSImage's alloc()'s initWithContentsOfFile:imgPath
	current application's NSWorkspace's sharedWorkspace()'s setIcon:img forFile:appPath options:0
end run
OSA
echo "  -> custom icon applied"

# --- 6. Bust icon/LaunchServices caches -------------------------------------
touch "$APP_DIR"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[ -x "$LSREGISTER" ] && "$LSREGISTER" -f "$APP_DIR" >/dev/null 2>&1 || true
killall Dock 2>/dev/null || true

rm -rf "$WORK"
echo ""
echo "=== Done ==="
echo "App:  $APP_DIR"
echo "Run:  open \"$APP_DIR\""
echo "Log:  /tmp/analiza_kolarska_launch.log"
echo ""
echo "If the Dock still shows a blank icon: remove the app from the Dock and"
echo "drag it back from $(dirname "$APP_DIR") — a rebuild replaces the bundle,"
echo "which orphans a previously pinned Dock item."
