# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

"""PyInstaller spec for the Student Management System desktop app.

Build from the repository root on Windows:

    pyinstaller StudentManagementSystem.spec

Output: dist/StudentManagementSystem/StudentManagementSystem.exe
(one-folder mode — chosen over onefile because it starts faster and avoids
antivirus heuristics that slow self-extracting onefile executables).

The app reads its database configuration from DB_* environment variables
or a .env file next to the exe, so no secrets are bundled.
"""

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("resources/app.qss", "resources"), ("resources/brand-icon.png", "resources")],
    hiddenimports=[
        "dotenv",
        # mysql.connector loads locale modules dynamically
        # (importlib.import_module in mysql/connector/locales/__init__.py),
        # which static analysis cannot see. Without these, any MySQL error
        # message crashes with "No localization support for language 'eng'".
        *collect_submodules("mysql.connector.locales"),
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Large standard-library modules the desktop app never uses.
        "tkinter",
        "unittest",
        "pydoc_data",
        # Not project dependencies; excluded so a broken/conflicting global
        # install (e.g. matplotlib vs numpy) can never break the build.
        "matplotlib",
        "matplotlib-inline",
        "numpy",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StudentManagementSystem",
    icon="resources/brand-icon.ico",  # exe file icon in Explorer/taskbar
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app: no terminal window
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="StudentManagementSystem",
)
