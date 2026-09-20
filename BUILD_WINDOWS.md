# Build the Windows desktop executable

This document explains how to produce `StudentManagementSystem.exe` — a
standalone Windows build of the PyQt6 desktop application — and how to
package it as a single-file installer (`StudentManagementSystem-Setup.exe`)
that installs like normal Windows software, with Start Menu shortcuts and
an uninstaller.

## What the executable does

- Packs the desktop app (`main.py`, services, repositories, dialogs, tabs)
  together with the `resources/app.qss` stylesheet.
- Does **not** bundle any credentials. On startup the app reads `DB_HOST`,
  `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` from environment variables,
  or from a `.env` file placed in the same folder as the exe.
- Connects directly to MySQL (the same database the API and web app use).
- Writes its log file to `%LOCALAPPDATA%\StudentManagementSystem\` so it
  stays writable even when the exe is installed in `Program Files`.

## Requirements

- Windows 10 or 11
- Python 3.11 or 3.12 (64-bit) — same version used in CI
- A reachable MySQL server (local, Docker, or remote)

## Build steps

From the repository root in PowerShell:

```powershell
# 1. Create and activate a build environment (once)
python -m venv .venv
.venv\Scripts\activate

# 2. Install application and build dependencies
pip install -r requirements.txt
pip install pyinstaller

# 3. Build
pyinstaller StudentManagementSystem.spec --noconfirm
```

Alternatively, run the one-step helper:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

## Output

```
dist\StudentManagementSystem\StudentManagementSystem.exe
```

The whole `dist\StudentManagementSystem\` folder is the application —
copy it anywhere; the exe does not depend on the source directory.
(One-folder mode is used instead of onefile because it starts faster and
avoids antivirus false-positive delays on self-extracting executables.)

## Running it

1. Make sure MySQL is running and the schema exists
   (`docker compose up -d` locally, or your own server).
2. Either set `DB_*` environment variables, or place a `.env` file
   (copy of `.env.example`, filled in) next to the exe.
3. Double-click `StudentManagementSystem.exe` and sign in with an active
   user account (create one with `python scripts\create_user.py`).

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Connect to MySQL" setup dialog appears | The app could not reach MySQL. Enter the correct server details; they are saved to a `.env` next to the exe for future runs. |
| "Database Connection Failed" dialog | MySQL not running, wrong `DB_*` values, or the schema was never created. |
| Exe flashes and closes | Run it from a terminal to see the error; check the log in `%LOCALAPPDATA%\StudentManagementSystem\`. |
| Missing stylesheet (unstyled windows) | Build from the repository root so the spec can find `resources/app.qss`. |
| Antivirus flags the exe | One-folder builds rarely trigger this; add an exclusion if needed. |

## Build the single-file installer (recommended for sharing)

Requires [Inno Setup](https://jrsoftware.org/isinfo.php) 6 or 7 (free):

```powershell
# 1. Build the app
pyinstaller StudentManagementSystem.spec --noconfirm

# 2. Compile the installer (adjust path if Inno Setup 6)
& "C:\Program Files\Inno Setup 7\ISCC.exe" installer.iss
```

Output: `output\StudentManagementSystem-Setup.exe` — a single file (~50 MB)
you can send to anyone. The person installing it gets:

- a normal install wizard (choose per-user or all-users install)
- a Start Menu shortcut, optional desktop shortcut
- a proper uninstaller (Windows Settings → Apps)
- on first launch, a friendly "Connect to MySQL" dialog if the database is
  not yet configured — no manual `.env` editing needed

**What the recipient still needs:** a reachable MySQL server that has the
schema loaded (e.g. your machine exposed on the network, or their own
`docker compose up -d` from this repository). The app is ready to use once
the setup dialog points at a valid database and a user account exists
(create one with `python scripts\create_user.py`).

## Continuous Integration

`.github/workflows/windows-build.yml` builds the exe on every push to
`main` using a Windows runner, so the artifact can be downloaded from the
Actions tab without installing anything locally.
