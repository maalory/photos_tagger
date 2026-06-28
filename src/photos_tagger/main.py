from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys


_DLL_DIRECTORY_HANDLES: list[object] = []
_QT_PATHS: tuple[Path, Path, Path] | None = None


def _resolve_qt_paths() -> tuple[Path, Path, Path] | None:
    global _QT_PATHS

    if _QT_PATHS is not None:
        return _QT_PATHS

    if getattr(sys, "frozen", False):
        pyside_root = Path(sys.executable).resolve().parent / "PySide6"
    else:
        spec = importlib.util.find_spec("PySide6")
        if spec is None or spec.origin is None:
            return None
        pyside_root = Path(spec.origin).resolve().parent

    plugins_root = pyside_root / "plugins"
    platforms_root = plugins_root / "platforms"
    _QT_PATHS = (pyside_root, plugins_root, platforms_root)
    return _QT_PATHS


def _add_windows_dll_directory(path: Path) -> None:
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return
    if not path.exists():
        return
    _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(path)))


def _configure_qt_environment() -> None:
    qt_paths = _resolve_qt_paths()
    if qt_paths is None:
        return

    pyside_root, plugins_root, platforms_root = qt_paths
    shiboken_spec = importlib.util.find_spec("shiboken6")
    shiboken_root = (
        Path(shiboken_spec.origin).resolve().parent
        if shiboken_spec is not None and shiboken_spec.origin is not None
        else None
    )

    _add_windows_dll_directory(pyside_root)
    if shiboken_root is not None:
        _add_windows_dll_directory(shiboken_root)

    if platforms_root.exists():
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platforms_root)
    if plugins_root.exists():
        os.environ["QT_PLUGIN_PATH"] = str(plugins_root)


_configure_qt_environment()

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from photos_tagger.bootstrap import ApplicationBootstrap
from photos_tagger.ui.main_window import MainWindow


def _register_qt_library_paths() -> None:
    qt_paths = _resolve_qt_paths()
    if qt_paths is None:
        return

    _pyside_root, plugins_root, _platforms_root = qt_paths
    if not plugins_root.exists():
        return

    paths = [str(plugins_root), *QCoreApplication.libraryPaths()]
    deduplicated_paths: list[str] = []
    for path in paths:
        if path and path not in deduplicated_paths:
            deduplicated_paths.append(path)
    QCoreApplication.setLibraryPaths(deduplicated_paths)


def main() -> int:
    _register_qt_library_paths()
    context = ApplicationBootstrap().build_context()

    app = QApplication(sys.argv)
    app.setApplicationName("Photos Tagger")

    window = MainWindow(context)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
