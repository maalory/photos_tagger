from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from photos_tagger.tagging import SHORTCUT_KEYS, ShortcutBinding


class ShortcutEditorDialog(QDialog):
    def __init__(self, bindings: list[ShortcutBinding], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rychle tagy")
        self.resize(420, 420)
        self._inputs: dict[str, QLineEdit] = {}
        self._build_ui(bindings)

    def values(self) -> dict[str, str | None]:
        return {
            key_sequence: (line_edit.text().strip() or None)
            for key_sequence, line_edit in self._inputs.items()
        }

    def _build_ui(self, bindings: list[ShortcutBinding]) -> None:
        root_layout = QVBoxLayout(self)

        intro = QLabel(
            "Vypln tag pro jednotlive klavesy 1..0. Prazdne pole znamena, ze klavesa nebude nic prirazovat."
        )
        intro.setWordWrap(True)
        root_layout.addWidget(intro)

        form_layout = QFormLayout()
        binding_map = {binding.key_sequence: binding.tag_name or "" for binding in bindings}
        for key_sequence in SHORTCUT_KEYS:
            line_edit = QLineEdit(binding_map.get(key_sequence, ""))
            line_edit.setPlaceholderText("napr. rodina nebo kvalita:top")
            line_edit.setClearButtonEnabled(True)
            self._inputs[key_sequence] = line_edit
            form_layout.addRow(f"{key_sequence}:", line_edit)
        root_layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        root_layout.addWidget(button_box)
