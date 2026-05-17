from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from photos_tagger.bootstrap import ApplicationContext
from photos_tagger.domain import Asset, Folder, MediaType
from photos_tagger.tagging import SHORTCUT_KEYS, ShortcutBinding, TaggingActionResult, TaggingUndoAction
from photos_tagger.ui.dialogs import FolderTagEditorDialog, ShortcutEditorDialog


class TaggingView(QWidget):
    def __init__(self, context: ApplicationContext) -> None:
        super().__init__()
        self.context = context
        self.setFocusPolicy(Qt.StrongFocus)

        self.sources_by_id: dict[int, object] = {}
        self.folders_by_id: dict[int, Folder] = {}
        self.assets_by_id: dict[int, Asset] = {}
        self.shortcut_bindings: dict[str, ShortcutBinding] = {}
        self.undo_stack: list[TaggingUndoAction] = []
        self._current_pixmap: QPixmap | None = None

        self.action_log = QListWidget()
        self.source_combo = QComboBox()
        self.folder_list = QListWidget()
        self.asset_list = QListWidget()
        self.shortcut_list = QListWidget()
        self.direct_tags_list = QListWidget()
        self.effective_tags_list = QListWidget()

        self.preview_title = QLabel("Neni vybrany asset")
        self.preview_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(420)
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("background: #f3f4f6; border: 1px solid #d0d7de; padding: 16px;")
        self.preview_path = QLabel("-")
        self.preview_path.setWordWrap(True)

        self.metadata_labels = {
            "captured_at": QLabel("-"),
            "captured_source": QLabel("-"),
            "gps": QLabel("-"),
            "event": QLabel("-"),
            "resolution": QLabel("-"),
            "file_size": QLabel("-"),
            "flags": QLabel("-"),
        }

        self.folder_tag_button = QPushButton("Tagovat slozku")
        self.folder_tag_button.clicked.connect(self._open_folder_tag_editor)
        self.folder_tag_button.setEnabled(False)

        self._build_ui()
        self._register_shortcuts()
        self.refresh_view()

    def refresh_view(self) -> None:
        self._refresh_shortcuts()
        self._refresh_sources()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._render_preview_pixmap()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(16)

        intro = QLabel(
            "Trideni uz pracuje nad realnymi assety v databazi. Vyber slozku, otevri fotku a pouzij klavesy 1..0, F, X, sipky nebo U. Tagy slozky lze upravovat tlacitkem pod seznamem slozek."
        )
        intro.setWordWrap(True)
        root_layout.addWidget(intro)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        source_box = QGroupBox("Zdroj")
        source_layout = QVBoxLayout(source_box)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_combo, 1)
        refresh_button = QPushButton("Obnovit")
        refresh_button.clicked.connect(self.refresh_view)
        source_row.addWidget(refresh_button)
        source_layout.addLayout(source_row)
        left_layout.addWidget(source_box)

        folders_box = QGroupBox("Slozky")
        folders_layout = QVBoxLayout(folders_box)
        folders_layout.addWidget(self.folder_list)
        folders_layout.addWidget(self.folder_tag_button)
        left_layout.addWidget(folders_box, 1)

        assets_box = QGroupBox("Assety")
        assets_layout = QVBoxLayout(assets_box)
        assets_layout.addWidget(self.asset_list)
        left_layout.addWidget(assets_box, 1)

        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(12)

        preview_box = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.preview_label, 1)
        preview_layout.addWidget(self.preview_path)
        center_layout.addWidget(preview_box, 1)

        log_box = QGroupBox("Posledni akce")
        log_layout = QVBoxLayout(log_box)
        log_layout.addWidget(self.action_log)
        center_layout.addWidget(log_box)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        metadata_box = QGroupBox("Metadata")
        metadata_layout = QFormLayout(metadata_box)
        metadata_layout.addRow("Datum:", self.metadata_labels["captured_at"])
        metadata_layout.addRow("Zdroj data:", self.metadata_labels["captured_source"])
        metadata_layout.addRow("GPS:", self.metadata_labels["gps"])
        metadata_layout.addRow("Event:", self.metadata_labels["event"])
        metadata_layout.addRow("Rozliseni:", self.metadata_labels["resolution"])
        metadata_layout.addRow("Velikost:", self.metadata_labels["file_size"])
        metadata_layout.addRow("Priznaky:", self.metadata_labels["flags"])
        right_layout.addWidget(metadata_box)

        shortcuts_box = QGroupBox("Rychle tagy")
        shortcuts_layout = QVBoxLayout(shortcuts_box)
        manage_shortcuts_button = QPushButton("Nastavit rychle tagy")
        manage_shortcuts_button.clicked.connect(self._open_shortcut_editor)
        shortcuts_layout.addWidget(manage_shortcuts_button)
        shortcuts_help = QLabel("Dvojklik na seznam nebo tlacitko upravi vazby 1..0. F = favorite, X = reject, U = undo.")
        shortcuts_help.setWordWrap(True)
        shortcuts_layout.addWidget(shortcuts_help)
        shortcuts_layout.addWidget(self.shortcut_list)
        right_layout.addWidget(shortcuts_box)

        direct_tags_box = QGroupBox("Prime tagy")
        direct_tags_layout = QVBoxLayout(direct_tags_box)
        direct_help = QLabel("Dvojklik na prime tagy je odebere z aktualni fotky.")
        direct_help.setWordWrap(True)
        direct_tags_layout.addWidget(direct_help)
        direct_tags_layout.addWidget(self.direct_tags_list)
        right_layout.addWidget(direct_tags_box, 1)

        effective_tags_box = QGroupBox("Efektivni tagy")
        effective_tags_layout = QVBoxLayout(effective_tags_box)
        effective_help = QLabel("Zobrazuji se zde prime tagy assetu i tagy zdedene ze slozky a eventu.")
        effective_help.setWordWrap(True)
        effective_tags_layout.addWidget(effective_help)
        effective_tags_layout.addWidget(self.effective_tags_list)
        right_layout.addWidget(effective_tags_box, 1)

        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([280, 620, 320])

        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.folder_list.currentItemChanged.connect(self._on_folder_changed)
        self.asset_list.currentItemChanged.connect(self._on_asset_changed)
        self.shortcut_list.itemDoubleClicked.connect(self._open_shortcut_editor)
        self.direct_tags_list.itemDoubleClicked.connect(self._remove_direct_tag)

        self._show_preview_message("Vyber slozku a asset v levem panelu.")
        self._append_log("Tagging screen je pripraveny.")

    def _register_shortcuts(self) -> None:
        for key_sequence in SHORTCUT_KEYS:
            shortcut = QShortcut(QKeySequence(key_sequence), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda value=key_sequence: self._handle_quick_tag(value))

        command_map = {
            "F": self._handle_favorite,
            "X": self._handle_reject,
            "Space": lambda: self._move_asset_selection(1),
            "Right": lambda: self._move_asset_selection(1),
            "Left": lambda: self._move_asset_selection(-1),
            "U": self._handle_undo,
        }
        for key_sequence, callback in command_map.items():
            shortcut = QShortcut(QKeySequence(key_sequence), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)

    def _refresh_sources(self, selected_source_id: int | None = None) -> None:
        sources = self.context.source_repository.list_sources()
        self.sources_by_id = {source.id: source for source in sources}

        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        if not sources:
            self.source_combo.addItem("Nejsou zadne zdroje", None)
            self.source_combo.blockSignals(False)
            self._clear_folders()
            self._clear_assets()
            self._update_asset_detail(None)
            self._update_folder_controls()
            return

        target_index = 0
        for index, source in enumerate(sources):
            self.source_combo.addItem(source.name, source.id)
            if selected_source_id is not None and source.id == selected_source_id:
                target_index = index

        self.source_combo.setCurrentIndex(target_index)
        self.source_combo.blockSignals(False)
        self._load_folders(self._selected_source_id())

    def _refresh_shortcuts(self) -> None:
        bindings = self.context.tagging_service.list_shortcut_bindings()
        self.shortcut_bindings = {binding.key_sequence: binding for binding in bindings}
        self.shortcut_list.clear()
        for key_sequence in SHORTCUT_KEYS:
            binding = self.shortcut_bindings[key_sequence]
            item = QListWidgetItem(self._format_shortcut_text(binding))
            item.setData(Qt.UserRole, key_sequence)
            self.shortcut_list.addItem(item)

    def _on_source_changed(self, *_args) -> None:
        self._load_folders(self._selected_source_id())

    def _load_folders(self, source_id: int | None, selected_folder_id: int | None = None) -> None:
        self.folder_list.blockSignals(True)
        self.folder_list.clear()
        self.folders_by_id.clear()

        if source_id is None:
            self.folder_list.blockSignals(False)
            self._clear_assets()
            self._update_asset_detail(None)
            self._update_folder_controls()
            return

        folders = self.context.folder_repository.list_by_source(source_id)
        self.folders_by_id = {folder.id: folder for folder in folders}

        target_row = 0
        for index, folder in enumerate(folders):
            label = folder.relative_path or "."
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, folder.id)
            self.folder_list.addItem(item)
            if selected_folder_id is not None and folder.id == selected_folder_id:
                target_row = index

        self.folder_list.blockSignals(False)
        if folders:
            self.folder_list.setCurrentRow(target_row)
            self._load_assets(folders[target_row].id)
        else:
            self._clear_assets()
            self._update_asset_detail(None)
        self._update_folder_controls()

    def _on_folder_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None = None) -> None:
        folder_id = None if current is None else current.data(Qt.UserRole)
        self._load_assets(int(folder_id)) if folder_id is not None else self._clear_assets()
        if folder_id is None:
            self._update_asset_detail(None)
        self._update_folder_controls()

    def _load_assets(self, folder_id: int, selected_asset_id: int | None = None) -> None:
        assets = self.context.asset_repository.list_by_folder(folder_id)
        self.assets_by_id = {asset.id: asset for asset in assets}

        self.asset_list.blockSignals(True)
        self.asset_list.clear()
        target_row = 0
        for index, asset in enumerate(assets):
            item = QListWidgetItem(self._format_asset_text(asset))
            item.setData(Qt.UserRole, asset.id)
            self.asset_list.addItem(item)
            if selected_asset_id is not None and asset.id == selected_asset_id:
                target_row = index

        self.asset_list.blockSignals(False)
        if assets:
            self.asset_list.setCurrentRow(target_row)
            self._update_asset_detail(self.context.asset_repository.get_by_id(assets[target_row].id))
            return

        self._update_asset_detail(None)

    def _clear_folders(self) -> None:
        self.folder_list.clear()
        self.folders_by_id.clear()

    def _clear_assets(self) -> None:
        self.asset_list.clear()
        self.assets_by_id.clear()

    def _on_asset_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None = None) -> None:
        asset_id = None if current is None else current.data(Qt.UserRole)
        asset = None if asset_id is None else self.context.asset_repository.get_by_id(int(asset_id))
        self._update_asset_detail(asset)

    def _update_asset_detail(self, asset: Asset | None) -> None:
        self.direct_tags_list.clear()
        self.effective_tags_list.clear()

        if asset is None:
            self.preview_title.setText("Neni vybrany asset")
            self.preview_path.setText("-")
            self._show_preview_message("Vyber asset v levem panelu.")
            for label in self.metadata_labels.values():
                label.setText("-")
            return

        metadata = self.context.metadata_repository.get_by_asset_id(asset.id)
        tag_state = self.context.tagging_service.get_asset_tag_state(asset.id)

        self.preview_title.setText(asset.file_name)
        self.preview_path.setText(asset.relative_path)
        self.metadata_labels["captured_at"].setText(_format_datetime(asset.captured_at))
        self.metadata_labels["captured_source"].setText(asset.captured_at_source.value)
        self.metadata_labels["gps"].setText(_format_gps(metadata.gps_lat if metadata else None, metadata.gps_lng if metadata else None))
        self.metadata_labels["event"].setText(f"#{asset.event_id}" if asset.event_id is not None else "-")
        self.metadata_labels["resolution"].setText(_format_resolution(asset.width, asset.height))
        self.metadata_labels["file_size"].setText(_format_file_size(asset.file_size))
        self.metadata_labels["flags"].setText(_format_flags(asset.is_favorite, asset.is_rejected))

        for tag in tag_state.direct_tags:
            item = QListWidgetItem(tag.name)
            item.setData(Qt.UserRole, tag.id)
            self.direct_tags_list.addItem(item)
        if not tag_state.direct_tags:
            placeholder = QListWidgetItem("Zatim zadne prime tagy")
            placeholder.setFlags(Qt.ItemIsEnabled)
            self.direct_tags_list.addItem(placeholder)

        for tag in tag_state.effective_tags:
            self.effective_tags_list.addItem(f"{tag.scope.value}: {tag.tag_name}")
        if not tag_state.effective_tags:
            placeholder = QListWidgetItem("Zatim zadne efektivni tagy")
            placeholder.setFlags(Qt.ItemIsEnabled)
            self.effective_tags_list.addItem(placeholder)

        self._load_preview(asset)

    def _load_preview(self, asset: Asset) -> None:
        if asset.media_type != MediaType.PHOTO:
            self._show_preview_message("Preview videi zatim neni implementovany. Asset lze ale tagovat a oznacovat.")
            return

        pixmap = QPixmap(asset.absolute_path)
        if pixmap.isNull():
            self._show_preview_message("Soubor se nepodarilo zobrazit jako obrazek. Tagovani ale funguje dal.")
            return

        self._current_pixmap = pixmap
        self._render_preview_pixmap()

    def _show_preview_message(self, message: str) -> None:
        self._current_pixmap = None
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText(message)

    def _render_preview_pixmap(self) -> None:
        if self._current_pixmap is None:
            return
        scaled = self._current_pixmap.scaled(
            self.preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_label.setText("")
        self.preview_label.setPixmap(scaled)

    def _open_shortcut_editor(self, *_args) -> None:
        dialog = ShortcutEditorDialog(self.context.tagging_service.list_shortcut_bindings(), self)
        if dialog.exec() == 0:
            return

        self.context.tagging_service.save_shortcut_bindings(dialog.values())
        self._refresh_shortcuts()
        self._append_log("Rychle tagy byly ulozeny.")

    def _open_folder_tag_editor(self) -> None:
        folder = self._current_folder()
        if folder is None:
            QMessageBox.information(self, "Tagy slozky", "Nejdriv vyber slozku, kterou chces hromadne otagovat.")
            return

        current_tags = [tag.name for tag in self.context.tagging_service.list_folder_tags(folder.id)]
        folder_label = folder.relative_path or "."
        dialog = FolderTagEditorDialog(folder_label=folder_label, current_tags=current_tags, parent=self)
        if dialog.exec() == 0:
            return

        result = self.context.tagging_service.save_folder_tags(folder.id, dialog.values())
        self._append_log(result.message)
        self._refresh_current_folder(folder.id)

    def _handle_quick_tag(self, key_sequence: str) -> None:
        asset = self._current_asset()
        if asset is None:
            self._append_log("Neni vybrany zadny asset.")
            return

        try:
            result = self.context.tagging_service.toggle_shortcut_tag(asset.id, key_sequence)
        except ValueError as exc:
            QMessageBox.information(self, "Rychly tag", str(exc))
            self._append_log(str(exc))
            return

        self._consume_action_result(result, asset.id)

    def _remove_direct_tag(self, item: QListWidgetItem) -> None:
        asset = self._current_asset()
        if asset is None:
            return

        tag_id = item.data(Qt.UserRole)
        if tag_id is None:
            return

        result = self.context.tagging_service.set_tag_assignment(
            asset_id=asset.id,
            tag_id=int(tag_id),
            is_assigned=False,
            assigned_via="manual",
        )
        self._consume_action_result(result, asset.id)

    def _handle_favorite(self) -> None:
        asset = self._current_asset()
        if asset is None:
            self._append_log("Neni vybrany zadny asset.")
            return
        result = self.context.tagging_service.toggle_favorite(asset.id)
        self._consume_action_result(result, asset.id)

    def _handle_reject(self) -> None:
        asset = self._current_asset()
        if asset is None:
            self._append_log("Neni vybrany zadny asset.")
            return
        result = self.context.tagging_service.toggle_rejected(asset.id)
        self._consume_action_result(result, asset.id)

    def _handle_undo(self) -> None:
        if not self.undo_stack:
            self._append_log("Neni co vratit.")
            return

        action = self.undo_stack.pop()
        result = self.context.tagging_service.undo(action)
        self._append_log(f"Undo: {result.message}")
        self._refresh_current_asset(action.asset_id)

    def _move_asset_selection(self, offset: int) -> None:
        if self.asset_list.count() == 0:
            self._append_log("Ve slozce nejsou zadne assety.")
            return

        current_row = self.asset_list.currentRow()
        if current_row < 0:
            target_row = 0
        else:
            target_row = max(0, min(self.asset_list.count() - 1, current_row + offset))
        self.asset_list.setCurrentRow(target_row)

    def _consume_action_result(self, result: TaggingActionResult, asset_id: int) -> None:
        if result.undo_action is not None:
            self.undo_stack.append(result.undo_action)
        self._append_log(result.message)
        self._refresh_current_asset(asset_id)

    def _refresh_current_asset(self, asset_id: int) -> None:
        folder_id = self._selected_folder_id()
        if folder_id is None:
            asset = self.context.asset_repository.get_by_id(asset_id)
            self._update_asset_detail(asset)
            return
        self._load_assets(folder_id, selected_asset_id=asset_id)

    def _refresh_current_folder(self, folder_id: int) -> None:
        current_asset = self._current_asset()
        current_asset_id = current_asset.id if current_asset is not None else None
        self._load_assets(folder_id, selected_asset_id=current_asset_id)
        self._update_folder_controls()

    def _current_asset(self) -> Asset | None:
        item = self.asset_list.currentItem()
        if item is None:
            return None
        asset_id = item.data(Qt.UserRole)
        if asset_id is None:
            return None
        return self.context.asset_repository.get_by_id(int(asset_id))

    def _current_folder(self) -> Folder | None:
        folder_id = self._selected_folder_id()
        if folder_id is None:
            return None
        return self.folders_by_id.get(folder_id)

    def _selected_source_id(self) -> int | None:
        source_id = self.source_combo.currentData()
        if source_id is None:
            return None
        return int(source_id)

    def _selected_folder_id(self) -> int | None:
        item = self.folder_list.currentItem()
        if item is None:
            return None
        folder_id = item.data(Qt.UserRole)
        if folder_id is None:
            return None
        return int(folder_id)

    def _update_folder_controls(self) -> None:
        self.folder_tag_button.setEnabled(self._selected_folder_id() is not None)

    def _append_log(self, message: str) -> None:
        self.action_log.insertItem(0, message)
        while self.action_log.count() > 50:
            self.action_log.takeItem(self.action_log.count() - 1)

    @staticmethod
    def _format_shortcut_text(binding: ShortcutBinding) -> str:
        if binding.tag_name:
            return f"{binding.key_sequence} -> {binding.tag_name}"
        return f"{binding.key_sequence} -> (neni prirazeno)"

    @staticmethod
    def _format_asset_text(asset: Asset) -> str:
        prefixes = []
        if asset.is_favorite:
            prefixes.append("[fav]")
        if asset.is_rejected:
            prefixes.append("[rej]")
        prefix = " ".join(prefixes)
        text = asset.file_name
        if asset.captured_at:
            text = f"{text}  [{_format_datetime(asset.captured_at)}]"
        if prefix:
            return f"{prefix} {text}"
        return text


def _format_datetime(value: str | None) -> str:
    if not value:
        return "-"
    return value.replace("T", " ")


def _format_gps(lat: float | None, lng: float | None) -> str:
    if lat is None or lng is None:
        return "-"
    return f"{lat:.6f}, {lng:.6f}"


def _format_resolution(width: int | None, height: int | None) -> str:
    if width is None or height is None:
        return "-"
    return f"{width} x {height}"


def _format_file_size(file_size: int | None) -> str:
    if file_size is None:
        return "-"
    size = float(file_size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or unit == "GB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{int(file_size)} B"


def _format_flags(is_favorite: bool, is_rejected: bool) -> str:
    flags = []
    if is_favorite:
        flags.append("favorite")
    if is_rejected:
        flags.append("reject")
    return ", ".join(flags) if flags else "-"
