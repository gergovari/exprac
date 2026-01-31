# ExPrac v1.0 Release Build Instructions

This guide explains how to build the standalone executables for Windows and Linux.

## 🛠️ Prerequisites

1.  Python 3.10+
2.  Install build dependencies:
    ```bash
    pip install pyinstaller
    ```

## 🐧 Linux (AppImage)

The easiest way to build the AppImage is using the provided automation script. It will automatically download the required tools and package everything into a single file.

1.  **Run the build script**:
    ```bash
    ./packaging/build/appimage.sh
    ```
    *Note: The script will download `appimagetool` into the `packaging/build/` directory if missing.*

## 🪟 Windows (.exe)

1.  Open PowerShell or Command Prompt.
2.  Run PyInstaller:
    ```bash
    pyinstaller packaging/ExPrac.spec
    ```
3.  The executable will be in `dist/ExPrac/ExPrac.exe`.

## 📦 Distribution
- **Windows**: Zip the `dist/ExPrac` folder (or just the `.exe` if you consolidate to onefile).
- **Linux**: The `.AppImage` file in the project root is ready for distribution as a single portable file.
