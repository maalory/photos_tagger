from __future__ import annotations

import re
from typing import Callable, Iterable

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from photos_tagger.bootstrap import ApplicationContext
from photos_tagger.domain import Asset, Tag
from photos_tagger.tagging import TagyShortcuts, load_tagy_shortcuts
from photos_tagger.ui.dialogs import TimeTagEditorDialog


THUMBNAIL_SIZE = QSize(180, 180)
SUBCATEGORY_DIGITS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")
YEAR_TAG_RE = re.compile(r"^rok:(\d{4})$", re.IGNORECASE)
MONTH_TAG_RE = re.compile(r"^mesic:(\d{4})-(\d{2})$", re.IGNORECASE)
SLICER_BUTTON_STYLE = (
    "QPushButton {"
    "background: #f8fafc; color: #1f2937; border: 1px solid #cbd5e1; border-radius: 7px; "
    "padding: 6px 10px; font-weight: 600; min-height: 28px;"
    "}"
    "QPushButton:hover {background: #e2e8f0;}"
    "QPushButton:pressed {background: #dbeafe;}"
    "QPushButton:checked {background: #1d4ed8; color: #ffffff; border-color: #1e40af;}"
    "QPushButton[missingInDb=\"true\"] {background: #fff1f2; color: #be123c; border-color: #fecdd3;}"
    "QPushButton[missingInDb=\"true\"]:hover {background: #ffe4e6;}"
    "QPushButton[missingInDb=\"true\"]:checked {background: #1d4ed8; color: #ffffff; border-color: #1e40af;}"
    "QPushButton:disabled {background: #f3f4f6; color: #9ca3af; border-color: #e5e7eb;}"
)


