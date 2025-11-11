# Minecraft Story Mode Launcher (Python)

This is a minimal GUI launcher for Minecraft Story Mode (Season 1 & Season 2).

Features (initial):
- Manual path selection for Season 1 and Season 2 executables.
- Launch button for each season.
- Simple config persistence in `launcher_config.json`.
- Optional logo images: place them in `assets/s1_logo.png` and `assets/s2_logo.png`.

How to run (Windows PowerShell):

1. Make sure you have Python 3.8+ installed and available on PATH.
2. (Optional) Install Pillow if you want extra image format support: `pip install pillow`.
3. From the project folder, run:

```powershell
python .\launcher.py
```

Notes:
- This initial version uses manual path selection. Auto-download from archive.org will be added later.
- If logos are missing the UI will still work.
- The app saves selected paths to `launcher_config.json` next to the script.
