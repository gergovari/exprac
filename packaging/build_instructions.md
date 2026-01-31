# ExPrac v1.0 Release Build Instructions

This guide explains how to build the standalone versioned executables for Linux and Windows using the provided automation scripts.

## 🛠️ Prerequisites

1.  **Linux Environment** (Distributions like Fedora, Ubuntu, etc.)
2.  **Docker or Podman** (Required for the Windows cross-compilation script)
3.  **Python 3.10+** and `pyinstaller` (Required for the Linux build script)

## 🐧 Linux (AppImage)

The Linux build script generates a portable AppImage.

1.  **Run the build script**:
    ```bash
    ./packaging/build/appimage.sh
    ```
2.  **Output**: The single versioned file `dist/ExPrac-x86_64-v1.0.AppImage` will be created in the project root's `dist/` directory.
    *Note: All temporary build files are isolated in the root `build/` directory.*

## 🪟 Windows (.exe)

The Windows build is performed via Docker cross-compilation directly on Linux.

1.  **Run the Windows build script**:
    ```bash
    ./packaging/build/windows.sh
    ```
2.  **Output**: The single versioned file `dist/ExPrac-x86_64-v1.0.exe` will be created in the project root's `dist/` directory.
    *Note: This EXE is configured to automatically spawn a terminal when opened.*

## 📦 Distribution
Distribution is simple—just share the single versioned file from the `dist/` folder! No installation or extra folders (like `dist/ExPrac/`) are required for the end user.
