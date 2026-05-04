from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QVBoxLayout


class FolderTagEditorDialog(QDialog):
    def __init__(self, folder_label: str, current_tags: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tagy slozky")
        self.resize(460, 360)
        self._editor = QPlainTextEdit()
        self._build_ui(folder_label, current_tags)

    def values(self) -> list[str]:
        return [line.strip() for line in self._editor.toPlainText().splitlines()]

    def _build_ui(self, folder_label: str, current_tags: list[str]) -> None:
        root_layout = QVBoxLayout(self)

        intro = QLabel(
            f"Uprav tagy pro slozku '{folder_label}'. Kazdy tag zapis na samostatny radek. Prazdny seznam znamena, ze slozka nebude mit zadne vlastni tagy."
        )
        intro.setWordWrap(True)
        root_layout.addWidget(intro)

        self._editor.setPlaceholderText("napr. rodina\ndovolena\nrok:2024")
        self._editor.setPlainText("\n".join(current_tags))
        root_layout.addWidget(self._editor, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        root_layout.addWidget(button_box)
