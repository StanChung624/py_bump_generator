"""Reusable dialog helpers for the Qt main window."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
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


@dataclass
class DXFImportDialogResult:
    group: int
    height: float
    base_z: float
    unit_scale: float
    selected_layers: List[str]


# ---------------------------------------------------------------------------
# Internal helpers


def _line_edit(default: str = "") -> QLineEdit:
    """Helper to create a QLineEdit with an optional default value."""
    le = QLineEdit()
    if default:
        le.setText(default)
    return le


def _pair(parent: QWidget, edits: list[QLineEdit]) -> QWidget:
    """Helper to group two QLineEdits horizontally."""
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    for edit in edits:
        layout.addWidget(edit)
    return container


def _triple(parent: QWidget, edits: list[QLineEdit]) -> QWidget:
    """Helper to group three QLineEdits horizontally."""
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    for edit in edits:
        layout.addWidget(edit)
    return container


def _standard_dialog_buttons(parent_dialog: QDialog, layout: QFormLayout) -> Tuple[QPushButton, QPushButton]:
    """Helper to append OK and Cancel buttons to a dialog's form layout."""
    btn_ok = QPushButton("OK")
    btn_cancel = QPushButton("Cancel")
    btn_box = QHBoxLayout()
    btn_box.addWidget(btn_ok)
    btn_box.addWidget(btn_cancel)
    layout.addRow(btn_box)
    
    btn_cancel.clicked.connect(parent_dialog.reject)
    return btn_ok, btn_cancel


# ---------------------------------------------------------------------------
# Public dialog factories


def request_pitch_parameters(parent) -> Optional[PitchDialogResult]:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Create Bumps by Pitch")
    layout = QFormLayout(dlg)

    p0_edits = [_line_edit("0"), _line_edit("0")]
    p1_edits = [_line_edit("100"), _line_edit("100")]
    x_pitch_edit = _line_edit("10")
    y_pitch_edit = _line_edit("10")
    dia_edit = _line_edit("10")
    group_edit = _line_edit("1")
    z_edit = _line_edit("0")
    h_edit = _line_edit("5")

    layout.addRow("Start Point (X, Y):", _pair(dlg, p0_edits))
    layout.addRow("End Point (X, Y):", _pair(dlg, p1_edits))
    layout.addRow("X Pitch:", x_pitch_edit)
    layout.addRow("Y Pitch:", y_pitch_edit)
    layout.addRow("Diameter:", dia_edit)
    layout.addRow("Group:", group_edit)
    layout.addRow("Base Z:", z_edit)
    layout.addRow("Height:", h_edit)

    btn_ok, _btn_cancel = _standard_dialog_buttons(dlg, layout)
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
            QMessageBox.warning(parent, "Warning", "Invalid input values. Please ensure all required fields are numbers.")
            return

        result = PitchDialogResult(p0, p1, x_pitch, y_pitch, dia, group, z, h)
        dlg.accept()

    btn_ok.clicked.connect(on_ok)

    if dlg.exec() == QDialog.Accepted:
        return result
    return None


def request_count_parameters(parent) -> Optional[CountDialogResult]:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Create Bumps by Count")
    layout = QFormLayout(dlg)

    p0_edits = [_line_edit("0"), _line_edit("0")]
    p1_edits = [_line_edit("100"), _line_edit("100")]
    x_count_edit = _line_edit("11")
    y_count_edit = _line_edit("11")
    dia_edit = _line_edit("10")
    group_edit = _line_edit("1")
    z_edit = _line_edit("0")
    h_edit = _line_edit("5")

    layout.addRow("Start Point (X, Y):", _pair(dlg, p0_edits))
    layout.addRow("End Point (X, Y):", _pair(dlg, p1_edits))
    layout.addRow("X Count:", x_count_edit)
    layout.addRow("Y Count:", y_count_edit)
    layout.addRow("Diameter:", dia_edit)
    layout.addRow("Group:", group_edit)
    layout.addRow("Base Z:", z_edit)
    layout.addRow("Height:", h_edit)

    btn_ok, _btn_cancel = _standard_dialog_buttons(dlg, layout)
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
            QMessageBox.warning(parent, "Warning", "Invalid input values. Please ensure counts are integers and other fields are numbers.")
            return

        result = CountDialogResult(p0, p1, x_count, y_count, dia, group, z, h)
        dlg.accept()

    btn_ok.clicked.connect(on_ok)

    if dlg.exec() == QDialog.Accepted:
        return result
    return None


def request_modify_value(parent, title: str, value_label: str) -> Optional[ModifyDialogResult]:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    layout = QFormLayout(dlg)

    group_edit = _line_edit("")
    new_value_edit = _line_edit("10")
    
    layout.addRow("Group Filter (Optional):", group_edit)
    layout.addRow(value_label, new_value_edit)

    btn_ok, _btn_cancel = _standard_dialog_buttons(dlg, layout)
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

    if dlg.exec() == QDialog.Accepted:
        return result
    return None


def request_move_parameters(parent) -> Optional[MoveDialogResult]:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Move / Duplicate Bumps")
    layout = QFormLayout(dlg)

    group_edit = _line_edit("")
    ref_xyz = [_line_edit("0"), _line_edit("0"), _line_edit("0")]
    new_xyz = [_line_edit("10"), _line_edit("0"), _line_edit("0")]
    keep_check = QCheckBox("Keep Original (Duplicate)")
    new_group_edit = _line_edit("")
    new_diam_edit = _line_edit("")

    layout.addRow("Group Filter (Optional):", group_edit)
    layout.addRow("Reference Point (X, Y, Z):", _triple(dlg, ref_xyz))
    layout.addRow("Target Point (X, Y, Z):", _triple(dlg, new_xyz))
    layout.addRow(keep_check)
    layout.addRow("New Group (Duplicate):", new_group_edit)
    layout.addRow("New Diameter (Duplicate):", new_diam_edit)

    btn_ok, _btn_cancel = _standard_dialog_buttons(dlg, layout)
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

    if dlg.exec() == QDialog.Accepted:
        return result
    return None


