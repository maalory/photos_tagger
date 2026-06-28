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
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from photos_tagger.bootstrap import ApplicationContext
from photos_tagger.domain import Folder
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
            "Zdroj je korenova slozka. Scan je rekurzivni, takze po naskenovani zdroje se projdou i vsechny podslozky. "
            "Napriklad kdyz pridas slozku '2025', aplikace nacita i jeji vnorene adresare."
        )
        intro.setWordWrap(True)
        root_layout.addWidget(intro)

        paths_box = QGroupBox("Běhové cesty")
        paths_layout = QFormLayout(paths_box)
        paths_layout.addRow("Aplikace:", QLabel(str(self.context.paths.project_root)))
        paths_layout.addRow("tagy.txt:", QLabel(str(self.context.paths.tagy_path)))
        paths_layout.addRow("User data:", QLabel(str(self.context.paths.user_data_dir)))
        paths_layout.addRow("SQLite DB:", QLabel(str(self.context.paths.db_path)))
        paths_layout.addRow("Miniatury:", QLabel(str(self.context.paths.thumbnails_dir)))
        root_layout.addWidget(paths_box)

        sources_box = QGroupBox("Zdrojové složky")
        sources_layout = QVBoxLayout(sources_box)
        self.sources_list = QListWidget()
        sources_layout.addWidget(self.sources_list)
        self.sources_list.currentItemChanged.connect(self._on_source_selection_changed)

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

        folders_box = QGroupBox("Naskenovana struktura slozek")
        folders_layout = QVBoxLayout(folders_box)
        folders_help = QLabel(
            "Strom se naplni po spusteni scanu. Slouzi jako rychla kontrola, co vsechno se pod vybranym zdrojem uz importovalo."
        )
        folders_help.setWordWrap(True)
        folders_layout.addWidget(folders_help)
        self.folders_tree = QTreeWidget()
        self.folders_tree.setHeaderHidden(True)
        self.folders_tree.setRootIsDecorated(True)
        self.folders_tree.setAlternatingRowColors(True)
        folders_layout.addWidget(self.folders_tree, 1)
        root_layout.addWidget(folders_box, 1)

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
            self._show_folder_tree_message("Nejdriv pridej zdrojovou slozku.")
            return

        for index, source in enumerate(sources):
            item = QListWidgetItem(f"{source.name}  [{source.root_path}]")
            item.setData(Qt.UserRole, source.id)
            self.sources_list.addItem(item)
            if selected_source_id is not None and source.id == selected_source_id:
                self.sources_list.setCurrentRow(index)

        if selected_source_id is None and self.sources_list.count() > 0:
            self.sources_list.setCurrentRow(0)
        self._refresh_folder_tree(self._get_selected_source_id())

    def _on_source_selection_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None = None,
    ) -> None:
        source_id = None if current is None else current.data(Qt.UserRole)
        self._refresh_folder_tree(None if source_id is None else int(source_id))

    def _refresh_folder_tree(self, source_id: int | None) -> None:
        if source_id is None:
            self._show_folder_tree_message("Vyber zdroj, ktery chces zkontrolovat.")
            return

        folders = self.context.folder_repository.list_by_source(source_id)
        if not folders:
            self._show_folder_tree_message("Vybrany zdroj jeste nebyl naskenovany.")
            return

        self.folders_tree.clear()
        items_by_id: dict[int, QTreeWidgetItem] = {}
        root_items: list[QTreeWidgetItem] = []

        for folder in folders:
            item = QTreeWidgetItem([self._folder_label(folder)])
            item.setData(0, Qt.UserRole, folder.id)
            items_by_id[folder.id] = item
            if folder.parent_id is None:
                root_items.append(item)
                continue

            parent_item = items_by_id.get(int(folder.parent_id))
            if parent_item is None:
                root_items.append(item)
            else:
                parent_item.addChild(item)

        for item in root_items:
            self.folders_tree.addTopLevelItem(item)
        self.folders_tree.expandToDepth(1)

    def _show_folder_tree_message(self, message: str) -> None:
        self.folders_tree.clear()
        item = QTreeWidgetItem([message])
        item.setFlags(Qt.ItemIsEnabled)
        self.folders_tree.addTopLevelItem(item)

    @staticmethod
    def _folder_label(folder: Folder) -> str:
        if folder.relative_path == "":
            return f"{folder.folder_name} (root)"
        return folder.folder_name

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
