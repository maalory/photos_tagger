from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from photos_tagger.bootstrap import ApplicationBootstrap
from photos_tagger.ui.main_window import MainWindow



def main() -> int:
    context = ApplicationBootstrap().build_context()

    app = QApplication(sys.argv)
    app.setApplicationName("Photos Tagger")

    window = MainWindow(context)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