class AlbumPreviewDialog(QDialog):
    def __init__(
        self,
        context: ApplicationContext,
        on_asset_updated: Callable[[Asset], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.on_asset_updated = on_asset_updated
        self.assets: list[Asset] = []
        self.current_index = 0
        self.preview_mode = "fit"
        self.current_pixmap: QPixmap | None = None
        self.slideshow_timer = QTimer(self)
        self.slideshow_timer.timeout.connect(self._next_asset)
        self.tagy_shortcuts = TagyShortcuts.empty()
        self.active_shortcut_letter: str | None = None
        self.active_base_tag_name: str | None = None
        self.tags_overlay_visible = False
        self.photo_only_fullscreen = False
        self._default_tags_overlay_style = (
            "background: #ffffff; color: #000000; border: 1px solid #111111; "
            "padding: 8px; font-size: 18px;"
        )
        self._fullscreen_tags_overlay_style = (
            "background: #ffffff; color: #000000; border: 1px solid #111111; "
            "padding: 10px; font-size: 24px;"
        )
        self._default_feedback_style = (
            "background: #ffffff; color: #000000; border: 1px solid #111111; "
            "padding: 10px; font-size: 22px; font-weight: 700;"
        )
        self._fullscreen_feedback_style = (
            "background: #ffffff; color: #000000; border: 1px solid #111111; "
            "padding: 12px; font-size: 30px; font-weight: 700;"
        )
        self._default_preview_style = "background: #111827; color: #e5e7eb; border: 1px solid #374151; padding: 14px;"
        self._photo_only_preview_style = "background: #000000; color: #e5e7eb; border: none; padding: 0px;"

        self.setWindowTitle("Prohlizec alba")
        self.resize(1360, 880)
        self.setWindowFlag(Qt.Window, True)

        self.title_label = QLabel("Neni vybrany asset")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.path_label = QLabel("-")
        self.path_label.setWordWrap(True)
        self.position_label = QLabel("-")

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet(self._default_preview_style)

        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidget(self.preview_label)
        self.preview_scroll.setWidgetResizable(True)
        self.tags_overlay_label = QLabel(self.preview_scroll.viewport())
        self.tags_overlay_label.setWordWrap(True)
        self.tags_overlay_label.setStyleSheet(self._default_tags_overlay_style)
        self.tags_overlay_label.hide()
        self.feedback_overlay_label = QLabel(self.preview_scroll.viewport())
        self.feedback_overlay_label.setWordWrap(True)
        self.feedback_overlay_label.setStyleSheet(self._default_feedback_style)
        self.feedback_overlay_label.hide()
        self.feedback_timer = QTimer(self)
        self.feedback_timer.setSingleShot(True)
        self.feedback_timer.timeout.connect(self.feedback_overlay_label.hide)

        self.prev_button = QPushButton("Predchozi")
        self.prev_button.clicked.connect(self._previous_asset)
        self.next_button = QPushButton("Dalsi")
        self.next_button.clicked.connect(self._next_asset)
        self.fit_button = QPushButton("Prizpusobit")
        self.fit_button.setCheckable(True)
        self.fit_button.setChecked(True)
        self.fit_button.clicked.connect(lambda: self._set_preview_mode("fit"))
        self.original_button = QPushButton("1:1")
        self.original_button.setCheckable(True)
        self.original_button.clicked.connect(lambda: self._set_preview_mode("original"))
        self.fullscreen_button = QPushButton("Fullscreen (F11)")
        self.fullscreen_button.clicked.connect(self._toggle_fullscreen)
        self.interval_combo = QComboBox()
        self.interval_combo.addItem("2 s", 2000)
        self.interval_combo.addItem("3 s", 3000)
        self.interval_combo.addItem("5 s", 5000)
        self.interval_combo.addItem("8 s", 8000)
        self.interval_combo.setCurrentIndex(1)
        self.interval_combo.currentIndexChanged.connect(self._on_interval_changed)
        self.slideshow_button = QPushButton("Start prezentace")
        self.slideshow_button.setCheckable(True)
        self.slideshow_button.clicked.connect(self._toggle_slideshow)
        self.close_button = QPushButton("Zavrit")
        self.close_button.clicked.connect(self.close)

        self.controls_widget = QWidget()
        controls_layout = QHBoxLayout(self.controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.addWidget(self.prev_button)
        controls_layout.addWidget(self.next_button)
        controls_layout.addWidget(self.fit_button)
        controls_layout.addWidget(self.original_button)
        controls_layout.addWidget(self.fullscreen_button)
        controls_layout.addStretch(1)
        controls_layout.addWidget(QLabel("Interval:"))
        controls_layout.addWidget(self.interval_combo)
        controls_layout.addWidget(self.slideshow_button)
        controls_layout.addWidget(self.close_button)

        self.shortcuts_label = QLabel(
            "Klavesy: Left/Right/Space = predchozi/dalsi, F11 = fullscreen foto-only, Ctrl+pismeno/1..0 = tagovani, ? = tagy, P = prezentace, Esc = zpet."
        )
        self.shortcuts_label.setWordWrap(True)

        self.metadata_labels = {
            "captured_at": QLabel("-"),
            "captured_source": QLabel("-"),
            "gps": QLabel("-"),
            "resolution": QLabel("-"),
            "file_size": QLabel("-"),
            "flags": QLabel("-"),
        }
        self.direct_tags_list = QListWidget()
        self.effective_tags_list = QListWidget()
        self.action_status_label = QLabel("-")
        self.action_status_label.setWordWrap(True)
        self.shortcut_status_label = QLabel("-")
        self.shortcut_status_label.setWordWrap(True)
        self.shortcuts_list = QListWidget()
        self.reload_shortcuts_button = QPushButton("Obnovit tagy.txt")
        self.reload_shortcuts_button.clicked.connect(self._reload_shortcuts_from_file)

        self.sidebar = QWidget()
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(10)

        metadata_box = QGroupBox("Metadata")
        metadata_layout = QFormLayout(metadata_box)
        metadata_layout.addRow("Datum:", self.metadata_labels["captured_at"])
        metadata_layout.addRow("Zdroj data:", self.metadata_labels["captured_source"])
        metadata_layout.addRow("GPS:", self.metadata_labels["gps"])
        metadata_layout.addRow("Rozliseni:", self.metadata_labels["resolution"])
        metadata_layout.addRow("Velikost:", self.metadata_labels["file_size"])
        metadata_layout.addRow("Priznaky:", self.metadata_labels["flags"])
        sidebar_layout.addWidget(metadata_box)

        shortcuts_box = QGroupBox("Rychle tagy (tagy.txt)")
        shortcuts_layout = QVBoxLayout(shortcuts_box)
        shortcuts_help = QLabel(
            "Ctrl+pismeno prida/odebere hlavni tag ze souboru tagy.txt. "
            "Cisla 1..0 priradi podkategorii k naposledy zvolene klavese. "
            "Specialni klavesy (napr. ';' nebo '\\') lze mapovat take."
        )
        shortcuts_help.setWordWrap(True)
        shortcuts_layout.addWidget(shortcuts_help)
        shortcuts_layout.addWidget(self.action_status_label)
        shortcuts_layout.addWidget(self.shortcut_status_label)
        shortcuts_layout.addWidget(self.shortcuts_list)
        shortcuts_layout.addWidget(self.reload_shortcuts_button)
        sidebar_layout.addWidget(shortcuts_box, 1)

        direct_tags_box = QGroupBox("Prime tagy")
        direct_tags_layout = QVBoxLayout(direct_tags_box)
        direct_tags_layout.addWidget(self.direct_tags_list)
        sidebar_layout.addWidget(direct_tags_box, 1)

        effective_tags_box = QGroupBox("Efektivni tagy")
        effective_tags_layout = QVBoxLayout(effective_tags_box)
        effective_tags_layout.addWidget(self.effective_tags_list)
        sidebar_layout.addWidget(effective_tags_box, 1)

        content_layout = QHBoxLayout()
        content_layout.addWidget(self.preview_scroll, 3)
        content_layout.addWidget(self.sidebar, 2)

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(12, 12, 12, 12)
        self.root_layout.setSpacing(10)
        self.root_layout.addWidget(self.title_label)
        self.root_layout.addWidget(self.path_label)
        self.root_layout.addWidget(self.position_label)
        self.root_layout.addWidget(self.controls_widget)
        self.root_layout.addWidget(self.shortcuts_label)
        self.root_layout.addLayout(content_layout, 1)

        self._clear_overlay()
        self._reload_shortcuts_from_file()
        self._register_shortcuts()
        self._update_overlay_styles()

    def open_assets(
        self,
        assets: list[Asset],
        start_index: int,
        start_fullscreen: bool = False,
        start_slideshow: bool = False,
    ) -> None:
        self._reload_shortcuts_from_file()
        self.assets = list(assets)
        if not self.assets:
            self._show_preview_message("Aktualni filtr nema zadne fotky.")
            self._clear_overlay()
            self.show()
            self.raise_()
            self.activateWindow()
            return

        self.current_index = max(0, min(len(self.assets) - 1, int(start_index)))
        self._show_asset(self.current_index)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

        self._set_photo_only_fullscreen(start_fullscreen)
        if start_slideshow:
            self._set_slideshow_active(True)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._render_preview_pixmap()
        self._position_tags_overlay()
        self._position_feedback_overlay()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key_Question or event.text() == "?":
            self._toggle_tags_overlay()
            return
        if self._handle_shortcut_key(event):
            return
        if event.key() == Qt.Key_Escape:
            if self.photo_only_fullscreen:
                self._set_photo_only_fullscreen(False)
                return
            if self.isFullScreen():
                self.showNormal()
                return
            self.close()
            return
        if event.key() in (Qt.Key_Right, Qt.Key_Space):
            self._next_asset()
            return
        if event.key() == Qt.Key_Left:
            self._previous_asset()
            return
        if event.key() == Qt.Key_F11:
            self._toggle_fullscreen()
            return
        if event.key() == Qt.Key_P:
            self._set_slideshow_active(not self.slideshow_button.isChecked())
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._set_slideshow_active(False)
        self._set_photo_only_fullscreen(False)
        self.feedback_timer.stop()
        self.feedback_overlay_label.hide()
        super().closeEvent(event)

    def _show_asset(self, index: int) -> None:
        if not self.assets:
            self._show_preview_message("Aktualni filtr nema zadne fotky.")
            self._clear_overlay()
            return

        self.current_index = max(0, min(len(self.assets) - 1, int(index)))
        asset = self._fresh_asset_for_index(self.current_index)
        if asset is None:
            self._show_preview_message("Asset se nepodarilo nacist z databaze.")
            self._clear_overlay()
            return

        self.title_label.setText(asset.file_name)
        self.path_label.setText(asset.relative_path)
        self.position_label.setText(f"Fotka {self.current_index + 1} / {len(self.assets)}")
        self.action_status_label.setText("-")
        self._update_overlay(asset)
        self._refresh_tags_overlay(asset)

        pixmap = QPixmap(asset.absolute_path)
        if pixmap.isNull():
            self._show_preview_message("Soubor se nepodarilo zobrazit jako obrazek.")
            return

        self.current_pixmap = pixmap
        self._render_preview_pixmap()

    def _show_preview_message(self, message: str) -> None:
        self.current_pixmap = None
        self.preview_scroll.setWidgetResizable(True)
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText(message)
        self._refresh_tags_overlay(None)

    def _render_preview_pixmap(self) -> None:
        if self.current_pixmap is None:
            return

        self.preview_label.setText("")
        if self.preview_mode == "fit":
            self.preview_scroll.setWidgetResizable(True)
            viewport = self.preview_scroll.viewport().size()
            scaled = self.current_pixmap.scaled(viewport, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_label.setPixmap(scaled)
            self._position_tags_overlay()
            return

        self.preview_scroll.setWidgetResizable(False)
        self.preview_label.setPixmap(self.current_pixmap)
        self.preview_label.resize(self.current_pixmap.size())
        self._position_tags_overlay()

    def _set_preview_mode(self, mode: str) -> None:
        if mode not in {"fit", "original"}:
            return
        self.preview_mode = mode
        self.fit_button.setChecked(mode == "fit")
        self.original_button.setChecked(mode == "original")
        self._render_preview_pixmap()

    def _toggle_fullscreen(self) -> None:
        self._set_photo_only_fullscreen(not self.photo_only_fullscreen)

    def _set_photo_only_fullscreen(self, enabled: bool) -> None:
        self.photo_only_fullscreen = bool(enabled)
        self._apply_photo_only_layout(self.photo_only_fullscreen)
        if self.photo_only_fullscreen:
            if not self.isFullScreen():
                self.showFullScreen()
        elif self.isFullScreen():
            self.showNormal()
        self.fullscreen_button.setText(
            "Ukoncit fullscreen (F11)" if self.photo_only_fullscreen else "Fullscreen (F11)"
        )
        self._update_overlay_styles()
        self._position_tags_overlay()
        self._position_feedback_overlay()
        self.setFocus()

    def _apply_photo_only_layout(self, enabled: bool) -> None:
        is_normal_layout = not enabled
        self.title_label.setVisible(is_normal_layout)
        self.path_label.setVisible(is_normal_layout)
        self.position_label.setVisible(is_normal_layout)
        self.controls_widget.setVisible(is_normal_layout)
        self.shortcuts_label.setVisible(is_normal_layout)
        self.sidebar.setVisible(is_normal_layout)
        if enabled:
            self.root_layout.setContentsMargins(0, 0, 0, 0)
            self.root_layout.setSpacing(0)
            self.preview_label.setStyleSheet(self._photo_only_preview_style)
            return
        self.root_layout.setContentsMargins(12, 12, 12, 12)
        self.root_layout.setSpacing(10)
        self.preview_label.setStyleSheet(self._default_preview_style)

    def _previous_asset(self) -> None:
        if not self.assets:
            return
        self._show_asset((self.current_index - 1) % len(self.assets))

    def _next_asset(self) -> None:
        if not self.assets:
            return
        self._show_asset((self.current_index + 1) % len(self.assets))

    def _on_interval_changed(self, _index: int) -> None:
        if self.slideshow_timer.isActive():
            interval = int(self.interval_combo.currentData())
            self.slideshow_timer.start(interval)

    def _toggle_slideshow(self) -> None:
        self._set_slideshow_active(self.slideshow_button.isChecked())

    def _set_slideshow_active(self, is_active: bool) -> None:
        self.slideshow_button.blockSignals(True)
        self.slideshow_button.setChecked(is_active)
        self.slideshow_button.blockSignals(False)
        if is_active:
            self.slideshow_button.setText("Stop prezentace")
            interval = int(self.interval_combo.currentData())
            self.slideshow_timer.start(interval)
            return
        self.slideshow_button.setText("Start prezentace")
        self.slideshow_timer.stop()

    def _current_asset(self) -> Asset | None:
        if not self.assets:
            return None
        if self.current_index < 0 or self.current_index >= len(self.assets):
            return None
        return self.assets[self.current_index]

    def _fresh_asset_for_index(self, index: int) -> Asset | None:
        if index < 0 or index >= len(self.assets):
            return None
        current = self.assets[index]
        fresh = self.context.asset_repository.get_by_id(current.id)
        if fresh is None:
            return current
        self.assets[index] = fresh
        return fresh

    def _handle_shortcut_key(self, event) -> bool:
        key = event.key()
        modifiers = event.modifiers()
        is_ctrl = bool(modifiers & Qt.ControlModifier)
        key_text = event.text()

        if is_ctrl and Qt.Key_A <= key <= Qt.Key_Z:
            letter = chr(key)
            self._apply_letter_shortcut(letter)
            return True

        if Qt.Key_0 <= key <= Qt.Key_9:
            digit = str(key - Qt.Key_0)
            self._apply_subcategory_shortcut(digit)
            return True

        if key_text in self.tagy_shortcuts.special_keys:
            self._apply_special_shortcut(key_text)
            return True

        return False

    def _apply_letter_shortcut(self, letter: str) -> None:
        asset = self._current_asset()
        if asset is None:
            self.shortcut_status_label.setText("Neni vybrany asset.")
            return

        letter_key = letter.upper()
        tag_name = self.tagy_shortcuts.letters.get(letter_key)
        if not tag_name:
            self.shortcut_status_label.setText(f"Klavesa Ctrl+{letter_key} nema v tagy.txt prirazeny tag.")
            return

        result = self.context.tagging_service.toggle_tag_by_name(asset.id, tag_name, assigned_via="shortcut")
        self.active_shortcut_letter = letter_key
        self.active_base_tag_name = tag_name
        self._refresh_asset_after_flag_update(asset.id, result.message)
        self._show_transient_feedback(result.message)
        self.shortcut_status_label.setText(
            f"{result.message} Aktivni pismeno: {letter_key}. Podkategorie pres cisla 1..0."
        )

    def _apply_subcategory_shortcut(self, digit: str) -> None:
        asset = self._current_asset()
        if asset is None:
            self.shortcut_status_label.setText("Neni vybrany asset.")
            return

        if digit not in SUBCATEGORY_DIGITS:
            return
        if self.active_base_tag_name is None or self.active_shortcut_letter is None:
            self.shortcut_status_label.setText("Nejdriv zvol Ctrl+pismeno z tagy.txt, potom podkategorii 1..0.")
            return

        explicit_tag = self.tagy_shortcuts.subcategories.get((self.active_shortcut_letter, digit))
        tag_name = explicit_tag or f"{self.active_base_tag_name}:{digit}"
        result = self.context.tagging_service.toggle_tag_by_name(asset.id, tag_name, assigned_via="shortcut")
        self._refresh_asset_after_flag_update(asset.id, result.message)
        self._show_transient_feedback(result.message)
        self.shortcut_status_label.setText(
            f"{result.message} (podkategorie pro Ctrl+{self.active_shortcut_letter})"
        )

    def _apply_special_shortcut(self, key_text: str) -> None:
        asset = self._current_asset()
        if asset is None:
            self.shortcut_status_label.setText("Neni vybrany asset.")
            return

        tag_name = self.tagy_shortcuts.special_keys.get(key_text)
        if not tag_name:
            self.shortcut_status_label.setText(f"Klavesa '{key_text}' nema v tagy.txt prirazeny tag.")
            return

        result = self.context.tagging_service.toggle_tag_by_name(asset.id, tag_name, assigned_via="shortcut")
        self._refresh_asset_after_flag_update(asset.id, result.message)
        self._show_transient_feedback(result.message)
        self.shortcut_status_label.setText(f"{result.message} (specialni klavesa '{key_text}')")

    def _reload_shortcuts_from_file(self) -> None:
        shortcuts_path = self.context.paths.tagy_path
        loaded = load_tagy_shortcuts(shortcuts_path)
        self.tagy_shortcuts = loaded

        self.shortcuts_list.clear()
        if not loaded.letters and not loaded.subcategories and not loaded.special_keys:
            placeholder = QListWidgetItem("tagy.txt neobsahuje zadne platne mapovani.")
            placeholder.setFlags(Qt.ItemIsEnabled)
            self.shortcuts_list.addItem(placeholder)
            self.shortcut_status_label.setText("Nenacteny zadny Ctrl+shortcut.")
            self.active_shortcut_letter = None
            self.active_base_tag_name = None
            return

        for letter in sorted(loaded.letters):
            self.shortcuts_list.addItem(f"Ctrl+{letter} -> {loaded.letters[letter]}")

        if loaded.special_keys:
            separator = QListWidgetItem("---- Specialni klavesy ----")
            separator.setFlags(Qt.ItemIsEnabled)
            self.shortcuts_list.addItem(separator)
            for key_text in sorted(loaded.special_keys):
                self.shortcuts_list.addItem(f"{key_text} -> {loaded.special_keys[key_text]}")

        if loaded.subcategories:
            separator = QListWidgetItem("---- Podkategorie ----")
            separator.setFlags(Qt.ItemIsEnabled)
            self.shortcuts_list.addItem(separator)
            for letter, digit in sorted(loaded.subcategories):
                tag_name = loaded.subcategories[(letter, digit)]
                self.shortcuts_list.addItem(f"{letter}+{digit} -> {tag_name}")

        if self.active_shortcut_letter not in loaded.letters:
            self.active_shortcut_letter = None
            self.active_base_tag_name = None
            self.shortcut_status_label.setText("Zvol Ctrl+pismeno pro aktivaci podkategorii 1..0.")
        else:
            assert self.active_shortcut_letter is not None
            self.active_base_tag_name = loaded.letters[self.active_shortcut_letter]
            self.shortcut_status_label.setText(
                f"Aktivni: Ctrl+{self.active_shortcut_letter} ({self.active_base_tag_name})"
            )

    def _refresh_asset_after_flag_update(self, asset_id: int, message: str) -> None:
        fresh_asset = self.context.asset_repository.get_by_id(asset_id)
        if fresh_asset is None:
            self.action_status_label.setText(message)
            return
        if 0 <= self.current_index < len(self.assets) and self.assets[self.current_index].id == asset_id:
            self.assets[self.current_index] = fresh_asset
        self.on_asset_updated(fresh_asset)
        self._update_overlay(fresh_asset)
        self._refresh_tags_overlay(fresh_asset)
        self.action_status_label.setText(message)

    def _update_overlay(self, asset: Asset) -> None:
        metadata = self.context.metadata_repository.get_by_asset_id(asset.id)
        tag_state = self.context.tagging_service.get_asset_tag_state(asset.id)

        self.metadata_labels["captured_at"].setText(_format_datetime(asset.captured_at))
        self.metadata_labels["captured_source"].setText(asset.captured_at_source.value)
        self.metadata_labels["gps"].setText(
            _format_gps(metadata.gps_lat if metadata else None, metadata.gps_lng if metadata else None)
        )
        self.metadata_labels["resolution"].setText(_format_resolution(asset.width, asset.height))
        self.metadata_labels["file_size"].setText(_format_file_size(asset.file_size))
        self.metadata_labels["flags"].setText(_format_flags(asset.is_favorite, asset.is_rejected))

        self.direct_tags_list.clear()
        for tag in tag_state.direct_tags:
            self.direct_tags_list.addItem(tag.name)
        if not tag_state.direct_tags:
            placeholder = QListWidgetItem("Zatim zadne prime tagy")
            placeholder.setFlags(Qt.ItemIsEnabled)
            self.direct_tags_list.addItem(placeholder)

        self.effective_tags_list.clear()
        for effective_tag in tag_state.effective_tags:
            self.effective_tags_list.addItem(f"{effective_tag.scope.value}: {effective_tag.tag_name}")
        if not tag_state.effective_tags:
            placeholder = QListWidgetItem("Zatim zadne efektivni tagy")
            placeholder.setFlags(Qt.ItemIsEnabled)
            self.effective_tags_list.addItem(placeholder)

    def _clear_overlay(self) -> None:
        self.action_status_label.setText("-")
        for label in self.metadata_labels.values():
            label.setText("-")

        self.direct_tags_list.clear()
        direct_placeholder = QListWidgetItem("Zatim zadne prime tagy")
        direct_placeholder.setFlags(Qt.ItemIsEnabled)
        self.direct_tags_list.addItem(direct_placeholder)

        self.effective_tags_list.clear()
        effective_placeholder = QListWidgetItem("Zatim zadne efektivni tagy")
        effective_placeholder.setFlags(Qt.ItemIsEnabled)
        self.effective_tags_list.addItem(effective_placeholder)

    def _toggle_tags_overlay(self) -> None:
        self.tags_overlay_visible = not self.tags_overlay_visible
        if not self.tags_overlay_visible:
            self.tags_overlay_label.hide()
            return
        self._refresh_tags_overlay(self._current_asset())

    def _refresh_tags_overlay(self, asset: Asset | None) -> None:
        if not self.tags_overlay_visible:
            return
        if asset is None:
            self.tags_overlay_label.setText("(zadne tagy)")
            self.tags_overlay_label.show()
            self._position_tags_overlay()
            return
        tag_state = self.context.tagging_service.get_asset_tag_state(asset.id)
        names = [tag.name for tag in tag_state.direct_tags]
        self.tags_overlay_label.setText("\n".join(names) if names else "(zadne tagy)")
        self.tags_overlay_label.show()
        self._position_tags_overlay()

    def _position_tags_overlay(self) -> None:
        if not self.tags_overlay_visible or not self.tags_overlay_label.isVisible():
            return
        self.tags_overlay_label.adjustSize()
        viewport = self.preview_scroll.viewport()
        x = max(8, viewport.width() - self.tags_overlay_label.width() - 12)
        y = max(8, viewport.height() - self.tags_overlay_label.height() - 12)
        self.tags_overlay_label.move(x, y)

    def _position_feedback_overlay(self) -> None:
        if not self.feedback_overlay_label.isVisible():
            return
        self.feedback_overlay_label.adjustSize()
        viewport = self.preview_scroll.viewport()
        x = max(8, viewport.width() - self.feedback_overlay_label.width() - 12)
        y = 12
        self.feedback_overlay_label.move(x, y)

    def _show_transient_feedback(self, message: str) -> None:
        if not self.photo_only_fullscreen:
            return
        self.feedback_timer.stop()
        self.feedback_overlay_label.setText(message)
        self.feedback_overlay_label.show()
        self._position_feedback_overlay()
        self.feedback_timer.start(1400)

    def _update_overlay_styles(self) -> None:
        if self.photo_only_fullscreen:
            self.tags_overlay_label.setStyleSheet(self._fullscreen_tags_overlay_style)
            self.feedback_overlay_label.setStyleSheet(self._fullscreen_feedback_style)
            return
        self.tags_overlay_label.setStyleSheet(self._default_tags_overlay_style)
        self.feedback_overlay_label.setStyleSheet(self._default_feedback_style)

    def _register_shortcuts(self) -> None:
        command_map = {
            "Right": self._next_asset,
            "Space": self._next_asset,
            "Left": self._previous_asset,
            "F11": self._toggle_fullscreen,
            "P": lambda: self._set_slideshow_active(not self.slideshow_button.isChecked()),
            "Escape": self._handle_escape_shortcut,
        }
        for key_sequence, callback in command_map.items():
            shortcut = QShortcut(QKeySequence(key_sequence), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)

        for key_text, qt_key in ((";", Qt.Key_Semicolon), ("\\", Qt.Key_Backslash)):
            shortcut = QShortcut(QKeySequence(qt_key), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda value=key_text: self._apply_special_shortcut(value))

    def _handle_escape_shortcut(self) -> None:
        if self.photo_only_fullscreen:
            self._set_photo_only_fullscreen(False)
            return
        if self.isFullScreen():
            self.showNormal()
            return
        self.close()


class AlbumsView(QWidget):
    def __init__(self, context: ApplicationContext) -> None:
        super().__init__()
        self.context = context
        self.tags_by_id: dict[int, Tag] = {}
        self.tags_by_name_casefold: dict[str, Tag] = {}
        self.assets_by_id: dict[int, Asset] = {}
        self.filtered_assets: list[Asset] = []
        self.filter_tagy_shortcuts = TagyShortcuts.empty()
        self.filter_tag_names: list[str] = []
        self.filter_tags_from_tagy = False
        self.year_tag_names_by_value: dict[str, str] = {}
        self.month_tag_names_by_value: dict[str, list[str]] = {}
        self.month_tag_names_by_year_month: dict[tuple[str, str], str] = {}
        self.year_slicer_buttons: dict[str, QPushButton] = {}
        self.month_slicer_buttons: dict[str, QPushButton] = {}
        self.text_tag_slicer_buttons: dict[str, QPushButton] = {}
        self.preview_dialog: AlbumPreviewDialog | None = None
        self._build_ui()
        self.refresh_view()

    def _build_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(16)

        filters_box = QGroupBox("Filtr podle tagu")
        filters_layout = QVBoxLayout(filters_box)
        intro = QLabel(
            "Vyber jeden nebo vice filtru. Zobrazi se fotky, ktere odpovidaji alespon jednomu vybranemu filtru."
        )
        intro.setWordWrap(True)
        filters_layout.addWidget(intro)

        time_slicer_box = QGroupBox("Datum (slicer)")
        time_slicer_layout = QVBoxLayout(time_slicer_box)
        time_slicer_layout.setSpacing(6)

        year_row = QWidget()
        year_row_layout = QHBoxLayout(year_row)
        year_row_layout.setContentsMargins(0, 0, 0, 0)
        year_row_layout.setSpacing(8)
        year_row_layout.addWidget(QLabel("Rok:"))
        self.year_slicer_grid = QGridLayout()
        self.year_slicer_grid.setContentsMargins(0, 0, 0, 0)
        self.year_slicer_grid.setHorizontalSpacing(6)
        self.year_slicer_grid.setVerticalSpacing(6)
        year_row_layout.addLayout(self.year_slicer_grid, 1)
        time_slicer_layout.addWidget(year_row)

        month_row = QWidget()
        month_row_layout = QHBoxLayout(month_row)
        month_row_layout.setContentsMargins(0, 0, 0, 0)
        month_row_layout.setSpacing(8)
        month_row_layout.addWidget(QLabel("Mesic:"))
        self.month_slicer_grid = QGridLayout()
        self.month_slicer_grid.setContentsMargins(0, 0, 0, 0)
        self.month_slicer_grid.setHorizontalSpacing(6)
        self.month_slicer_grid.setVerticalSpacing(6)
        month_row_layout.addLayout(self.month_slicer_grid, 1)
        time_slicer_layout.addWidget(month_row)
        filters_layout.addWidget(time_slicer_box)

        tags_label = QLabel("Tagy z tagy.txt")
        tags_label.setStyleSheet("font-weight: 600;")
        filters_layout.addWidget(tags_label)

        self.text_tags_slicer_host = QWidget()
        self.text_tags_slicer_grid = QGridLayout(self.text_tags_slicer_host)
        self.text_tags_slicer_grid.setContentsMargins(0, 0, 0, 0)
        self.text_tags_slicer_grid.setHorizontalSpacing(6)
        self.text_tags_slicer_grid.setVerticalSpacing(6)
        self.text_tags_slicer_scroll = QScrollArea()
        self.text_tags_slicer_scroll.setWidgetResizable(True)
        self.text_tags_slicer_scroll.setWidget(self.text_tags_slicer_host)
        self.text_tags_slicer_scroll.setMinimumHeight(170)
        filters_layout.addWidget(self.text_tags_slicer_scroll, 1)

        buttons_row = QHBoxLayout()
        refresh_tags_button = QPushButton("Obnovit tagy")
        refresh_tags_button.clicked.connect(self.refresh_view)
        buttons_row.addWidget(refresh_tags_button)
        reload_tagy_button = QPushButton("Obnovit tagy.txt")
        reload_tagy_button.clicked.connect(self.refresh_view)
        buttons_row.addWidget(reload_tagy_button)
        clear_selection_button = QPushButton("Vymazat vyber")
        clear_selection_button.clicked.connect(self._clear_tag_selection)
        buttons_row.addWidget(clear_selection_button)
        filters_layout.addLayout(buttons_row)

        self.selection_summary = QLabel("-")
        self.selection_summary.setWordWrap(True)
        filters_layout.addWidget(self.selection_summary)

        results_box = QGroupBox("Vysledne miniatury")
        results_layout = QVBoxLayout(results_box)
        results_help = QLabel(
            "Dvojklik na miniaturu otevre detail. Tlacitka pod nadpisem spusti fullscreen nebo prezentaci."
        )
        results_help.setWordWrap(True)
        results_layout.addWidget(results_help)

        self.results_summary = QLabel("Nalezeno: 0")
        results_layout.addWidget(self.results_summary)

        viewer_buttons_row = QHBoxLayout()
        self.open_button = QPushButton("Otevrit vybranou")
        self.open_button.clicked.connect(self._open_preview_dialog)
        self.open_button.setEnabled(False)
        viewer_buttons_row.addWidget(self.open_button)
        self.fullscreen_button = QPushButton("Fullscreen")
        self.fullscreen_button.clicked.connect(lambda: self._open_preview_dialog(start_fullscreen=True))
        self.fullscreen_button.setEnabled(False)
        viewer_buttons_row.addWidget(self.fullscreen_button)
        self.slideshow_button = QPushButton("Prezentace")
        self.slideshow_button.clicked.connect(self._start_slideshow)
        self.slideshow_button.setEnabled(False)
        viewer_buttons_row.addWidget(self.slideshow_button)
        self.time_tags_button = QPushButton("Datum tagy pro vyfiltrovane")
        self.time_tags_button.clicked.connect(self._open_time_tag_editor_for_filtered)
        self.time_tags_button.setEnabled(False)
        viewer_buttons_row.addWidget(self.time_tags_button)
        viewer_buttons_row.addStretch(1)
        results_layout.addLayout(viewer_buttons_row)

        self.selected_asset_summary = QLabel("Vybrano: -")
        self.selected_asset_summary.setWordWrap(True)
        results_layout.addWidget(self.selected_asset_summary)

        self.thumbnail_list = QListWidget()
        self.thumbnail_list.setViewMode(QListWidget.IconMode)
        self.thumbnail_list.setResizeMode(QListWidget.Adjust)
        self.thumbnail_list.setMovement(QListWidget.Static)
        self.thumbnail_list.setIconSize(THUMBNAIL_SIZE)
        self.thumbnail_list.setSpacing(10)
        self.thumbnail_list.setUniformItemSizes(True)
        self.thumbnail_list.setWordWrap(True)
        self.thumbnail_list.setSelectionMode(QListWidget.SingleSelection)
        self.thumbnail_list.itemSelectionChanged.connect(self._on_thumbnail_selection_changed)
        self.thumbnail_list.itemDoubleClicked.connect(lambda _item: self._open_preview_dialog())
        results_layout.addWidget(self.thumbnail_list, 1)

        root_layout.addWidget(filters_box, 1)
        root_layout.addWidget(results_box, 2)

    def refresh_view(self) -> None:
        selected_text_tag_names = set(self._selected_text_tag_names())
        selected_year_values = set(self._selected_year_values())
        selected_month_values = set(self._selected_month_values())
        self.tags_by_id = {tag.id: tag for tag in self.context.tag_repository.list_tags()}
        self.tags_by_name_casefold = {tag.name.casefold(): tag for tag in self.tags_by_id.values()}
        self.year_tag_names_by_value = _build_year_tag_map(self.tags_by_id.values())
        selected_year_values = {
            year_value for year_value in selected_year_values if year_value in self.year_tag_names_by_value
        }
        self.month_tag_names_by_value, self.month_tag_names_by_year_month = _build_month_tag_maps(
            self.tags_by_id.values()
        )
        selected_month_values = {
            month_value for month_value in selected_month_values if month_value in self.month_tag_names_by_value
        }
        self._rebuild_year_slicer(selected_year_values)
        self._rebuild_month_slicer(selected_month_values)

        self.filter_tagy_shortcuts = load_tagy_shortcuts(self.context.paths.tagy_path)
        self.filter_tag_names = _build_filter_tag_names(self.filter_tagy_shortcuts)
        self.filter_tags_from_tagy = bool(self.filter_tag_names)
        if not self.filter_tag_names:
            self.filter_tag_names = sorted((tag.name for tag in self.tags_by_id.values()), key=str.casefold)
        self.filter_tag_names = [name for name in self.filter_tag_names if not _is_time_tag_name(name)]
        self._rebuild_text_tag_slicer(selected_text_tag_names)
        self._refresh_results()

    def _clear_tag_selection(self) -> None:
        for button in self.year_slicer_buttons.values():
            button.blockSignals(True)
            button.setChecked(False)
            button.blockSignals(False)
        for button in self.month_slicer_buttons.values():
            button.blockSignals(True)
            button.setChecked(False)
            button.blockSignals(False)
        for button in self.text_tag_slicer_buttons.values():
            button.blockSignals(True)
            button.setChecked(False)
            button.blockSignals(False)
        self._refresh_results()

    def _refresh_results(self) -> None:
        date_tag_names = self._selected_date_tag_names()
        text_tag_names = self._selected_text_tag_names()
        selected_tag_names = sorted(set(date_tag_names + text_tag_names), key=str.casefold)
        missing_tag_names: list[str] = []

        filter_groups: list[tuple[str, list[str]]] = []
        if date_tag_names:
            filter_groups.append(("datum", date_tag_names))
        if text_tag_names:
            filter_groups.append(("tagy", text_tag_names))

        if not filter_groups:
            assets = self.context.asset_repository.list_by_effective_tag_ids(
                [],
                require_all=False,
                photos_only=True,
            )
        else:
            base_assets: list[Asset] = []
            matching_ids: set[int] | None = None

            for index, (_group_name, group_tag_names) in enumerate(filter_groups):
                group_tag_ids, group_missing_names = self._resolve_selected_tag_ids(group_tag_names)
                missing_tag_names.extend(group_missing_names)
                if not group_tag_ids:
                    matching_ids = set()
                    break

                group_assets = self.context.asset_repository.list_by_effective_tag_ids(
                    group_tag_ids,
                    require_all=False,
                    photos_only=True,
                )
                group_ids = {asset.id for asset in group_assets}
                if index == 0:
                    base_assets = group_assets
                    matching_ids = set(group_ids)
                else:
                    assert matching_ids is not None
                    matching_ids &= group_ids

                if not matching_ids:
                    break

            if matching_ids is None:
                assets = []
            else:
                assets = [asset for asset in base_assets if asset.id in matching_ids]

        self.filtered_assets = assets
        self.assets_by_id = {asset.id: asset for asset in assets}
        self._render_thumbnail_results(assets)

        if selected_tag_names:
            base_text = f"Vybrane filtry (AND mezi skupinami): {', '.join(selected_tag_names)}"
            if missing_tag_names:
                base_text += f" | Mimo DB: {', '.join(missing_tag_names)}"
            self.selection_summary.setText(base_text)
        else:
            source_label = "tagy.txt" if self.filter_tags_from_tagy else "DB"
            self.selection_summary.setText(
                f"Vybrane tagy: zadne (zobrazuji se vsechny naskenovane fotky). Zdroj picklistu: {source_label}."
            )
        self.results_summary.setText(f"Nalezeno fotek: {len(assets)}")
        self.time_tags_button.setEnabled(bool(assets))
        self._on_thumbnail_selection_changed()

    def _render_thumbnail_results(self, assets: list[Asset]) -> None:
        self.thumbnail_list.clear()
        for asset in assets:
            item = QListWidgetItem(self._build_thumbnail_icon(asset), self._format_asset_tile_text(asset))
            item.setData(Qt.UserRole, asset.id)
            item.setToolTip(asset.relative_path)
            self.thumbnail_list.addItem(item)
        if self.thumbnail_list.count() > 0:
            self.thumbnail_list.setCurrentRow(0)

    @staticmethod
    def _build_thumbnail_icon(asset: Asset) -> QIcon:
        pixmap = QPixmap(asset.absolute_path)
        if pixmap.isNull():
            return QIcon(_placeholder_thumbnail())
        scaled = pixmap.scaled(THUMBNAIL_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QIcon(scaled)

    @staticmethod
    def _format_asset_tile_text(asset: Asset) -> str:
        return asset.file_name

    def _selected_year_values(self) -> list[str]:
        return sorted(
            [year_value for year_value, button in self.year_slicer_buttons.items() if button.isChecked()],
            key=int,
            reverse=True,
        )

    def _selected_month_values(self) -> list[str]:
        return sorted(
            [month_value for month_value, button in self.month_slicer_buttons.items() if button.isChecked()],
            key=int,
        )

    def _selected_text_tag_names(self) -> list[str]:
        return sorted(
            [tag_name for tag_name, button in self.text_tag_slicer_buttons.items() if button.isChecked()],
            key=str.casefold,
        )

    def _rebuild_year_slicer(self, selected_year_values: set[str]) -> None:
        self._clear_grid_layout(self.year_slicer_grid)
        self.year_slicer_buttons = {}

        year_values = sorted(self.year_tag_names_by_value, key=int, reverse=True)
        if not year_values:
            placeholder = QLabel("Zadne rokove tagy v DB.")
            placeholder.setStyleSheet("color: #6b7280;")
            self.year_slicer_grid.addWidget(placeholder, 0, 0)
            return

        columns = 4
        for index, year_value in enumerate(year_values):
            button = self._create_slicer_button(year_value)
            button.setChecked(year_value in selected_year_values)
            button.setToolTip(self.year_tag_names_by_value[year_value])
            button.clicked.connect(lambda checked, value=year_value: self._on_year_slicer_clicked(value, checked))
            self.year_slicer_buttons[year_value] = button
            row = index // columns
            column = index % columns
            self.year_slicer_grid.addWidget(button, row, column)

    def _rebuild_month_slicer(self, selected_month_values: set[str]) -> None:
        self._clear_grid_layout(self.month_slicer_grid)
        self.month_slicer_buttons = {}

        month_values = [f"{month:02d}" for month in range(1, 13)]
        columns = 6
        for index, month_value in enumerate(month_values):
            button = self._create_slicer_button(month_value)
            tag_name = self.month_tag_names_by_value.get(month_value)
            is_available = tag_name is not None
            button.setEnabled(is_available)
            if is_available:
                button.setToolTip(", ".join(tag_name))
                button.setChecked(month_value in selected_month_values)
            else:
                button.setToolTip("Mesic neni v DB dostupny.")
            button.clicked.connect(lambda checked, value=month_value: self._on_month_slicer_clicked(value, checked))
            self.month_slicer_buttons[month_value] = button
            row = index // columns
            column = index % columns
            self.month_slicer_grid.addWidget(button, row, column)

    def _on_year_slicer_clicked(self, year_value: str, checked: bool) -> None:
        self._refresh_results()

    def _on_month_slicer_clicked(self, month_value: str, checked: bool) -> None:
        self._refresh_results()

    def _rebuild_text_tag_slicer(self, selected_text_tag_names: set[str]) -> None:
        self._clear_grid_layout(self.text_tags_slicer_grid)
        self.text_tag_slicer_buttons = {}

        if not self.filter_tag_names:
            placeholder = QLabel("V tagy.txt nejsou definovane textove tagy.")
            placeholder.setStyleSheet("color: #6b7280;")
            self.text_tags_slicer_grid.addWidget(placeholder, 0, 0)
            return

        columns = 2
        for index, tag_name in enumerate(self.filter_tag_names):
            missing_in_db = self.tags_by_name_casefold.get(tag_name.casefold()) is None
            button = self._create_slicer_button(tag_name, missing_in_db=missing_in_db)
            button.setChecked(tag_name in selected_text_tag_names)
            if missing_in_db:
                button.setToolTip("Tag zatim neni v DB.")
            button.clicked.connect(lambda checked, value=tag_name: self._on_text_tag_slicer_clicked(value, checked))
            self.text_tag_slicer_buttons[tag_name] = button
            row = index // columns
            column = index % columns
            self.text_tags_slicer_grid.addWidget(button, row, column)

    def _on_text_tag_slicer_clicked(self, tag_name: str, checked: bool) -> None:
        self._refresh_results()

    @staticmethod
    def _create_slicer_button(text: str, missing_in_db: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setCheckable(True)
        button.setProperty("missingInDb", "true" if missing_in_db else "false")
        button.setStyleSheet(SLICER_BUTTON_STYLE)
        return button

    @staticmethod
    def _clear_grid_layout(layout: QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _selected_date_tag_names(self) -> list[str]:
        names: list[str] = []
        selected_year_values = self._selected_year_values()
        selected_month_values = self._selected_month_values()

        if selected_month_values:
            if selected_year_values:
                for selected_year in selected_year_values:
                    for selected_month in selected_month_values:
                        month_tag_name = self.month_tag_names_by_year_month.get((selected_year, selected_month))
                        if month_tag_name is not None:
                            names.append(month_tag_name)
                            continue
                        names.append(f"mesic:{selected_year}-{selected_month}")
            else:
                for selected_month in selected_month_values:
                    month_tag_names = self.month_tag_names_by_value.get(selected_month, [])
                    names.extend(month_tag_names)
        else:
            for selected_year in selected_year_values:
                year_tag_name = self.year_tag_names_by_value.get(selected_year)
                if year_tag_name:
                    names.append(year_tag_name)
        return sorted(set(names), key=str.casefold)

    def _selected_tag_names(self) -> list[str]:
        names = self._selected_date_tag_names()
        names.extend(self._selected_text_tag_names())
        return sorted(set(names), key=str.casefold)

    def _resolve_selected_tag_ids(self, selected_tag_names: list[str]) -> tuple[list[int], list[str]]:
        tag_ids: list[int] = []
        missing: list[str] = []
        for tag_name in selected_tag_names:
            resolved = self.tags_by_name_casefold.get(tag_name.casefold())
            if resolved is None:
                missing.append(tag_name)
                continue
            tag_ids.append(resolved.id)
        return sorted(set(tag_ids)), missing

    def _selected_asset_index(self) -> int:
        item = self.thumbnail_list.currentItem()
        if item is None:
            return 0
        selected_asset_id = item.data(Qt.UserRole)
        if selected_asset_id is None:
            return 0
        selected_asset_id = int(selected_asset_id)
        for index, asset in enumerate(self.filtered_assets):
            if asset.id == selected_asset_id:
                return index
        return 0

    def _selected_asset(self) -> Asset | None:
        if not self.filtered_assets:
            return None
        return self.filtered_assets[self._selected_asset_index()]

    def _on_thumbnail_selection_changed(self) -> None:
        asset = self._selected_asset()
        has_asset = asset is not None
        self.open_button.setEnabled(has_asset)
        self.fullscreen_button.setEnabled(has_asset)
        self.slideshow_button.setEnabled(has_asset)
        if not has_asset:
            self.selected_asset_summary.setText("Vybrano: -")
            return
        assert asset is not None
        self.selected_asset_summary.setText(
            f"Vybrano: {self._format_asset_tile_text(asset)} [{asset.relative_path}]"
        )

    def _open_preview_dialog(self, start_fullscreen: bool = False, start_slideshow: bool = False) -> None:
        if not self.filtered_assets:
            QMessageBox.information(self, "Prohlizec", "Aktualni filtr nema zadne fotky.")
            return
        start_index = self._selected_asset_index()
        if self.preview_dialog is None:
            self.preview_dialog = AlbumPreviewDialog(
                context=self.context,
                on_asset_updated=self._on_preview_asset_updated,
                parent=self,
            )
        self.preview_dialog.open_assets(
            assets=self.filtered_assets,
            start_index=start_index,
            start_fullscreen=start_fullscreen,
            start_slideshow=start_slideshow,
        )

    def _start_slideshow(self) -> None:
        self._open_preview_dialog(start_fullscreen=True, start_slideshow=True)

    def _open_time_tag_editor_for_filtered(self) -> None:
        if not self.filtered_assets:
            QMessageBox.information(self, "Datum tagy", "Aktualni filtr nema zadne fotky.")
            return

        scope_label = f"{len(self.filtered_assets)} vyfiltrovanych fotek"
        dialog = TimeTagEditorDialog(scope_label=scope_label, allow_subfolders=False, parent=self)
        if dialog.exec() == 0:
            return

        mode, year, month, _ = dialog.selection()
        asset_ids = [asset.id for asset in self.filtered_assets]
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
            return

        self.refresh_view()
        QMessageBox.information(self, "Datum tagy", summary.message)

    def _on_preview_asset_updated(self, updated_asset: Asset) -> None:
        self.assets_by_id[updated_asset.id] = updated_asset
        for index, asset in enumerate(self.filtered_assets):
            if asset.id != updated_asset.id:
                continue
            self.filtered_assets[index] = updated_asset
            break
        for row in range(self.thumbnail_list.count()):
            item = self.thumbnail_list.item(row)
            if item is None:
                continue
            asset_id = item.data(Qt.UserRole)
            if asset_id is None or int(asset_id) != updated_asset.id:
                continue
            item.setText(self._format_asset_tile_text(updated_asset))
            break
        self._on_thumbnail_selection_changed()


def _placeholder_thumbnail() -> QPixmap:
    pixmap = QPixmap(THUMBNAIL_SIZE)
    pixmap.fill(QColor("#e5e7eb"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QColor("#4b5563"))
    painter.drawRect(8, 8, THUMBNAIL_SIZE.width() - 16, THUMBNAIL_SIZE.height() - 16)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "NO PREVIEW")
    painter.end()
    return pixmap


def _is_time_tag_name(tag_name: str) -> bool:
    normalized = tag_name.strip()
    return YEAR_TAG_RE.match(normalized) is not None or MONTH_TAG_RE.match(normalized) is not None


def _build_year_tag_map(tags: Iterable[Tag]) -> dict[str, str]:
    result: dict[str, str] = {}
    for tag in tags:
        normalized = tag.name.strip()
        match = YEAR_TAG_RE.match(normalized)
        if match is None:
            continue
        year_value = match.group(1)
        if year_value not in result:
            result[year_value] = normalized
    return result


def _build_month_tag_maps(tags: Iterable[Tag]) -> tuple[dict[str, list[str]], dict[tuple[str, str], str]]:
    by_month: dict[str, list[str]] = {}
    by_year_month: dict[tuple[str, str], str] = {}

    for tag in tags:
        normalized = tag.name.strip()
        match = MONTH_TAG_RE.match(normalized)
        if match is None:
            continue
        year_value, month_value = match.groups()
        bucket = by_month.setdefault(month_value, [])
        bucket.append(normalized)
        by_year_month.setdefault((year_value, month_value), normalized)

    for month_value in by_month:
        by_month[month_value] = sorted(by_month[month_value], reverse=True)
    return by_month, by_year_month


def _build_filter_tag_names(shortcuts: TagyShortcuts) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    for letter in sorted(shortcuts.letters):
        tag_name = shortcuts.letters[letter].strip()
        key = tag_name.casefold()
        if not tag_name or key in seen:
            continue
        seen.add(key)
        names.append(tag_name)

    for key_text in sorted(shortcuts.special_keys):
        tag_name = shortcuts.special_keys[key_text].strip()
        key = tag_name.casefold()
        if not tag_name or key in seen:
            continue
        seen.add(key)
        names.append(tag_name)

    for letter, digit in sorted(shortcuts.subcategories):
        tag_name = shortcuts.subcategories[(letter, digit)].strip()
        key = tag_name.casefold()
        if not tag_name or key in seen:
            continue
        seen.add(key)
        names.append(tag_name)

    return names


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
