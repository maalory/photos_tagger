from __future__ import annotations

import os
from pathlib import Path
import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from photos_tagger.bootstrap import ApplicationBootstrap
from photos_tagger.ui.main_window import MainWindow


def _configure_qt_plugin_paths() -> None:
    if not getattr(sys, "frozen", False):
        return

    app_dir = Path(sys.executable).resolve().parent
    plugins_root = app_dir / "PySide6" / "plugins"
    platforms_root = plugins_root / "platforms"

    if platforms_root.exists():
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(platforms_root))
    if plugins_root.exists():
        os.environ.setdefault("QT_PLUGIN_PATH", str(plugins_root))
        QCoreApplication.addLibraryPath(str(plugins_root))


def main() -> int:
    context = ApplicationBootstrap().build_context()
    _configure_qt_plugin_paths()

    app = QApplication(sys.argv)
    app.setApplicationName("Photos Tagger")

    window = MainWindow(context)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
