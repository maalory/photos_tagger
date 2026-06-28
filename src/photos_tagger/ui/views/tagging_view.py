from __future__ import annotations

from string import ascii_uppercase
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from photos_tagger.bootstrap import ApplicationContext
from photos_tagger.domain import Asset, Folder, MediaType
from photos_tagger.tagging import (
    SHORTCUT_KEYS,
    ShortcutBinding,
    TaggingActionResult,
    TaggingUndoAction,
    TagyShortcuts,
    load_tagy_shortcuts,
)
from photos_tagger.ui.dialogs import FolderTagEditorDialog, ShortcutEditorDialog, TimeTagEditorDialog


SUBCATEGORY_DIGITS = set(SHORTCUT_KEYS)


class FullscreenPreviewDialog(QDialog):
    def __init__(
        self,
        get_current_asset: Callable[[], Asset | None],
        move_selection: Callable[[int], None],
        handle_tag_shortcut: Callable[[int, Qt.KeyboardModifiers], bool],
        get_current_tags_text: Callable[[Asset], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_current_asset = get_current_asset
        self._move_selection = move_selection
        self._handle_tag_shortcut = handle_tag_shortcut
        self._get_current_tags_text = get_current_tags_text
        self._preview_mode = "fit"
        self._current_pixmap: QPixmap | None = None
        self._tags_overlay_visible = False

        self.setWindowTitle("Fullscreen preview")
        self.setWindowFlag(Qt.Window, True)

        self.preview_title = QLabel("Neni vybrany asset")
        self.preview_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.preview_path = QLabel("-")
        self.preview_path.setWordWrap(True)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("background: #111827; color: #e5e7eb; border: 1px solid #374151; padding: 16px;")

        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidget(self.preview_label)
        self.preview_scroll.setWidgetResizable(True)

        self.tags_overlay_label = QLabel(self.preview_scroll.viewport())
        self.tags_overlay_label.setWordWrap(True)
        self.tags_overlay_label.setStyleSheet(
            "background: #ffffff; color: #000000; border: 1px solid #111111; padding: 6px;"
        )
        self.tags_overlay_label.hide()

        self.fit_button = QPushButton("Prizpusobit")
        self.fit_button.setCheckable(True)
        self.fit_button.setChecked(True)
        self.fit_button.clicked.connect(lambda: self.set_preview_mode("fit"))

        self.original_button = QPushButton("1:1")
        self.original_button.setCheckable(True)
        self.original_button.clicked.connect(lambda: self.set_preview_mode("original"))

        close_button = QPushButton("Zavrit")
        close_button.clicked.connect(self.close)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.fit_button)
        controls_layout.addWidget(self.original_button)
        controls_layout.addStretch(1)
        controls_layout.addWidget(close_button)

        hint_label = QLabel(
            "Sipky/Space = dalsi nebo predchozi fotka, Ctrl+pismeno/1..0 = tagovani, ? = zobrazit tagy, Esc = zavrit."
        )
        hint_label.setWordWrap(True)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)
        root_layout.addWidget(self.preview_title)
        root_layout.addWidget(self.preview_path)
        root_layout.addLayout(controls_layout)
        root_layout.addWidget(hint_label)
        root_layout.addWidget(self.preview_scroll, 1)
        self._register_shortcuts()

    def open_for_current_asset(self) -> None:
        self.sync_with_current_asset()
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def sync_with_current_asset(self) -> None:
        asset = self._get_current_asset()
        if asset is None:
            self.preview_title.setText("Neni vybrany asset")
            self.preview_path.setText("-")
            self._show_message("Vyber asset v levem panelu.")
            self._refresh_tags_overlay(None)
            return

        self.preview_title.setText(asset.file_name)
        self.preview_path.setText(asset.relative_path)

        if asset.media_type != MediaType.PHOTO:
            self._show_message("Preview videi zatim neni implementovany.")
            self._refresh_tags_overlay(None)
            return

        pixmap = QPixmap(asset.absolute_path)
        if pixmap.isNull():
            self._show_message("Soubor se nepodarilo zobrazit jako obrazek.")
            self._refresh_tags_overlay(None)
            return

        self._current_pixmap = pixmap
        self._render_preview_pixmap()
        self._refresh_tags_overlay(asset)

    def set_preview_mode(self, mode: str) -> None:
        if mode not in {"fit", "original"}:
            return
        self._preview_mode = mode
        self.fit_button.setChecked(mode == "fit")
        self.original_button.setChecked(mode == "original")
        self._render_preview_pixmap()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._render_preview_pixmap()
        self._position_tags_overlay()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key_Question or event.text() == "?":
            self._toggle_tags_overlay()
            return
        if self._handle_tag_shortcut(event.key(), event.modifiers()):
            self.sync_with_current_asset()
            return
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        if event.key() in (Qt.Key_Right, Qt.Key_Space):
            self._move_selection(1)
            self.sync_with_current_asset()
            return
        if event.key() == Qt.Key_Left:
            self._move_selection(-1)
            self.sync_with_current_asset()
            return
        super().keyPressEvent(event)

    def _register_shortcuts(self) -> None:
        command_map = {
            "Right": lambda: self._move_and_sync(1),
            "Space": lambda: self._move_and_sync(1),
            "Left": lambda: self._move_and_sync(-1),
            "Escape": self.close,
        }
        for key_sequence, callback in command_map.items():
            shortcut = QShortcut(QKeySequence(key_sequence), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)

    def _move_and_sync(self, offset: int) -> None:
        self._move_selection(offset)
        self.sync_with_current_asset()

    def _show_message(self, message: str) -> None:
        self._current_pixmap = None
        self.preview_scroll.setWidgetResizable(True)
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText(message)
        self._position_tags_overlay()

    def _render_preview_pixmap(self) -> None:
        if self._current_pixmap is None:
            return
        self.preview_label.setText("")
        if self._preview_mode == "fit":
            self.preview_scroll.setWidgetResizable(True)
            viewport = self.preview_scroll.viewport().size()
            scaled = self._current_pixmap.scaled(
                viewport,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)
            self._position_tags_overlay()
            return

        self.preview_scroll.setWidgetResizable(False)
        self.preview_label.setPixmap(self._current_pixmap)
        self.preview_label.resize(self._current_pixmap.size())
        self._position_tags_overlay()

    def _toggle_tags_overlay(self) -> None:
        self._tags_overlay_visible = not self._tags_overlay_visible
        if not self._tags_overlay_visible:
            self.tags_overlay_label.hide()
            return
        self._refresh_tags_overlay(self._get_current_asset())

    def _refresh_tags_overlay(self, asset: Asset | None) -> None:
        if not self._tags_overlay_visible:
            return
        if asset is None:
            self.tags_overlay_label.setText("(zadne tagy)")
            self.tags_overlay_label.show()
            self._position_tags_overlay()
            return
        self.tags_overlay_label.setText(self._get_current_tags_text(asset))
        self.tags_overlay_label.show()
        self._position_tags_overlay()

    def _position_tags_overlay(self) -> None:
        if not self._tags_overlay_visible or not self.tags_overlay_label.isVisible():
            return
        self.tags_overlay_label.adjustSize()
        viewport = self.preview_scroll.viewport()
        x = max(8, viewport.width() - self.tags_overlay_label.width() - 12)
        y = max(8, viewport.height() - self.tags_overlay_label.height() - 12)
        self.tags_overlay_label.move(x, y)


