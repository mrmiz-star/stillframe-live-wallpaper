# Stillframe — Windows Live Wallpaper Studio

Stillframe is a Windows desktop controller for looping local video wallpapers behind desktop icons. It uses PySide6/Qt Multimedia for playback and attaches a borderless video surface to the Explorer `WorkerW` desktop layer.

## Features

- Add multiple local videos to a persistent playlist; duplicate entries are skipped.
- Navigate tracks, reorder or remove them, and toggle shuffle.
- Each selected video loops continuously; pause/play and adjustable audio volume are available.
- Playlist, current selection, and volume are saved between launches.
- Optional launch-at-sign-in setting, stored for the current Windows user.

## Requirements

- Windows 10 or 11 (64-bit)
- Python 3.10 or newer (64-bit) for source mode
- Video supported by Qt Multimedia/Windows codecs; MP4/H.264 is recommended

## Run from source

Open PowerShell in this folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Use **Add videos** to create a playlist, select a track, then click **Set as wallpaper**. Volume is saved; set it to 0 for silence. The startup checkbox adds/removes the app in the current user's Windows Run registry key.

## Build a standalone executable

Run `build_windows.bat` on Windows. It writes an onedir build to `dist\Stillframe\Stillframe.exe`. Qt Multimedia requires its plugins and runtime libraries alongside the executable, so distribute the **entire** `dist\Stillframe` folder, preferably zipped—not only the EXE.

## Limitations and recovery

- This is an independent starter project, not a fully tested replacement for established wallpaper software.
- The WorkerW attachment relies on undocumented Explorer behavior and can be affected by Windows updates or shell customizations. If it fails, close and reopen Stillframe; if needed, restart Windows Explorer from Task Manager.
- Current wallpaper rendering targets the primary display only. A multi-display mode is not included yet.
- Closing Stillframe stops playback and removes its wallpaper window. Startup launch starts the controller; applying the wallpaper may still require Explorer initialization and a saved playlist path that exists.
- If a file opens but stays black, try an MP4/H.264 video and ensure the necessary Windows media codecs are installed.
- This project was syntax-checked in a Linux sandbox; the Windows Explorer integration and packaged executable have not been runtime-tested here.

## Project files

- `app.py` — playlist, controls, persistence, startup option, playback, and desktop integration.
- `requirements.txt` — Python dependency.
- `build_windows.bat` — Windows packaging command.

## Build from GitHub

The repository includes a GitHub Actions workflow at `.github/workflows/windows-build.yml`. It builds on `windows-latest` after pushes to `main`, and can also be run manually from the repository's **Actions** tab using **Build Windows app → Run workflow**. When the run succeeds, open that run and download the **Stillframe-Windows** artifact from its Artifacts section. Extract the ZIP and launch `Stillframe\Stillframe.exe`; keep the full folder together.
