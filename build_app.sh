#!/bin/bash
# build_app.sh — build "Analiza Kolarska.app" for the macOS Dock.
#
# Run this ONCE on your Mac from inside the repo:
#     cd ~/Documents/Analiza_Kolarska
#     bash build_app.sh
#
# It creates ~/Applications/Analiza Kolarska.app. Drag it to the Dock.
# The app's executable calls this repo's launcher.sh, so it stays in sync
# with the code — no rebuild needed after you edit/pull the project.

set -euo pipefail

APP_NAME="Analiza Kolarska"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Build into /Applications so it shows in the standard Applications folder.
# Fall back to ~/Applications only if /Applications is not writable.
if touch "/Applications/.ak_write_test" 2>/dev/null; then
  rm -f "/Applications/.ak_write_test"
  APP_DIR="/Applications/$APP_NAME.app"
else
  mkdir -p "$HOME/Applications"
  APP_DIR="$HOME/Applications/$APP_NAME.app"
fi
echo "Target: $APP_DIR"
MACOS_DIR="$APP_DIR/Contents/MacOS"
RES_DIR="$APP_DIR/Contents/Resources"
PLIST="$APP_DIR/Contents/Info.plist"
ICON_PNG="$SCRIPT_DIR/icon.png"

echo "=== Building $APP_NAME.app ==="

# 0. Regenerate icon.png if Pillow is available and it's missing
if [ ! -f "$ICON_PNG" ]; then
  echo "icon.png missing — attempting to generate it (needs Pillow)..."
  python3 "$SCRIPT_DIR/make_icon.py" || {
    echo "Could not generate icon.png. Install Pillow: pip3 install Pillow"; exit 1; }
fi

# 1. Bundle skeleton
rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RES_DIR"

# 2. Executable — fires the repo's launcher.sh in the BACKGROUND and returns
#    immediately. If it blocked (exec) on the launcher's readiness loop, macOS
#    would flag the app as "not responding".
cat > "$MACOS_DIR/AnalizaKolarska" <<EOF
#!/bin/bash
nohup "$SCRIPT_DIR/launcher.sh" >/dev/null 2>&1 &
exit 0
EOF
chmod 755 "$MACOS_DIR/AnalizaKolarska"
chmod 755 "$SCRIPT_DIR/launcher.sh" 2>/dev/null || true

# 3. Convert icon.png -> AppIcon.icns (macOS iconutil)
echo "Building icon..."
ICONSET="$(mktemp -d)/AppIcon.iconset"
mkdir -p "$ICONSET"
for sz in 16 32 64 128 256 512 1024; do
  sips -z "$sz" "$sz" "$ICON_PNG" --out "$ICONSET/icon_${sz}x${sz}.png" >/dev/null
done
# retina (@2x) variants expected by iconutil
cp "$ICONSET/icon_32x32.png"   "$ICONSET/icon_16x16@2x.png"
cp "$ICONSET/icon_64x64.png"   "$ICONSET/icon_32x32@2x.png"
cp "$ICONSET/icon_256x256.png" "$ICONSET/icon_128x128@2x.png"
cp "$ICONSET/icon_512x512.png" "$ICONSET/icon_256x256@2x.png"
cp "$ICONSET/icon_1024x1024.png" "$ICONSET/icon_512x512@2x.png"
iconutil -c icns "$ICONSET" -o "$RES_DIR/AppIcon.icns"
echo "  -> AppIcon.icns installed"

# 4. Info.plist
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>AnalizaKolarska</string>
    <key>CFBundleIdentifier</key>
    <string>com.wielkikrzych.analiza-kolarska</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
PLISTEOF
echo "  -> Info.plist written"

# 5. De-quarantine + adhoc sign so Gatekeeper lets it run
xattr -dr com.apple.quarantine "$APP_DIR" 2>/dev/null || true
codesign --force --deep --sign - "$APP_DIR" 2>/dev/null || true
# refresh icon cache
touch "$APP_DIR"

echo ""
echo "=== Done ==="
echo "App:  $APP_DIR"
echo "Open: open \"$APP_DIR\"   (then drag it from ~/Applications to the Dock)"
echo "Logs: /tmp/analiza_kolarska_launch.log"
