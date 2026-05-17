from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from photos_tagger.bootstrap import ApplicationContext


class AlbumsView(QWidget):
    def __init__(self, context: ApplicationContext) -> None:
        super().__init__()
        self.context = context
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(16)

        albums_box = QGroupBox("Alba")
        albums_layout = QVBoxLayout(albums_box)
        albums_list = QListWidget()
        for item in (
            "Top 50 za rok 2025",
            "Rodina a nejlepší fotky",
            "Itálie 2025",
            "Eventy: letní dovolené",
        ):
            albums_list.addItem(item)
        albums_layout.addWidget(albums_list)

        buttons_row = QHBoxLayout()
        for label in ("Nové statické album", "Nové smart album", "Export"):
            button = QPushButton(label)
            button.clicked.connect(self._show_stub_message)
            buttons_row.addWidget(button)
        albums_layout.addLayout(buttons_row)

        detail_box = QGroupBox("Pravidla smart alba")
        detail_layout = QVBoxLayout(detail_box)
        detail_text = QTextEdit()
        detail_text.setReadOnly(True)
        detail_text.setPlainText(
            '{\n'
            '  "operator": "and",\n'
            '  "conditions": [\n'
            '    {"field": "effective_tags", "op": "contains", "value": "tema:rodina"},\n'
            '    {"field": "effective_tags", "op": "contains", "value": "kvalita:top"},\n'
            '    {"field": "captured_at", "op": "between", "value": ["2025-01-01", "2025-12-31"]},\n'
            '    {"field": "place.country_code", "op": "=", "value": "IT"},\n'
            '    {"field": "effective_tags", "op": "not_contains", "value": "stav:mazat"}\n'
            '  ]\n'
            '}'
        )
        detail_layout.addWidget(QLabel("Smart albumy budou vyhodnocované nad efektivními tagy, datem, místem a ratingem."))
        detail_layout.addWidget(detail_text)

        root_layout.addWidget(albums_box, 1)
        root_layout.addWidget(detail_box, 2)

    def _show_stub_message(self) -> None:
        QMessageBox.information(
            self,
            "Skeleton",
            "V další iteraci sem patří AlbumService, builder pravidel a export výběru do cílové složky.",
        )
