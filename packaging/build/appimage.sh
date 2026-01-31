#!/bin/bash
# ExPrac AppImage Automation Script
# Should be run from the project root: ./packaging/build/appimage.sh

set -e

# 1. Setup paths
BASE_DIR=$(pwd)
PACKAGING_DIR="$BASE_DIR/packaging"
BUILD_TOOLS_DIR="$PACKAGING_DIR/build"
# Non-dist artifacts go to project root build/
APPDIR="$BASE_DIR/build/ExPrac.AppDir"
OUT_IMAGE="ExPrac.AppImage"
TOOL_NAME="appimagetool-x86_64.AppImage"
TOOL_PATH="$BUILD_TOOLS_DIR/$TOOL_NAME"

echo "🚀 Starting ExPrac v1.0 Build Process..."

# 2. Ensure appimagetool exists
if [ ! -f "$TOOL_PATH" ] && ! command -v appimagetool >/dev/null 2>&1; then
    echo "⬇️ Downloading appimagetool..."
    curl -L -o "$TOOL_PATH" "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$TOOL_PATH"
fi

# 3. Clean previous builds
echo "🧹 Cleaning old build files..."
rm -rf build dist "$APPDIR" "$OUT_IMAGE"

# 4. Running PyInstaller
echo "🛠️ Building binaries with PyInstaller..."
pyinstaller "$PACKAGING_DIR/ExPrac.spec"

# 5. Prepare AppDir
echo "📂 Preparing AppDir structure..."
mkdir -p "$APPDIR"
cp -r "$BASE_DIR/dist/ExPrac.AppImage"/* "$APPDIR/"
cp "$PACKAGING_DIR/AppRun" "$APPDIR/"
cp "$PACKAGING_DIR/exprac.desktop" "$APPDIR/"
cp "$PACKAGING_DIR/icon.png" "$APPDIR/"

chmod +x "$APPDIR/AppRun"

# 6. Build AppImage
echo "📦 Generating AppImage..."
if command -v appimagetool >/dev/null 2>&1; then
    appimagetool "$APPDIR" "$OUT_IMAGE"
else
    "$TOOL_PATH" "$APPDIR" "$OUT_IMAGE"
fi

echo "✅ Build Complete: $OUT_IMAGE"