class TaggingView(QWidget):
    def __init__(self, context: ApplicationContext) -> None:
        super().__init__()
        self.context = context
        self.setFocusPolicy(Qt.StrongFocus)

        self.sources_by_id: dict[int, object] = {}
        self.folders_by_id: dict[int, Folder] = {}
        self.assets_by_id: dict[int, Asset] = {}
        self.shortcut_bindings: dict[str, ShortcutBinding] = {}
        self.tagy_shortcuts = TagyShortcuts.empty()
        self.active_shortcut_letter: str | None = None
        self.active_base_tag_name: str | None = None
        self.undo_stack: list[TaggingUndoAction] = []
        self._current_pixmap: QPixmap | None = None
        self._preview_mode = "fit"
        self._fullscreen_dialog: FullscreenPreviewDialog | None = None

        self.action_log = QListWidget()
        self.source_combo = QComboBox()
        self.folder_list = QListWidget()
        self.asset_list = QListWidget()
        self.shortcut_list = QListWidget()
        self.tagy_shortcut_list = QListWidget()
        self.direct_tags_list = QListWidget()
        self.effective_tags_list = QListWidget()

        self.preview_title = QLabel("Neni vybrany asset")
        self.preview_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("background: #f3f4f6; border: 1px solid #d0d7de; padding: 16px;")
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidget(self.preview_label)
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setMinimumHeight(420)
        self.preview_fit_button = QPushButton("Prizpusobit")
        self.preview_fit_button.setCheckable(True)
        self.preview_fit_button.setChecked(True)
        self.preview_fit_button.clicked.connect(lambda: self._set_preview_mode("fit"))
        self.preview_original_button = QPushButton("1:1")
        self.preview_original_button.setCheckable(True)
        self.preview_original_button.clicked.connect(lambda: self._set_preview_mode("original"))
        self.preview_fullscreen_button = QPushButton("Fullscreen")
        self.preview_fullscreen_button.clicked.connect(self._open_fullscreen_preview)
        self.preview_fit_button.setEnabled(False)
        self.preview_original_button.setEnabled(False)
        self.preview_fullscreen_button.setEnabled(False)
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
        self.time_tag_button = QPushButton("Datum tagy (rok/mesic)")
        self.time_tag_button.clicked.connect(self._open_time_tag_editor)
        self.time_tag_button.setEnabled(False)
        self.asset_time_tag_button = QPushButton("Datum tagy aktualni fotky")
        self.asset_time_tag_button.clicked.connect(self._open_asset_time_tag_editor)
        self.asset_time_tag_button.setEnabled(False)
        self.reload_tagy_button = QPushButton("Obnovit tagy.txt")
        self.reload_tagy_button.clicked.connect(self._reload_tagy_shortcuts)
        self.tagy_status_label = QLabel("-")
        self.tagy_status_label.setWordWrap(True)

        self._build_ui()
        self._register_shortcuts()
        self.refresh_view()

    def refresh_view(self) -> None:
        self._reload_tagy_shortcuts()
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
            "Trideni uz pracuje nad realnymi assety v databazi. Vyber slozku, otevri fotku a pouzij klavesy 1..0, F, X, sipky nebo U. "
            "Tagy slozky i datum tagy (rok/mesic) lze aplikovat jen na aktualni slozku nebo i na cely podstrom. Pro fullscreen pouzij F11. "
            "Rychle tagy lze ridit i podle tagy.txt pres Ctrl+pismeno."
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
        folders_layout.addWidget(self.time_tag_button)
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
        preview_controls_layout = QHBoxLayout()
        preview_controls_layout.addWidget(self.preview_fit_button)
        preview_controls_layout.addWidget(self.preview_original_button)
        preview_controls_layout.addWidget(self.preview_fullscreen_button)
        preview_controls_layout.addStretch(1)
        preview_layout.addLayout(preview_controls_layout)
        preview_layout.addWidget(self.preview_scroll, 1)
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
        shortcuts_help = QLabel(
            "Dvojklik na seznam nebo tlacitko upravi vazby 1..0. F = favorite, X = reject, U = undo, F11 = fullscreen preview."
        )
        shortcuts_help.setWordWrap(True)
        shortcuts_layout.addWidget(shortcuts_help)
        shortcuts_layout.addWidget(self.shortcut_list)
        tagy_help = QLabel(
            "Ctrl+pismeno prida/odebere hlavni tag dle tagy.txt. "
            "Po zvoleni Ctrl+pismeno budou klavesy 1..0 fungovat jako podkategorie."
        )
        tagy_help.setWordWrap(True)
        shortcuts_layout.addWidget(tagy_help)
        shortcuts_layout.addWidget(self.tagy_status_label)
        shortcuts_layout.addWidget(self.tagy_shortcut_list)
        shortcuts_layout.addWidget(self.reload_tagy_button)
        right_layout.addWidget(shortcuts_box)

        direct_tags_box = QGroupBox("Prime tagy")
        direct_tags_layout = QVBoxLayout(direct_tags_box)
        direct_help = QLabel("Dvojklik na prime tagy je odebere z aktualni fotky.")
        direct_help.setWordWrap(True)
        direct_tags_layout.addWidget(direct_help)
        direct_tags_layout.addWidget(self.asset_time_tag_button)
        direct_tags_layout.addWidget(self.direct_tags_list)
        right_layout.addWidget(direct_tags_box, 1)

        effective_tags_box = QGroupBox("Efektivni tagy")
        effective_tags_layout = QVBoxLayout(effective_tags_box)
        effective_help = QLabel(
            "Zobrazuji se zde prime tagy assetu i tagy zdedene ze slozky, nadrazenych slozek a eventu."
        )
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

        for letter in ascii_uppercase:
            shortcut = QShortcut(QKeySequence(f"Ctrl+{letter}"), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda value=letter: self._handle_ctrl_letter_shortcut(value))

        command_map = {
            "F": self._handle_favorite,
            "X": self._handle_reject,
            "Space": lambda: self._move_asset_selection(1),
            "Right": lambda: self._move_asset_selection(1),
            "Left": lambda: self._move_asset_selection(-1),
            "U": self._handle_undo,
            "F11": self._open_fullscreen_preview,
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

    def _reload_tagy_shortcuts(self) -> None:
        shortcuts_path = self.context.paths.tagy_path
        loaded = load_tagy_shortcuts(shortcuts_path)
        self.tagy_shortcuts = loaded

        self.tagy_shortcut_list.clear()
        if not loaded.letters and not loaded.subcategories:
            placeholder = QListWidgetItem("tagy.txt neobsahuje zadne platne mapovani.")
            placeholder.setFlags(Qt.ItemIsEnabled)
            self.tagy_shortcut_list.addItem(placeholder)
            self.tagy_status_label.setText("Nenacteny zadny Ctrl+shortcut.")
            self.active_shortcut_letter = None
            self.active_base_tag_name = None
            return

        for letter in sorted(loaded.letters):
            self.tagy_shortcut_list.addItem(f"Ctrl+{letter} -> {loaded.letters[letter]}")

        if loaded.subcategories:
            separator = QListWidgetItem("---- Podkategorie ----")
            separator.setFlags(Qt.ItemIsEnabled)
            self.tagy_shortcut_list.addItem(separator)
            for letter, digit in sorted(loaded.subcategories):
                tag_name = loaded.subcategories[(letter, digit)]
                self.tagy_shortcut_list.addItem(f"{letter}+{digit} -> {tag_name}")

        if self.active_shortcut_letter not in loaded.letters:
            self.active_shortcut_letter = None
            self.active_base_tag_name = None
            self.tagy_status_label.setText("Zvol Ctrl+pismeno pro aktivaci podkategorii 1..0.")
        else:
            assert self.active_shortcut_letter is not None
            self.active_base_tag_name = loaded.letters[self.active_shortcut_letter]
            self.tagy_status_label.setText(
                f"Aktivni: Ctrl+{self.active_shortcut_letter} ({self.active_base_tag_name})"
            )

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
            self.asset_time_tag_button.setEnabled(False)
            self._sync_fullscreen_preview()
            return

        self.asset_time_tag_button.setEnabled(True)
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
        self._sync_fullscreen_preview()

    def _load_preview(self, asset: Asset) -> None:
        if asset.media_type != MediaType.PHOTO:
            self._show_preview_message("Preview videi zatim neni implementovany. Asset lze ale tagovat a oznacovat.")
            return

        pixmap = QPixmap(asset.absolute_path)
        if pixmap.isNull():
            self._show_preview_message("Soubor se nepodarilo zobrazit jako obrazek. Tagovani ale funguje dal.")
            return

        self._current_pixmap = pixmap
        self.preview_fit_button.setEnabled(True)
        self.preview_original_button.setEnabled(True)
        self.preview_fullscreen_button.setEnabled(True)
        self._render_preview_pixmap()

    def _show_preview_message(self, message: str) -> None:
        self._current_pixmap = None
        self.preview_scroll.setWidgetResizable(True)
        self.preview_fit_button.setEnabled(False)
        self.preview_original_button.setEnabled(False)
        self.preview_fullscreen_button.setEnabled(False)
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText(message)

    def _render_preview_pixmap(self) -> None:
        if self._current_pixmap is None:
            return
        self.preview_label.setText("")
        if self._preview_mode == "fit":
            self.preview_scroll.setWidgetResizable(True)
            viewport = self.preview_scroll.viewport().size()
            scaled = self._current_pixmap.scaled(
                viewport,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)
            return

        self.preview_scroll.setWidgetResizable(False)
        self.preview_label.setPixmap(self._current_pixmap)
        self.preview_label.resize(self._current_pixmap.size())

    def _set_preview_mode(self, mode: str) -> None:
        if mode not in {"fit", "original"}:
            return
        self._preview_mode = mode
        self.preview_fit_button.setChecked(mode == "fit")
        self.preview_original_button.setChecked(mode == "original")
        self._render_preview_pixmap()

    def _open_fullscreen_preview(self) -> None:
        asset = self._current_asset()
        if asset is None:
            self._append_log("Neni vybrany zadny asset.")
            return
        if asset.media_type != MediaType.PHOTO:
            QMessageBox.information(self, "Fullscreen", "Fullscreen preview je zatim dostupny jen pro fotky.")
            return

        if self._fullscreen_dialog is None:
            self._fullscreen_dialog = FullscreenPreviewDialog(
                get_current_asset=self._current_asset,
                move_selection=self._move_asset_selection,
                handle_tag_shortcut=self._handle_fullscreen_tag_shortcut,
                get_current_tags_text=self._current_asset_tags_text,
                parent=self,
            )
        self._fullscreen_dialog.open_for_current_asset()

    def _sync_fullscreen_preview(self) -> None:
        if self._fullscreen_dialog is None:
            return
        if self._fullscreen_dialog.isVisible():
            self._fullscreen_dialog.sync_with_current_asset()

    def _handle_fullscreen_tag_shortcut(self, key: int, modifiers: Qt.KeyboardModifiers) -> bool:
        if modifiers & Qt.ControlModifier and Qt.Key_A <= key <= Qt.Key_Z:
            self._handle_ctrl_letter_shortcut(chr(key))
            return True
        if Qt.Key_0 <= key <= Qt.Key_9:
            self._handle_quick_tag(str(key - Qt.Key_0))
            return True
        if key == Qt.Key_F:
            self._handle_favorite()
            return True
        if key == Qt.Key_X:
            self._handle_reject()
            return True
        if key == Qt.Key_U:
            self._handle_undo()
            return True
        return False

    def _current_asset_tags_text(self, asset: Asset) -> str:
        tag_state = self.context.tagging_service.get_asset_tag_state(asset.id)
        names = [tag.name for tag in tag_state.direct_tags]
        if not names:
            return "(zadne tagy)"
        return "\n".join(names)

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

        try:
            result = self.context.tagging_service.save_folder_tags(
                folder.id,
                dialog.values(),
                include_subfolders=dialog.apply_to_subfolders(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Tagy slozky", str(exc))
            self._append_log(str(exc))
            return
        self._append_log(result.message)
        self._refresh_current_folder(folder.id)

    def _open_time_tag_editor(self) -> None:
        folder = self._current_folder()
        if folder is None:
            QMessageBox.information(self, "Datum tagy", "Nejdriv vyber slozku, kterou chces hromadne upravit.")
            return

        folder_label = folder.relative_path or "."
        dialog = TimeTagEditorDialog(scope_label=folder_label, allow_subfolders=True, parent=self)
        if dialog.exec() == 0:
            return

        mode, year, month, include_subfolders = dialog.selection()
        folder_ids = [folder.id]
        if include_subfolders:
            folder_ids = self.context.tag_repository.list_descendant_folder_ids(folder.id)

        asset_ids = self.context.asset_repository.list_ids_by_folder_ids(folder_ids)
        if not asset_ids:
            message = "Ve zvolenem rozsahu nejsou zadne assety."
            QMessageBox.information(self, "Datum tagy", message)
            self._append_log(message)
            return

        try:
            if mode == "auto":
                summary = self.context.time_tag_service.set_auto_time_tags(asset_ids, assigned_via="bulk")
            else:
                assert year is not None
                summary = self.context.time_tag_service.set_manual_time_tags(
                    asset_ids,
                    year=year,
                    month=month,
                    assigned_via="bulk",
                )
        except ValueError as exc:
            QMessageBox.warning(self, "Datum tagy", str(exc))
            self._append_log(str(exc))
            return

        self._append_log(summary.message)
        self._refresh_current_folder(folder.id)

    def _open_asset_time_tag_editor(self) -> None:
        asset = self._current_asset()
        if asset is None:
            QMessageBox.information(self, "Datum tagy", "Nejdriv vyber fotku, kterou chces upravit.")
            return

        scope_label = asset.relative_path
        dialog = TimeTagEditorDialog(scope_label=scope_label, allow_subfolders=False, parent=self)
        if dialog.exec() == 0:
            return

        mode, year, month, _include_subfolders = dialog.selection()
        try:
            if mode == "auto":
                summary = self.context.time_tag_service.set_auto_time_tags([asset.id], assigned_via="manual")
            else:
                assert year is not None
                summary = self.context.time_tag_service.set_manual_time_tags(
                    [asset.id],
                    year=year,
                    month=month,
                    assigned_via="manual",
                )
        except ValueError as exc:
            QMessageBox.warning(self, "Datum tagy", str(exc))
            self._append_log(str(exc))
            return

        self._append_log(f"{summary.message} ({asset.file_name})")
        self._refresh_current_asset(asset.id)

    def _handle_quick_tag(self, key_sequence: str) -> None:
        if self.active_base_tag_name is not None and key_sequence in SUBCATEGORY_DIGITS:
            self._handle_subcategory_shortcut(key_sequence)
            return

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

    def _handle_ctrl_letter_shortcut(self, letter: str) -> None:
        asset = self._current_asset()
        if asset is None:
            self._append_log("Neni vybrany zadny asset.")
            return

        letter_key = letter.upper()
        tag_name = self.tagy_shortcuts.letters.get(letter_key)
        if not tag_name:
            message = f"Klavesa Ctrl+{letter_key} nema v tagy.txt prirazeny tag."
            self.tagy_status_label.setText(message)
            self._append_log(message)
            return

        result = self.context.tagging_service.toggle_tag_by_name(asset.id, tag_name, assigned_via="shortcut")
        self.active_shortcut_letter = letter_key
        self.active_base_tag_name = tag_name
        self.tagy_status_label.setText(
            f"{result.message} Aktivni pismeno: {letter_key}. Podkategorie pres klavesy 1..0."
        )
        self._consume_action_result(result, asset.id)

    def _handle_subcategory_shortcut(self, digit: str) -> None:
        asset = self._current_asset()
        if asset is None:
            self._append_log("Neni vybrany zadny asset.")
            return

        if self.active_shortcut_letter is None or self.active_base_tag_name is None:
            message = "Nejdriv zvol Ctrl+pismeno z tagy.txt, potom podkategorii 1..0."
            self.tagy_status_label.setText(message)
            self._append_log(message)
            return

        explicit_tag = self.tagy_shortcuts.subcategories.get((self.active_shortcut_letter, digit))
        tag_name = explicit_tag or f"{self.active_base_tag_name}:{digit}"
        result = self.context.tagging_service.toggle_tag_by_name(asset.id, tag_name, assigned_via="shortcut")
        self.tagy_status_label.setText(
            f"{result.message} (podkategorie pro Ctrl+{self.active_shortcut_letter})"
        )
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
        has_folder = self._selected_folder_id() is not None
        self.folder_tag_button.setEnabled(has_folder)
        self.time_tag_button.setEnabled(has_folder)

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
