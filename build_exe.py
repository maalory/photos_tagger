from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys


APP_NAME = "PhotosTagger"
REQUIRED_MODULES = ("PyInstaller", "PySide6", "PIL")
PREFERRED_WINDOWS_PYTHON = (3, 11)
BOOTSTRAP_ENV_VAR = "PHOTOS_TAGGER_EXE_BUILD_BOOTSTRAPPED"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)


def _add_data_arg(source: Path, destination: str) -> str:
    return f"{source}{os.pathsep}{destination}"


def _format_version(version: tuple[int, int]) -> str:
    return f"{version[0]}.{version[1]}"


def _find_python_launcher(version: tuple[int, int]) -> Path | None:
    if os.name != "nt":
        return None

    try:
        completed = subprocess.run(
            ["py", f"-{_format_version(version)}", "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None

    if completed.returncode != 0:
        return None

    executable = completed.stdout.strip()
    if not executable:
        return None
    return Path(executable)


def _interpreter_has_modules(python_bin: Path, module_names: tuple[str, ...]) -> bool:
    code = (
        "import importlib.util, sys; "
        f"missing=[name for name in {module_names!r} if importlib.util.find_spec(name) is None]; "
        "sys.exit(0 if not missing else 1)"
    )
    completed = subprocess.run(
        [str(python_bin), "-c", code],
        capture_output=True,
        check=False,
        text=True,
    )
    return completed.returncode == 0


def _current_interpreter_has_modules(module_names: tuple[str, ...]) -> bool:
    return all(importlib.util.find_spec(name) is not None for name in module_names)


def _get_build_venv_dir() -> Path:
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / APP_NAME / "build-venv-py311"
    return Path.home() / ".photos_tagger" / "build-venv-py311"


def _get_runtime_venv_python() -> Path | None:
    local_appdata = os.getenv("LOCALAPPDATA")
    if not local_appdata:
        return None

    runtime_python = Path(local_appdata) / APP_NAME / "venv" / "Scripts" / "python.exe"
    if runtime_python.exists():
        return runtime_python
    return None


def _get_venv_python(venv_dir: Path) -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    python_name = "python.exe" if os.name == "nt" else "python"
    return venv_dir / scripts_dir / python_name


def _ensure_build_venv(project_root: Path, base_python: Path) -> Path | None:
    venv_dir = _get_build_venv_dir()
    venv_python = _get_venv_python(venv_dir)

    if not venv_python.exists():
        print(f"Vytvarim build virtualni prostredi: {venv_dir}")
        created = subprocess.run(
            [str(base_python), "-m", "venv", str(venv_dir)],
            check=False,
            cwd=project_root,
        )
        if created.returncode != 0:
            print("Nepodarilo se vytvorit build virtualni prostredi pro EXE.")
            return None

    if _interpreter_has_modules(venv_python, REQUIRED_MODULES):
        return venv_python

    print("Doinstaluji build zavislosti do build virtualniho prostredi...")
    install = subprocess.run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "-r",
            str(project_root / "requirements.txt"),
            "pyinstaller",
        ],
        check=False,
        cwd=project_root,
    )
    if install.returncode != 0:
        print("Instalace build zavislosti selhala.")
        return None

    if not _interpreter_has_modules(venv_python, REQUIRED_MODULES):
        print("Build virtualni prostredi stale neobsahuje vsechny potrebne moduly.")
        return None
    return venv_python


def _maybe_reexec_in_preferred_windows_python(project_root: Path) -> int | None:
    if os.name != "nt":
        return None
    if os.environ.get(BOOTSTRAP_ENV_VAR) == "1":
        return None

    current_version = sys.version_info[:2]
    current_has_modules = _current_interpreter_has_modules(REQUIRED_MODULES)
    preferred_python = _find_python_launcher(PREFERRED_WINDOWS_PYTHON)
    runtime_python = _get_runtime_venv_python()

    if current_version == PREFERRED_WINDOWS_PYTHON and current_has_modules:
        return None

    fallback_python: Path | None = None
    if runtime_python is not None and _interpreter_has_modules(runtime_python, REQUIRED_MODULES):
        fallback_python = runtime_python
    elif current_has_modules:
        fallback_python = Path(sys.executable)

    if preferred_python is None:
        if current_version != PREFERRED_WINDOWS_PYTHON:
            print(
                "Python 3.11 nebyl nalezen. "
                f"Pokracuji s aktualnim interpreterem {sys.version.split()[0]}."
            )
        if fallback_python is not None and fallback_python != Path(sys.executable):
            print(f"Pouzivam fallback build interpreter: {fallback_python}")
            env = os.environ.copy()
            env[BOOTSTRAP_ENV_VAR] = "1"
            completed = subprocess.run(
                [str(fallback_python), str(Path(__file__).resolve()), *sys.argv[1:]],
                check=False,
                cwd=project_root,
                env=env,
            )
            return completed.returncode
        return None

    build_python = _ensure_build_venv(project_root, preferred_python)
    if build_python is None:
        if fallback_python is None:
            return 6
        print(
            "Nepodarilo se pripravit Python 3.11 build env. "
            f"Pouzivam fallback interpreter: {fallback_python}"
        )
        env = os.environ.copy()
        env[BOOTSTRAP_ENV_VAR] = "1"
        completed = subprocess.run(
            [str(fallback_python), str(Path(__file__).resolve()), *sys.argv[1:]],
            check=False,
            cwd=project_root,
            env=env,
        )
        return completed.returncode

    print(f"Pro Windows EXE build pouzivam Python {_format_version(PREFERRED_WINDOWS_PYTHON)}: {build_python}")
    env = os.environ.copy()
    env[BOOTSTRAP_ENV_VAR] = "1"
    completed = subprocess.run(
        [str(build_python), str(Path(__file__).resolve()), *sys.argv[1:]],
        check=False,
        cwd=project_root,
        env=env,
    )
    return completed.returncode


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
        print("Doporucena cesta pro Windows 10 build:")
        print("  py -3.11 build_exe.py")
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
    build_dir.mkdir(parents=True, exist_ok=True)

    args = [
        "--noconfirm",
        "--clean",
        "--name",
        APP_NAME,
        "--windowed",
        "--noupx",
        "--specpath",
        str(build_dir),
        "--paths",
        str(project_root / "src"),
        "--add-data",
        _add_data_arg(schema_dir, "database"),
        "--add-data",
        _add_data_arg(tagy_file, "."),
    ]
    if onefile:
        args.append("--onefile")
    else:
        args.extend(["--onedir", "--contents-directory", "."])
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
    project_root = Path(__file__).resolve().parent
    bootstrap_result = _maybe_reexec_in_preferred_windows_python(project_root)
    if bootstrap_result is not None:
        return bootstrap_result

    parser = argparse.ArgumentParser(
        description="Sestavi distribucni EXE aplikace Photos Tagger pomoci PyInstaller.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--onefile",
        action="store_true",
        help="Vytvori jeden EXE soubor. Pro starsi Windows 10 je stabilnejsi vychozi onedir varianta.",
    )
    mode_group.add_argument(
        "--onedir",
        action="store_true",
        help="Vytvori slozku s EXE a runtime soubory. Toto je vychozi a doporucena varianta.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Nesmaze pred buildem slozky dist/ a build/.",
    )
    args = parser.parse_args()
    return build(onefile=args.onefile, clean=not args.no_clean)


if __name__ == "__main__":
    raise SystemExit(main())