def request_substrate_box(
    parent,
    *,
    initial: Optional[tuple[tuple[float, float, float], tuple[float, float, float]]] = None,
    auto_bounds: Optional[tuple[tuple[float, float, float], tuple[float, float, float]]] = None,
) -> Optional[SubstrateDialogResult]:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Set Substrate Box Coordinates")
    layout = QFormLayout(dlg)

    p0_edits = [_line_edit(""), _line_edit(""), _line_edit("")]
    p1_edits = [_line_edit(""), _line_edit(""), _line_edit("")]
    layout.addRow("Start Point (X, Y, Z):", _triple(dlg, p0_edits))
    layout.addRow("End Point (X, Y, Z):", _triple(dlg, p1_edits))

    def _populate_fields(values: tuple[tuple[float, float, float], tuple[float, float, float]]) -> None:
        (min_corner, max_corner) = values
        for edit, value in zip(p0_edits, min_corner):
            edit.setText(f"{value:g}")
        for edit, value in zip(p1_edits, max_corner):
            edit.setText(f"{value:g}")

    if initial is not None:
        _populate_fields(initial)

    btn_ok = QPushButton("OK")
    btn_cancel = QPushButton("Cancel")
    btn_auto = QPushButton("Auto Compute")
    btn_auto.setEnabled(auto_bounds is not None)
    
    btn_box = QHBoxLayout()
    btn_box.addWidget(btn_auto)
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

    def on_auto():
        if auto_bounds is None:
            QMessageBox.information(parent, "Info", "No vbumps available to compute bounding box.")
            return
        _populate_fields(auto_bounds)

    btn_auto.clicked.connect(on_auto)
    btn_ok.clicked.connect(on_ok)
    btn_cancel.clicked.connect(dlg.reject)

    if dlg.exec() == QDialog.Accepted:
        return result
    return None


def request_dxf_import_parameters(parent, layers: dict[str, int]) -> Optional[DXFImportDialogResult]:
    dlg = QDialog(parent)
    dlg.setWindowTitle("DXF Import Parameters")
    main_layout = QVBoxLayout(dlg)
    form_layout = QFormLayout()

    group_edit = _line_edit("1")
    height_edit = _line_edit("10.0")
    base_z_edit = _line_edit("0.0")
    unit_scale_edit = _line_edit("0.001")

    form_layout.addRow("Group ID:", group_edit)
    form_layout.addRow("Height:", height_edit)
    form_layout.addRow("Base Z:", base_z_edit)
    form_layout.addRow("Unit scale:", unit_scale_edit)
    main_layout.addLayout(form_layout)

    main_layout.addWidget(QWidget()) # spacer
    main_layout.addWidget(QPushButton("Select Layers to Import:"))
    
    list_widget = QListWidget()
    # Sort layers by name for better UX
    for layer_name in sorted(layers.keys()):
        count = layers[layer_name]
        display_text = f"{layer_name} (counts: {count})"
        item = QListWidgetItem(display_text)
        item.setData(Qt.UserRole, layer_name) # Store original name
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        list_widget.addItem(item)
    main_layout.addWidget(list_widget)

    # Helper buttons for list
    list_buttons = QHBoxLayout()
    btn_all = QPushButton("Select All")
    btn_none = QPushButton("Deselect All")
    list_buttons.addWidget(btn_all)
    list_buttons.addWidget(btn_none)
    main_layout.addLayout(list_buttons)

    def select_all():
        for i in range(list_widget.count()):
            list_widget.item(i).setCheckState(Qt.Checked)

    def select_none():
        for i in range(list_widget.count()):
            list_widget.item(i).setCheckState(Qt.Unchecked)

    btn_all.clicked.connect(select_all)
    btn_none.clicked.connect(select_none)

    btn_ok = QPushButton("OK")
    btn_cancel = QPushButton("Cancel")
    btn_box = QHBoxLayout()
    btn_box.addWidget(btn_ok)
    btn_box.addWidget(btn_cancel)
    main_layout.addLayout(btn_box)

    result: Optional[DXFImportDialogResult] = None

    def on_ok():
        nonlocal result
        selected_layers = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected_layers.append(item.data(Qt.UserRole))
        
        if not selected_layers:
            QMessageBox.warning(dlg, "Warning", "Please select at least one layer.")
            return

        try:
            group = int(group_edit.text())
            height = float(height_edit.text())
            base_z = float(base_z_edit.text())
            unit_scale = float(unit_scale_edit.text())
        except ValueError:
            QMessageBox.warning(dlg, "Warning", "Invalid input values. Please ensure all fields are numbers.")
            return

        result = DXFImportDialogResult(group, height, base_z, unit_scale, selected_layers)
        dlg.accept()

        try:
            group = int(group_edit.text())
            height = float(height_edit.text())
            base_z = float(base_z_edit.text())
            unit_scale = float(unit_scale_edit.text())
        except ValueError:
            QMessageBox.warning(dlg, "Warning", "Invalid input values. Please ensure all fields are numbers.")
            return

        result = DXFImportDialogResult(group, height, base_z, unit_scale, selected_layers)
        dlg.accept()

    btn_ok.clicked.connect(on_ok)
    btn_cancel.clicked.connect(dlg.reject)

    if dlg.exec() == QDialog.Accepted:
        return result
    return None
