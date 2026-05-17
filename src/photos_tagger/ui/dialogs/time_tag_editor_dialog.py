from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)


class TimeTagEditorDialog(QDialog):
    def __init__(
        self,
        scope_label: str,
        allow_subfolders: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Datum tagy (rok/mesic)")
        self.resize(440, 320)

        self._radio_auto = QRadioButton("Auto z metadata")
        self._radio_manual_year_month = QRadioButton("Manualne nastavit rok i mesic")
        self._radio_manual_year_only = QRadioButton("Manualne nastavit jen rok")
        self._radio_auto.setChecked(True)

        current_year = datetime.now().year
        self._year_input = QSpinBox()
        self._year_input.setRange(1, 9999)
        self._year_input.setValue(current_year)

        self._month_input = QComboBox()
        for month in range(1, 13):
            self._month_input.addItem(f"{month:02d}", month)

        self._apply_to_subfolders = QCheckBox("Aplikovat i na podslozky")
        self._apply_to_subfolders.setVisible(allow_subfolders)

        self._build_ui(scope_label)
        self._wire_events()
        self._update_input_state()

    def selection(self) -> tuple[str, int | None, int | None, bool]:
        apply_to_subfolders = self._apply_to_subfolders.isChecked() and self._apply_to_subfolders.isVisible()
        if self._radio_auto.isChecked():
            return "auto", None, None, apply_to_subfolders
        year = int(self._year_input.value())
        if self._radio_manual_year_only.isChecked():
            return "manual", year, None, apply_to_subfolders
        month = int(self._month_input.currentData())
        return "manual", year, month, apply_to_subfolders

    def _build_ui(self, scope_label: str) -> None:
        root_layout = QVBoxLayout(self)

        intro = QLabel(
            f"Nastav, jak se maji pro vyber '{scope_label}' priradit datum tagy. "
            "Spravovane tagy: rok:YYYY a mesic:YYYY-MM."
        )
        intro.setWordWrap(True)
        root_layout.addWidget(intro)

        mode_box = QGroupBox("Rezim")
        mode_layout = QVBoxLayout(mode_box)
        mode_layout.addWidget(self._radio_auto)
        mode_layout.addWidget(self._radio_manual_year_month)
        mode_layout.addWidget(self._radio_manual_year_only)
        root_layout.addWidget(mode_box)

        values_box = QGroupBox("Manualni hodnota")
        values_layout = QFormLayout(values_box)
        values_layout.addRow("Rok:", self._year_input)
        values_layout.addRow("Mesic:", self._month_input)
        root_layout.addWidget(values_box)
        root_layout.addWidget(self._apply_to_subfolders)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        root_layout.addWidget(button_box)

    def _wire_events(self) -> None:
        self._radio_auto.toggled.connect(self._update_input_state)
        self._radio_manual_year_month.toggled.connect(self._update_input_state)
        self._radio_manual_year_only.toggled.connect(self._update_input_state)

    def _update_input_state(self) -> None:
        is_auto = self._radio_auto.isChecked()
        is_year_only = self._radio_manual_year_only.isChecked()
        self._year_input.setEnabled(not is_auto)
        self._month_input.setEnabled(not is_auto and not is_year_only)
