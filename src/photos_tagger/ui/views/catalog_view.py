from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from photos_tagger.bootstrap import ApplicationContext
from photos_tagger.catalog import DuplicateSourceError, SourceNotFoundError


class CatalogView(QWidget):
    def __init__(self, context: ApplicationContext) -> None:
        super().__init__()
        self.context = context
        self.count_labels: dict[str, QLabel] = {}
        self._build_ui()
        self.refresh_view()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(16)

        intro = QLabel(
            "Katalog je vstupní bod pro správu zdrojových složek, databáze a cache miniatur. "
            "Tato verze už umí přidat root složku a skutečně naskenovat podporované fotky a videa do SQLite katalogu."
        )
        intro.setWordWrap(True)
        root_layout.addWidget(intro)

        paths_box = QGroupBox("Běhové cesty")
        paths_layout = QFormLayout(paths_box)
        paths_layout.addRow("Projekt:", QLabel(str(self.context.paths.project_root)))
        paths_layout.addRow("User data:", QLabel(str(self.context.paths.user_data_dir)))
        paths_layout.addRow("SQLite DB:", QLabel(str(self.context.paths.db_path)))
        paths_layout.addRow("Miniatury:", QLabel(str(self.context.paths.thumbnails_dir)))
        root_layout.addWidget(paths_box)

        sources_box = QGroupBox("Zdrojové složky")
        sources_layout = QVBoxLayout(sources_box)
        self.sources_list = QListWidget()
        sources_layout.addWidget(self.sources_list)

        buttons_row = QHBoxLayout()

        add_button = QPushButton("Přidat složku")
        add_button.clicked.connect(self._add_source)
        buttons_row.addWidget(add_button)

        scan_button = QPushButton("Spustit scan")
        scan_button.clicked.connect(self._scan_selected_source)
        buttons_row.addWidget(scan_button)

        refresh_button = QPushButton("Obnovit přehled")
        refresh_button.clicked.connect(self.refresh_view)
        buttons_row.addWidget(refresh_button)

        buttons_row.addStretch(1)
        sources_layout.addLayout(buttons_row)
        root_layout.addWidget(sources_box)

        counts_box = QGroupBox("Aktuální stav katalogu")
        counts_layout = QFormLayout(counts_box)
        for key in ("sources", "folders", "assets", "albums", "tags"):
            value = QLabel("0")
            self.count_labels[key] = value
            counts_layout.addRow(f"{key}:", value)
        root_layout.addWidget(counts_box)
        root_layout.addStretch(1)

    def refresh_view(self, selected_source_id: int | None = None) -> None:
        self._refresh_sources(selected_source_id)
        self._refresh_counts()

    def _refresh_sources(self, selected_source_id: int | None = None) -> None:
        self.sources_list.clear()
        sources = self.context.source_repository.list_sources()
        if not sources:
            placeholder = QListWidgetItem("Zatím nejsou přidané žádné zdroje.")
            placeholder.setFlags(Qt.ItemIsEnabled)
            self.sources_list.addItem(placeholder)
            return

        for index, source in enumerate(sources):
            item = QListWidgetItem(f"{source.name}  [{source.root_path}]")
            item.setData(Qt.UserRole, source.id)
            self.sources_list.addItem(item)
            if selected_source_id is not None and source.id == selected_source_id:
                self.sources_list.setCurrentRow(index)

        if selected_source_id is None and self.sources_list.count() > 0:
            self.sources_list.setCurrentRow(0)

    def _refresh_counts(self) -> None:
        counts = {
            "sources": self.context.source_repository.count(),
            "folders": self.context.folder_repository.count(),
            "assets": self.context.asset_repository.count(),
            "albums": self.context.album_repository.count(),
            "tags": self.context.tag_repository.count(),
        }
        for key, label in self.count_labels.items():
            label.setText(str(counts.get(key, 0)))

    def _add_source(self) -> None:
        selected_dir = QFileDialog.getExistingDirectory(self, "Vyber zdrojovou složku s fotkami")
        if not selected_dir:
            return

        try:
            source = self.context.source_repository.add_source(selected_dir)
        except DuplicateSourceError as exc:
            QMessageBox.information(self, "Zdroj už existuje", str(exc))
            return
        except ValueError as exc:
            QMessageBox.warning(self, "Neplatná složka", str(exc))
            return

        self.refresh_view(selected_source_id=source.id)
        QMessageBox.information(self, "Zdroj přidán", f"Zdroj '{source.name}' byl uložen do katalogu.")

    def _scan_selected_source(self) -> None:
        selected_source_id = self._get_selected_source_id()
        if selected_source_id is None:
            QMessageBox.information(self, "Vyber zdroj", "Nejdřív vyber zdrojovou složku, kterou chceš naskenovat.")
            return

        try:
            summary = self.context.catalog_import_service.import_source(selected_source_id)
        except SourceNotFoundError as exc:
            QMessageBox.warning(self, "Chybějící zdroj", str(exc))
            self.refresh_view()
            return
        except ValueError as exc:
            QMessageBox.warning(self, "Neplatná složka", str(exc))
            return

        self.refresh_view(selected_source_id=selected_source_id)
        QMessageBox.information(
            self,
            "Scan dokončen",
            f"Zdroj '{summary.source.name}' byl naskenován.\n\n"
            f"Složky: {summary.scanned_folder_count}\n"
            f"Assety: {summary.scanned_asset_count}",
        )

    def _get_selected_source_id(self) -> int | None:
        item = self.sources_list.currentItem()
        if item is None:
            return None
        source_id = item.data(Qt.UserRole)
        if source_id is None:
            return None
        return int(source_id)
