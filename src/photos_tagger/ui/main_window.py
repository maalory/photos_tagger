from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QStatusBar, QTabWidget

from photos_tagger.bootstrap import ApplicationContext
from photos_tagger.ui.views.albums_view import AlbumsView
from photos_tagger.ui.views.catalog_view import CatalogView
from photos_tagger.ui.views.tagging_view import TaggingView


class MainWindow(QMainWindow):
    def __init__(self, context: ApplicationContext) -> None:
        super().__init__()
        self.context = context
        self.setWindowTitle("Photos Tagger MVP")
        self.resize(1360, 860)
        self.setMinimumSize(1100, 720)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setTabPosition(QTabWidget.North)
        tabs.addTab(CatalogView(context), "Katalog")
        tabs.addTab(TaggingView(context), "Třídění")
        tabs.addTab(AlbumsView(context), "Alba")
        self.setCentralWidget(tabs)

        status_bar = QStatusBar(self)
        status_bar.showMessage(f"SQLite katalog: {context.paths.db_path}")
        self.setStatusBar(status_bar)

        self.setUnifiedTitleAndToolBarOnMac(False)
        self.setWindowFlag(Qt.Window, True)
