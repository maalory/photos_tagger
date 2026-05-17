from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import sys


APP_NAME = "PhotosTagger"
REQUIRED_MODULES = ("PySide6", "PIL")


def _add_data_arg(source: Path, destination: str) -> str:
    return f"{source}{os.pathsep}{destination}"


def build(onefile: bool, clean: bool) -> int:
    project_root = Path(__file__).resolve().parent
    entry_script = project_root / "src" / "photos_tagger" / "main.py"
    schema_dir = project_root / "database"
    tagy_file = project_root / "tagy.txt"

    missing_paths = [path for path in (entry_script, schema_dir, tagy_file) if not path.exists()]
    if missing_paths:
        print("Build nelze spustit, chybi soubory:")
        for path in missing_paths:
            print(f"  - {path}")
        return 2

    missing_modules = [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]
    if missing_modules:
        print("Build nelze spustit, chybi Python moduly v aktivnim interpreteru:")
        for name in missing_modules:
            print(f"  - {name}")
        print("")
        print("Pouzij interpreter z runtime venv aplikace:")
        print(r"  %LOCALAPPDATA%\PhotosTagger\venv\Scripts\python.exe build_exe.py")
        print("")
        print("Nebo do aktualniho Pythonu doinstaluj zavislosti:")
        print("  python -m pip install -r requirements.txt pyinstaller")
        return 5

    try:
        from PyInstaller.__main__ import run as pyinstaller_run
    except Exception:
        print("PyInstaller neni nainstalovany.")
        print("Nainstaluj ho prikazem:")
        print("  python -m pip install pyinstaller")
        return 3

    dist_dir = project_root / "dist"
    build_dir = project_root / "build"
    if clean:
        shutil.rmtree(dist_dir, ignore_errors=True)
        shutil.rmtree(build_dir, ignore_errors=True)

    args = [
        "--noconfirm",
        "--clean",
        "--name",
        APP_NAME,
        "--windowed",
        "--paths",
        str(project_root / "src"),
        "--add-data",
        _add_data_arg(schema_dir, "database"),
        "--add-data",
        _add_data_arg(tagy_file, "."),
    ]
    args.append("--onefile" if onefile else "--onedir")
    args.append(str(entry_script))

    print("Spoustim PyInstaller:")
    print("  " + " ".join(args))
    pyinstaller_run(args)

    if onefile:
        target_path = dist_dir / f"{APP_NAME}.exe"
    else:
        target_path = dist_dir / APP_NAME / f"{APP_NAME}.exe"

    print("")
    print("Build dokonceny.")
    print(f"Vystup: {target_path}")
    if not target_path.exists():
        print("Pozor: ocekavany EXE soubor nebyl nalezen.")
        return 4
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sestavi distribucni EXE aplikace Photos Tagger pomoci PyInstaller.",
    )
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Vytvori slozku s EXE a runtime soubory misto jednoho EXE souboru.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Nesmaze pred buildem slozky dist/ a build/.",
    )
    args = parser.parse_args()
    return build(onefile=not args.onedir, clean=not args.no_clean)


if __name__ == "__main__":
    raise SystemExit(main())
