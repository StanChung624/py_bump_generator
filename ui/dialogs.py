"""Reusable dialog helpers for the Qt main window."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)


@dataclass
class PitchDialogResult:
    p0: Tuple[float, float]
    p1: Tuple[float, float]
    x_pitch: float
    y_pitch: float
    diameter: float
    group: int
    z: float
    h: float


@dataclass
class CountDialogResult:
    p0: Tuple[float, float]
    p1: Tuple[float, float]
    x_count: int
    y_count: int
    diameter: float
    group: int
    z: float
    h: float


@dataclass
class ModifyDialogResult:
    group_filter: Optional[int]
    new_value: float


@dataclass
class MoveDialogResult:
    group_filter: Optional[int]
    reference: Tuple[float, float, float]
    target: Tuple[float, float, float]
    keep_original: bool
    new_group: Optional[int]
    new_diameter: Optional[float]


@dataclass
class SubstrateDialogResult:
    p0: Tuple[float, float, float]
    p1: Tuple[float, float, float]


# ---------------------------------------------------------------------------
# Internal helpers


def _pair(parent: QWidget, edits: list[QLineEdit]) -> QWidget:
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    for edit in edits:
        layout.addWidget(edit)
    return container


def _triple(parent: QWidget, edits: list[QLineEdit]) -> QWidget:
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    for edit in edits:
        layout.addWidget(edit)
    return container


# ---------------------------------------------------------------------------
# Public dialog factories


def request_pitch_parameters(parent) -> Optional[PitchDialogResult]:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Create Bumps by Pitch")
    layout = QFormLayout(dlg)

    p0_edits = [QLineEdit(), QLineEdit()]
    p1_edits = [QLineEdit(), QLineEdit()]
    x_pitch_edit = QLineEdit()
    y_pitch_edit = QLineEdit()
    dia_edit = QLineEdit()
    group_edit = QLineEdit()
    z_edit = QLineEdit()
    h_edit = QLineEdit()

    layout.addRow("Lower corner (x0, y0):", _pair(dlg, p0_edits))
    layout.addRow("Upper corner (x1, y1):", _pair(dlg, p1_edits))
    layout.addRow("X pitch:", x_pitch_edit)
    layout.addRow("Y pitch:", y_pitch_edit)
    layout.addRow("Diameter:", dia_edit)
    layout.addRow("Group:", group_edit)
    layout.addRow("Base Z:", z_edit)
    layout.addRow("Height:", h_edit)

    btn_ok = QPushButton("OK")
    btn_cancel = QPushButton("Cancel")
    btn_box = QHBoxLayout()
    btn_box.addWidget(btn_ok)
    btn_box.addWidget(btn_cancel)
    layout.addRow(btn_box)

    result: Optional[PitchDialogResult] = None

    def on_ok():
        nonlocal result
        try:
            p0 = (float(p0_edits[0].text()), float(p0_edits[1].text()))
            p1 = (float(p1_edits[0].text()), float(p1_edits[1].text()))
            x_pitch = float(x_pitch_edit.text())
            y_pitch = float(y_pitch_edit.text())
            dia = float(dia_edit.text())
            group = int(group_edit.text()) if group_edit.text() else 1
            z = float(z_edit.text())
            h = float(h_edit.text())
        except ValueError:
            QMessageBox.warning(parent, "Warning", "Invalid input values.")
            return

        result = PitchDialogResult(p0, p1, x_pitch, y_pitch, dia, group, z, h)
        dlg.accept()

    btn_ok.clicked.connect(on_ok)
    btn_cancel.clicked.connect(dlg.reject)

    if dlg.exec() == QDialog.Accepted:
        return result
    return None


def request_count_parameters(parent) -> Optional[CountDialogResult]:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Create Bumps by Count")
    layout = QFormLayout(dlg)

    p0_edits = [QLineEdit(), QLineEdit()]
    p1_edits = [QLineEdit(), QLineEdit()]
    x_count_edit = QLineEdit()
    y_count_edit = QLineEdit()
    dia_edit = QLineEdit()
    group_edit = QLineEdit()
    z_edit = QLineEdit()
    h_edit = QLineEdit()

    layout.addRow("Lower corner (x0, y0):", _pair(dlg, p0_edits))
    layout.addRow("Upper corner (x1, y1):", _pair(dlg, p1_edits))
    layout.addRow("X count:", x_count_edit)
    layout.addRow("Y count:", y_count_edit)
    layout.addRow("Diameter:", dia_edit)
    layout.addRow("Group:", group_edit)
    layout.addRow("Base Z:", z_edit)
    layout.addRow("Height:", h_edit)

    btn_ok = QPushButton("OK")
    btn_cancel = QPushButton("Cancel")
    btn_box = QHBoxLayout()
    btn_box.addWidget(btn_ok)
    btn_box.addWidget(btn_cancel)
    layout.addRow(btn_box)

    result: Optional[CountDialogResult] = None

    def on_ok():
        nonlocal result
        try:
            p0 = (float(p0_edits[0].text()), float(p0_edits[1].text()))
            p1 = (float(p1_edits[0].text()), float(p1_edits[1].text()))
            x_count = int(x_count_edit.text())
            y_count = int(y_count_edit.text())
            dia = float(dia_edit.text())
            group = int(group_edit.text()) if group_edit.text() else 1
            z = float(z_edit.text())
            h = float(h_edit.text())
        except ValueError:
            QMessageBox.warning(parent, "Warning", "Invalid input values.")
            return

        result = CountDialogResult(p0, p1, x_count, y_count, dia, group, z, h)
        dlg.accept()

    btn_ok.clicked.connect(on_ok)
    btn_cancel.clicked.connect(dlg.reject)

    if dlg.exec() == QDialog.Accepted:
        return result
    return None


def request_modify_value(parent, title: str, value_label: str) -> Optional[ModifyDialogResult]:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    layout = QFormLayout(dlg)

    group_edit = QLineEdit()
    new_value_edit = QLineEdit()
    layout.addRow("Group Filter (optional):", group_edit)
    layout.addRow(value_label, new_value_edit)

    btn_ok = QPushButton("OK")
    btn_cancel = QPushButton("Cancel")
    btn_box = QHBoxLayout()
    btn_box.addWidget(btn_ok)
    btn_box.addWidget(btn_cancel)
    layout.addRow(btn_box)

    result: Optional[ModifyDialogResult] = None

    def on_ok():
        nonlocal result
        try:
            gid = int(group_edit.text()) if group_edit.text() else None
            new_value = float(new_value_edit.text())
        except ValueError:
            QMessageBox.warning(parent, "Warning", "Invalid input values.")
            return

        result = ModifyDialogResult(gid, new_value)
        dlg.accept()

    btn_ok.clicked.connect(on_ok)
    btn_cancel.clicked.connect(dlg.reject)

    if dlg.exec() == QDialog.Accepted:
        return result
    return None


def request_move_parameters(parent) -> Optional[MoveDialogResult]:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Move / Copy Bumps")
    layout = QFormLayout(dlg)

    group_edit = QLineEdit()
    ref_xyz = [QLineEdit(), QLineEdit(), QLineEdit()]
    new_xyz = [QLineEdit(), QLineEdit(), QLineEdit()]
    keep_check = QCheckBox("Keep Original (Copy)")
    new_group_edit = QLineEdit()
    new_diam_edit = QLineEdit()

    layout.addRow("Group Filter (optional):", group_edit)
    layout.addRow("Reference Point (x,y,z):", _triple(dlg, ref_xyz))
    layout.addRow("Target Point (x,y,z):", _triple(dlg, new_xyz))
    layout.addRow(keep_check)
    layout.addRow("New Group (copy):", new_group_edit)
    layout.addRow("New Diameter (copy):", new_diam_edit)

    btn_ok = QPushButton("OK")
    btn_cancel = QPushButton("Cancel")
    btn_box = QHBoxLayout()
    btn_box.addWidget(btn_ok)
    btn_box.addWidget(btn_cancel)
    layout.addRow(btn_box)

    result: Optional[MoveDialogResult] = None

    def on_ok():
        nonlocal result
        try:
            reference = tuple(float(edit.text()) for edit in ref_xyz)
            target = tuple(float(edit.text()) for edit in new_xyz)
            if len(reference) != 3 or len(target) != 3:
                raise ValueError
            group_filter = int(group_edit.text()) if group_edit.text() else None
            new_group = int(new_group_edit.text()) if new_group_edit.text() else None
            new_diameter = float(new_diam_edit.text()) if new_diam_edit.text() else None
        except ValueError:
            QMessageBox.warning(parent, "Warning", "Invalid input values.")
            return

        result = MoveDialogResult(
            group_filter,
            reference,
            target,
            keep_check.isChecked(),
            new_group,
            new_diameter,
        )
        dlg.accept()

    btn_ok.clicked.connect(on_ok)
    btn_cancel.clicked.connect(dlg.reject)

    if dlg.exec() == QDialog.Accepted:
        return result
    return None


def request_substrate_box(parent) -> Optional[SubstrateDialogResult]:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Set Substrate Box Coordinates")
    layout = QFormLayout(dlg)

    p0_edits = [QLineEdit(), QLineEdit(), QLineEdit()]
    p1_edits = [QLineEdit(), QLineEdit(), QLineEdit()]
    layout.addRow("Lower corner (x0, y0, z0):", _triple(dlg, p0_edits))
    layout.addRow("Upper corner (x1, y1, z1):", _triple(dlg, p1_edits))

    btn_ok = QPushButton("OK")
    btn_cancel = QPushButton("Cancel")
    btn_box = QHBoxLayout()
    btn_box.addWidget(btn_ok)
    btn_box.addWidget(btn_cancel)
    layout.addRow(btn_box)

    result: Optional[SubstrateDialogResult] = None

    def on_ok():
        nonlocal result
        try:
            p0 = tuple(float(edit.text()) for edit in p0_edits)
            p1 = tuple(float(edit.text()) for edit in p1_edits)
            if len(p0) != 3 or len(p1) != 3:
                raise ValueError
        except ValueError:
            QMessageBox.warning(parent, "Warning", "Invalid input values.")
            return

        result = SubstrateDialogResult(p0, p1)
        dlg.accept()

    btn_ok.clicked.connect(on_ok)
    btn_cancel.clicked.connect(dlg.reject)

    if dlg.exec() == QDialog.Accepted:
        return result
    return None
