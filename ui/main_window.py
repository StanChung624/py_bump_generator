from __future__ import annotations

import shutil
from pathlib import Path
from typing import Tuple, Callable

import h5py
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from VBump.Basic import to_csv
from VBump.CreateRectangularArea import (
    create_rectangular_area_XY_by_number_to_hdf5,
    create_rectangular_area_XY_by_pitch_to_hdf5,
)
from VBump.ExportVTP import write_vbumps_vtp
from VBump.ExportWDL import (
    vbump_2_wdl_as_airtrap,
    vbump_2_wdl_as_weldline,
    vbump_2_wdl_as_weldline_AABB,
)
from VBump.VBumpPlot import plot_vbumps, plot_vbumps_aabb
from ui.dialogs import (
    request_count_parameters,
    request_modify_value,
    request_move_parameters,
    request_pitch_parameters,
    request_substrate_box,
)
from ui.logic import VBumpLogic

PLOT_MATERIALIZE_THRESHOLD = 1_000_000

class VBumpUI(QMainWindow):
    def __init__(self, logic: VBumpLogic):
        super().__init__()
        self.logic = logic
        self.setWindowTitle("Virtual Bump CSV Generator (GUI)")
        self.setMinimumSize(1000, 700)

        self.substrate_p0: Tuple[float, float, float] | None = None
        self.substrate_p1: Tuple[float, float, float] | None = None

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setCentralWidget(central)

        # UI Construction (abbreviated for clarity, but includes all elements)
        file_box = QGroupBox("📂 File Operations")
        flayout = QHBoxLayout(file_box)
        self.btn_load = QPushButton("Load")
        self.btn_save = QPushButton("Save")
        flayout.addWidget(self.btn_load)
        flayout.addWidget(self.btn_save)
        layout.addWidget(file_box)

        create_box = QGroupBox("📐 Create Rectangular Area")
        form_create = QFormLayout(create_box)
        self.btn_create_pitch = QPushButton("Generate by Pitch")
        self.btn_create_count = QPushButton("Generate by Count")
        form_create.addRow(self.btn_create_pitch, self.btn_create_count)
        layout.addWidget(create_box)

        mod_box = QGroupBox("🔧 Modify / Move")
        mlayout = QFormLayout(mod_box)
        self.btn_modify_diam = QPushButton("Modify Diameter")
        self.btn_modify_height = QPushButton("Modify Height")
        self.btn_move = QPushButton("Move / Copy Bumps")
        self.btn_delete_group = QPushButton("Delete Group")
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_modify_diam)
        btn_row.addWidget(self.btn_modify_height)
        btn_row.addWidget(self.btn_move)
        btn_row.addWidget(self.btn_delete_group)
        mlayout.addRow(btn_row)
        layout.addWidget(mod_box)

        exp_box = QGroupBox("📤 Export / Plot")
        explayout = QHBoxLayout(exp_box)
        self.btn_weldline = QPushButton("Export WDL (Weldline)")
        self.btn_airtrap = QPushButton("Export WDL (Airtrap)")
        self.btn_vtp = QPushButton("Export VTP")
        self.btn_plot = QPushButton("Plot")
        explayout.addWidget(self.btn_weldline)
        explayout.addWidget(self.btn_airtrap)
        explayout.addWidget(self.btn_vtp)
        explayout.addWidget(self.btn_plot)
        layout.addWidget(exp_box)

        layout.addWidget(QLabel("🧾 Log Output:"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        self.plot_box = QGroupBox("📊 Plot Preview")
        plot_layout = QVBoxLayout(self.plot_box)
        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        plot_layout.addWidget(self.canvas)

        view_btn_layout = QHBoxLayout()
        self.btn_view_top = QPushButton("Top")
        self.btn_view_front = QPushButton("Front")
        self.btn_view_right = QPushButton("Right")
        self.btn_view_default = QPushButton("Default")
        view_btn_layout.addWidget(self.btn_view_top)
        view_btn_layout.addWidget(self.btn_view_front)
        view_btn_layout.addWidget(self.btn_view_right)
        view_btn_layout.addWidget(self.btn_view_default)
        plot_layout.addLayout(view_btn_layout)

        def set_view(elev, azim):
            if not self.figure.axes:
                QMessageBox.information(self, "Info", "Please plot something first.")
                return
            ax = self.figure.axes[0]
            ax.view_init(elev=elev, azim=azim)
            self.canvas.draw()

        self.btn_view_top.clicked.connect(lambda: set_view(90, -90))
        self.btn_view_front.clicked.connect(lambda: set_view(0, -90))
        self.btn_view_right.clicked.connect(lambda: set_view(0, 0))
        self.btn_view_default.clicked.connect(lambda: set_view(30, -60))

        bottom_split = QHBoxLayout()
        bottom_split.addWidget(self.log_view, stretch=1)
        bottom_split.addWidget(self.plot_box, stretch=2)
        layout.addLayout(bottom_split, stretch=1)

        # Signal connections
        self.btn_load.clicked.connect(self.load_csv)
        self.btn_save.clicked.connect(self.save_csv)
        self.btn_create_pitch.clicked.connect(self.create_pitch)
        self.btn_create_count.clicked.connect(self.create_count)
        self.btn_modify_diam.clicked.connect(self.modify_diameter)
        self.btn_modify_height.clicked.connect(self.modify_height)
        self.btn_move.clicked.connect(self.move_bumps)
        self.btn_delete_group.clicked.connect(self.delete_group)
        self.btn_weldline.clicked.connect(self.export_weldline)
        self.btn_airtrap.clicked.connect(self.export_airtrap)
        self.btn_vtp.clicked.connect(self.export_vtp)
        self.btn_plot.clicked.connect(self.plot_aabb)

        self.log("🐢 Virtual Bump Generator (GUI mode) started.")
        self.log("🔁 Proxy mode is enabled for all operations.")

    def log(self, text):
        self.log_view.append(text)
        self.log_view.moveCursor(QTextCursor.End)
        QApplication.processEvents()

    def _ensure_proxy_loaded(self) -> bool:
        if not self.logic.proxy_h5_path:
            QMessageBox.warning(self, "Warning", "No bumps loaded.")
            return False
        return True

    def load_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "CSV/h5/DXF/VBump Files (*.csv *.CSV *.hdf5 *h5 *.vbump *.VBUMP *.dxf *.DXF);;All Files (*)",
        )
        if not path:
            return

        try:
            if path.lower().endswith(".dxf"):
                from PySide6.QtWidgets import QInputDialog
                group, ok = QInputDialog.getInt(self, "DXF Import", "Group ID:", 1, 1, 9999)
                if not ok: return
                height, ok = QInputDialog.getDouble(self, "DXF Import", "Height:", 10.0, -1e9, 1e9, 6)
                if not ok: return
                base_z, ok = QInputDialog.getDouble(self, "DXF Import", "Base Z:", 0.0, -1e9, 1e9, 6)
                if not ok: return
                unit_scale, ok = QInputDialog.getDouble(self, "DXF Import", "Unit scale:", 0.001, 1e-12, 1e12, 9)
                if not ok: return
                incoming_proxy = self.logic.build_proxy_from_dxf(path, group, height, base_z, unit_scale)
                self.log("✅ Loading DXF format and converting to proxy hdf5")
            elif h5py.is_hdf5(path):
                incoming_proxy = self.logic.copy_hdf5_to_proxy(path)
                self.log("✅ Loading hdf5 format (proxy copy)")
            else:
                incoming_proxy = self.logic.build_proxy_from_csv(path)
                self.log("✅ Loading csv format and converting to proxy hdf5")

            reply = QMessageBox.question(
                self, "Reassign Group ID",
                "Do you want to assign a new group ID to the newly loaded bumps?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                from PySide6.QtWidgets import QInputDialog
                new_gid, ok = QInputDialog.getInt(self, "New Group ID", "Enter new group ID:", 1, 1, 9999)
                if ok:
                    incoming_proxy = self.logic.copy_proxy_with_single_group(incoming_proxy, new_gid)
                    self.log(f"🔢 Newly loaded bumps reassigned to group {new_gid}.")

            if self.logic.proxy_h5_path:
                merged = self.logic.merge_proxy_paths([self.logic.proxy_h5_path, incoming_proxy])
                self.logic.replace_proxy(merged, f"✅ Loaded and appended {path} (total {self.logic.current_source_count():,} bumps)")
            else:
                self.logic.replace_proxy(incoming_proxy, f"✅ Loaded {path} ({self.logic.current_source_count():,} bumps)")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def save_csv(self):
        if not self._ensure_proxy_loaded():
            return

        reply = QMessageBox.question(
            self, "Save as HDF5?",
            "Do you want to save the file as HDF5 format?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            path, _ = QFileDialog.getSaveFileName(self, "Save HDF5", "", "HDF5 Files (*.h5 *.hdf5)")
            if path:
                shutil.copy2(self.logic.proxy_h5_path, path)
                self.log(f"💾 Saved proxy HDF5 to {path}")
        else:
            path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
            if path:
                vbumps = self.logic.materialize_current()
                to_csv(path, vbumps)
                self.log(f"💾 Materialized and saved CSV to {path}")

    def create_pitch(self):
        dialog_result = request_pitch_parameters(self)
        if not dialog_result: return
        out_proxy = self.logic.next_proxy_path("create_pitch")
        try:
            written = create_rectangular_area_XY_by_pitch_to_hdf5(
                out_proxy, dialog_result.p0, dialog_result.p1,
                dialog_result.x_pitch, dialog_result.y_pitch,
                dialog_result.diameter, dialog_result.group,
                dialog_result.z, dialog_result.h,
                log_callback=self.log,
            )
            if self.logic.proxy_h5_path:
                merged = self.logic.merge_proxy_paths([self.logic.proxy_h5_path, out_proxy])
                self.logic.replace_proxy(merged, f"📐 Appended {written:,} bumps by pitch in proxy mode")
            else:
                self.logic.replace_proxy(out_proxy, f"📐 Created {written:,} bumps by pitch in proxy mode")
            if self.substrate_p0 and self.substrate_p1: self.plot_aabb()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def create_count(self):
        dialog_result = request_count_parameters(self)
        if not dialog_result: return
        out_proxy = self.logic.next_proxy_path("create_count")
        try:
            written = create_rectangular_area_XY_by_number_to_hdf5(
                out_proxy, dialog_result.p0, dialog_result.p1,
                dialog_result.x_count, dialog_result.y_count,
                dialog_result.diameter, dialog_result.group,
                dialog_result.z, dialog_result.h,
                log_callback=self.log,
            )
            if self.logic.proxy_h5_path:
                merged = self.logic.merge_proxy_paths([self.logic.proxy_h5_path, out_proxy])
                self.logic.replace_proxy(merged, f"📏 Appended {written:,} bumps by count in proxy mode")
            else:
                self.logic.replace_proxy(out_proxy, f"📏 Created {written:,} bumps by count in proxy mode")
            if self.substrate_p0 and self.substrate_p1: self.plot_aabb()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def modify_diameter(self):
        if not self._ensure_proxy_loaded(): return
        dialog_result = request_modify_value(self, "Modify Diameter", "New Diameter:")
        if not dialog_result: return
        gid = dialog_result.group_filter
        new_d = dialog_result.new_value
        def transform(record: dict) -> list[dict]:
            if gid is not None and int(record["group"]) != gid: return [record]
            record["D"] = float(new_d)
            return [record]
        try:
            out_path, written = self.logic.transform_proxy(transform, "modify_diameter")
            self.logic.replace_proxy(out_path, f"🔧 Updated diameter to {new_d} (rows now: {written:,})")
        except Exception as exc: QMessageBox.critical(self, "Error", str(exc))

    def modify_height(self):
        if not self._ensure_proxy_loaded(): return
        dialog_result = request_modify_value(self, "Modify Height", "New Height:")
        if not dialog_result: return
        gid = dialog_result.group_filter
        new_h = dialog_result.new_value
        def transform(record: dict) -> list[dict]:
            if gid is not None and int(record["group"]) != gid: return [record]
            x0, y0, z0 = float(record["x0"]), float(record["y0"]), float(record["z0"])
            x1, y1, z1 = float(record["x1"]), float(record["y1"]), float(record["z1"])
            dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
            length = (dx * dx + dy * dy + dz * dz) ** 0.5
            if length == 0: return [record]
            scale = float(new_h) / length
            record["x1"], record["y1"], record["z1"] = x0 + scale * dx, y0 + scale * dy, z0 + scale * dz
            return [record]
        try:
            out_path, written = self.logic.transform_proxy(transform, "modify_height")
            self.logic.replace_proxy(out_path, f"📐 Updated height to {new_h} (rows now: {written:,})")
            if self.substrate_p0 and self.substrate_p1: self.plot_aabb()
        except Exception as exc: QMessageBox.critical(self, "Error", str(exc))

    def delete_group(self):
        if not self._ensure_proxy_loaded(): return
        from PySide6.QtWidgets import QInputDialog
        gid, ok = QInputDialog.getInt(self, "Delete Group", "Enter group ID to delete:", 0, 1, 9999)
        if not ok: return
        before = self.logic.current_source_count()
        def transform(record: dict) -> list[dict]:
            if int(record["group"]) == gid: return []
            return [record]
        try:
            out_path, written = self.logic.transform_proxy(transform, "delete_group")
            self.logic.replace_proxy(out_path, f"🗑️ Deleted group {gid} ({before - written:,} bumps removed)")
            if self.substrate_p0 and self.substrate_p1: self.plot_aabb()
        except Exception as exc: QMessageBox.critical(self, "Error", str(exc))

    def move_bumps(self):
        if not self._ensure_proxy_loaded(): return
        dialog_result = request_move_parameters(self)
        if not dialog_result: return
        gid, keep, new_g, new_d = dialog_result.group_filter, dialog_result.keep_original, dialog_result.new_group, dialog_result.new_diameter
        delta_u = tuple(t - r for t, r in zip(dialog_result.target, dialog_result.reference))
        auto_group_map = {}
        if keep and gid is None and new_g is None:
            existing = self.logic.get_existing_groups()
            max_group = max(existing) if existing else 0
            with h5py.File(self.logic.proxy_h5_path, "r") as fin:
                dset = fin["vbump"]
                seen = set()
                for start in range(0, int(dset.shape[0]), 1_000_000):
                    end = min(start + 1_000_000, int(dset.shape[0]))
                    for g in dset[start:end]["group"]:
                        gv = int(g)
                        if gv not in seen:
                            seen.add(gv)
                            max_group += 1
                            auto_group_map[gv] = max_group
        def transform(record: dict) -> list[dict]:
            current_gid = int(record["group"])
            if gid is not None and current_gid != gid: return [record]
            moved = dict(record)
            moved["x0"], moved["y0"], moved["z0"] = float(moved["x0"]) + delta_u[0], float(moved["y0"]) + delta_u[1], float(moved["z0"]) + delta_u[2]
            moved["x1"], moved["y1"], moved["z1"] = float(moved["x1"]) + delta_u[0], float(moved["y1"]) + delta_u[1], float(moved["z1"]) + delta_u[2]
            if new_d is not None: moved["D"] = float(new_d)
            if auto_group_map and current_gid in auto_group_map: moved["group"] = int(auto_group_map[current_gid])
            elif new_g is not None: moved["group"] = int(new_g)
            return [record, moved] if keep else [moved]
        try:
            out_path, written = self.logic.transform_proxy(transform, "move_copy")
            msg = f"📤 Move/Copy applied (rows now: {written:,})"
            if auto_group_map: msg = f"📤 Duplicated bumps with auto-groups {', '.join(str(v) for v in sorted(auto_group_map.values()))} (rows now: {written:,})"
            self.logic.replace_proxy(out_path, msg)
            if self.substrate_p0 and self.substrate_p1: self.plot_aabb()
        except Exception as exc: QMessageBox.critical(self, "Error", str(exc))

    def export_weldline(self):
        if not self._ensure_proxy_loaded(): return
        path, _ = QFileDialog.getSaveFileName(self, "Save WDL (weldline)", "", "WDL Files (*.wdl)")
        if not path: return
        vbumps = self.logic.materialize_current()
        if len(vbumps) < 20000: vbump_2_wdl_as_weldline(path, vbumps)
        else: vbump_2_wdl_as_weldline_AABB(path, vbumps)
        self.log(f"🧵 Weldline exported to {path} (materialized {len(vbumps):,} rows)")

    def export_airtrap(self):
        if not self._ensure_proxy_loaded(): return
        path, _ = QFileDialog.getSaveFileName(self, "Save WDL (airtrap)", "", "WDL Files (*.wdl)")
        if not path: return
        vbumps = self.logic.materialize_current()
        vbump_2_wdl_as_airtrap(path, vbumps)
        self.log(f"💨 Airtrap exported to {path} (materialized {len(vbumps):,} rows)")

    def export_vtp(self):
        if not self._ensure_proxy_loaded(): return
        path, _ = QFileDialog.getSaveFileName(self, "Save VTP", "", "VTP Files (*.vtp)")
        if not path: return
        vbumps = self.logic.materialize_current()
        write_vbumps_vtp(vbumps, path)
        self.log(f"🧪 VTP exported to {path} (materialized {len(vbumps):,} rows)")

    def plot_aabb(self):
        if not self._ensure_proxy_loaded(): return
        if not self.set_substrate_box(): return

        self.figure.clear()
        ax = self.figure.add_subplot(111, projection="3d")
        source_count = self.logic.current_source_count()
        if source_count <= PLOT_MATERIALIZE_THRESHOLD:
            vbumps = self.logic.materialize_current()
            if len(vbumps) < 9000: plot_vbumps(vbumps, self.substrate_p0, self.substrate_p1, ax=ax)
            else: plot_vbumps_aabb(vbumps, self.substrate_p0, self.substrate_p1, ax=ax)
            self.log(f"📊 Plot rendered with materialized data ({len(vbumps):,} rows).")
        else:
            plot_vbumps_aabb(self.logic.current_vbumps, self.substrate_p0, self.substrate_p1, ax=ax)
            self.log(f"📊 Plot rendered from proxy markers (source {source_count:,} rows > {PLOT_MATERIALIZE_THRESHOLD:,}).")
        self.canvas.draw()

    def set_substrate_box(self):
        auto_bounds = None
        if self.logic.current_vbumps:
            bounds = self.logic.compute_bounding_box(self.logic.current_vbumps)
            if bounds:
                min_pt, max_pt = bounds
                auto_bounds = (min_pt, (max_pt[0], max_pt[1], max_pt[2] * -1))
        initial = (self.substrate_p0, self.substrate_p1) if self.substrate_p0 and self.substrate_p1 else None
        res = request_substrate_box(self, initial=initial, auto_bounds=auto_bounds)
        if res:
            self.substrate_p0, self.substrate_p1 = res.p0, res.p1
            self.log(f"🧱 Substrate box set to {res.p0} - {res.p1}")
            return True
        return False

    def closeEvent(self, event):
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.setParent(None)
            del self.canvas
        super().closeEvent(event)
