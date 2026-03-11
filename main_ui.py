from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Callable, Tuple

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

from VBump.Basic import VBump, VBumpCollection, load_csv, load_hdf5, to_csv, to_hdf5
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
from VBump.DXFImport import DXFVBumpImporter

from ui.dialogs import (
    request_count_parameters,
    request_modify_value,
    request_move_parameters,
    request_pitch_parameters,
    request_substrate_box,
)

PLOT_MATERIALIZE_THRESHOLD = 1_000_000
HDF5_CHUNK_SIZE = 1_000_000


class VBumpUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Virtual Bump CSV Generator (GUI)")
        self.setMinimumSize(1000, 700)

        self.loaded_vbumps: VBumpCollection = VBumpCollection()
        self.current_vbumps: VBumpCollection = VBumpCollection()
        self.substrate_p0: Tuple[float, float, float] | None = None
        self.substrate_p1: Tuple[float, float, float] | None = None
        self.proxy_dir = Path(__file__).resolve().parent / ".proxy_runtime"
        self.proxy_dir.mkdir(parents=True, exist_ok=True)
        self.proxy_h5_path: str | None = None

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setCentralWidget(central)

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

    def _next_proxy_path(self, stem: str) -> str:
        return str((self.proxy_dir / f"{stem}_{uuid.uuid4().hex}.h5").resolve())

    def _ensure_proxy_loaded(self) -> bool:
        if not self.proxy_h5_path:
            QMessageBox.warning(self, "Warning", "No bumps loaded.")
            return False
        return True

    def _compute_bounding_box(self, bumps) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
        points_x: list[float] = []
        points_y: list[float] = []
        points_z: list[float] = []
        for bump in bumps:
            points_x.extend([bump.x0, bump.x1])
            points_y.extend([bump.y0, bump.y1])
            points_z.extend([bump.z0, bump.z1])
        if not points_x:
            return None
        return (
            (min(points_x), min(points_y), min(points_z)),
            (max(points_x), max(points_y), max(points_z)),
        )

    def _set_active_proxy(self, path: str) -> None:
        self.proxy_h5_path = path
        proxy_markers = load_hdf5(path, only_bounding_boxes=True)
        self.current_vbumps = proxy_markers
        self.loaded_vbumps = VBumpCollection(proxy_markers)

    def _build_proxy_from_csv(self, csv_path: str) -> str:
        vbumps = load_csv(csv_path)
        target = self._next_proxy_path("load_csv")
        to_hdf5(target, vbumps, log_callback=self.log)
        return target

    def _build_proxy_from_dxf(self, dxf_path: str) -> str | None:
        from PySide6.QtWidgets import QInputDialog

        group, ok = QInputDialog.getInt(self, "DXF Import", "Group ID:", 1, 1, 9999)
        if not ok:
            return None
        height, ok = QInputDialog.getDouble(self, "DXF Import", "Height:", 10.0, -1e9, 1e9, 6)
        if not ok:
            return None
        base_z, ok = QInputDialog.getDouble(self, "DXF Import", "Base Z:", 0.0, -1e9, 1e9, 6)
        if not ok:
            return None
        unit_scale, ok = QInputDialog.getDouble(
            self,
            "DXF Import",
            "Unit scale (DXF unit -> output unit):",
            0.001,
            1e-12,
            1e12,
            9,
        )
        if not ok:
            return None

        importer = DXFVBumpImporter(unit_scale=unit_scale, base_z=base_z)
        vbumps, report = importer.import_file(dxf_path, group=group, height=height)
        self.log(
            f"✅ DXF parsed: {len(vbumps):,} bumps "
            f"(geometry={report.used_geometry}, diagnostics={report.diagnostics_count})"
        )
        target = self._next_proxy_path("load_dxf")
        to_hdf5(target, vbumps, log_callback=self.log)
        return target

    def _copy_hdf5_to_proxy(self, src_path: str) -> str:
        target = self._next_proxy_path("load_h5")
        shutil.copy2(src_path, target)
        return target

    def _iterate_dtype_names(self, dset) -> list[str]:
        names = list(dset.dtype.names or [])
        if not names:
            raise ValueError("Invalid vbump dataset format.")
        return names

    def _update_bbox(
        self,
        record: dict,
        overall_bbox: list[float] | None,
        group_bbox: dict[int, list[float]],
    ) -> list[float]:
        x0 = float(record["x0"])
        y0 = float(record["y0"])
        z0 = float(record["z0"])
        x1 = float(record["x1"])
        y1 = float(record["y1"])
        z1 = float(record["z1"])
        diameter = float(record["D"])
        gid = int(record["group"])
        half_d = diameter / 2.0

        x_min = min(x0, x1) - half_d
        x_max = max(x0, x1) + half_d
        y_min = min(y0, y1) - half_d
        y_max = max(y0, y1) + half_d
        z_min = min(z0, z1)
        z_max = max(z0, z1)

        if overall_bbox is None:
            overall_bbox = [x_min, y_min, z_min, x_max, y_max, z_max]
        else:
            overall_bbox[0] = min(overall_bbox[0], x_min)
            overall_bbox[1] = min(overall_bbox[1], y_min)
            overall_bbox[2] = min(overall_bbox[2], z_min)
            overall_bbox[3] = max(overall_bbox[3], x_max)
            overall_bbox[4] = max(overall_bbox[4], y_max)
            overall_bbox[5] = max(overall_bbox[5], z_max)

        bbox = group_bbox.get(gid)
        if bbox is None:
            group_bbox[gid] = [x_min, y_min, z_min, x_max, y_max, z_max]
        else:
            bbox[0] = min(bbox[0], x_min)
            bbox[1] = min(bbox[1], y_min)
            bbox[2] = min(bbox[2], z_min)
            bbox[3] = max(bbox[3], x_max)
            bbox[4] = max(bbox[4], y_max)
            bbox[5] = max(bbox[5], z_max)

        return overall_bbox

    def _write_bbox_attrs(self, fout, dset_out, overall_bbox, group_bbox) -> None:
        if overall_bbox is not None:
            dset_out.attrs["bounding_box"] = (
                (overall_bbox[0], overall_bbox[1], overall_bbox[2]),
                (overall_bbox[3], overall_bbox[4], overall_bbox[5]),
            )
        groups_node = fout.create_group("groups")
        for gid, bbox in sorted(group_bbox.items()):
            node = groups_node.create_group(str(gid))
            node.attrs["bounding_box"] = (
                (bbox[0], bbox[1], bbox[2]),
                (bbox[3], bbox[4], bbox[5]),
            )

    def _merge_proxy_paths(self, paths: list[str]) -> str:
        out_path = self._next_proxy_path("merge")
        with h5py.File(out_path, "w") as fout:
            dset_out = None
            names = None
            overall_bbox = None
            group_bbox: dict[int, list[float]] = {}

            for path in paths:
                with h5py.File(path, "r") as fin:
                    if "vbump" not in fin:
                        raise KeyError(f"Dataset 'vbump' not found in {path}.")
                    dset_in = fin["vbump"]
                    if dset_out is None:
                        dset_out = fout.create_dataset(
                            "vbump",
                            shape=(0,),
                            maxshape=(None,),
                            dtype=dset_in.dtype,
                            chunks=True,
                            compression="gzip",
                        )
                        names = self._iterate_dtype_names(dset_in)
                    for start in range(0, int(dset_in.shape[0]), HDF5_CHUNK_SIZE):
                        end = min(start + HDF5_CHUNK_SIZE, int(dset_in.shape[0]))
                        arr = dset_in[start:end]
                        if len(arr) == 0:
                            continue
                        old_size = int(dset_out.shape[0])
                        dset_out.resize((old_size + len(arr),))
                        dset_out[old_size:old_size + len(arr)] = arr
                        for row in arr:
                            record = {name: row[name].item() for name in names}
                            overall_bbox = self._update_bbox(record, overall_bbox, group_bbox)

            if dset_out is None:
                raise RuntimeError("No proxy data to merge.")
            self._write_bbox_attrs(fout, dset_out, overall_bbox, group_bbox)
        return out_path

    def _transform_proxy(self, transform: Callable[[dict], list[dict]], label: str) -> tuple[str, int]:
        if not self.proxy_h5_path:
            raise RuntimeError("No active proxy dataset.")

        out_path = self._next_proxy_path(label)
        written = 0
        with h5py.File(self.proxy_h5_path, "r") as fin, h5py.File(out_path, "w") as fout:
            if "vbump" not in fin:
                raise KeyError("Dataset 'vbump' not found.")
            dset_in = fin["vbump"]
            names = self._iterate_dtype_names(dset_in)
            dset_out = fout.create_dataset(
                "vbump",
                shape=(0,),
                maxshape=(None,),
                dtype=dset_in.dtype,
                chunks=True,
                compression="gzip",
            )

            overall_bbox = None
            group_bbox: dict[int, list[float]] = {}

            for start in range(0, int(dset_in.shape[0]), HDF5_CHUNK_SIZE):
                end = min(start + HDF5_CHUNK_SIZE, int(dset_in.shape[0]))
                arr = dset_in[start:end]
                if len(arr) == 0:
                    continue
                out_records = []
                for row in arr:
                    record = {name: row[name].item() for name in names}
                    transformed = transform(record)
                    for item in transformed:
                        out_records.append(tuple(item[name] for name in names))
                        overall_bbox = self._update_bbox(item, overall_bbox, group_bbox)
                if out_records:
                    old_size = int(dset_out.shape[0])
                    chunk = len(out_records)
                    dset_out.resize((old_size + chunk,))
                    dset_out[old_size:old_size + chunk] = out_records
                    written += chunk
            self._write_bbox_attrs(fout, dset_out, overall_bbox, group_bbox)
        return out_path, written

    def _copy_proxy_with_single_group(self, src_path: str, new_group: int) -> str:
        out_path = self._next_proxy_path("reassign_group")
        with h5py.File(src_path, "r") as fin, h5py.File(out_path, "w") as fout:
            if "vbump" not in fin:
                raise KeyError("Dataset 'vbump' not found.")
            dset_in = fin["vbump"]
            names = self._iterate_dtype_names(dset_in)
            dset_out = fout.create_dataset(
                "vbump",
                shape=(0,),
                maxshape=(None,),
                dtype=dset_in.dtype,
                chunks=True,
                compression="gzip",
            )

            overall_bbox = None
            group_bbox: dict[int, list[float]] = {}
            for start in range(0, int(dset_in.shape[0]), HDF5_CHUNK_SIZE):
                end = min(start + HDF5_CHUNK_SIZE, int(dset_in.shape[0]))
                arr = dset_in[start:end]
                if len(arr) == 0:
                    continue
                out_records = []
                for row in arr:
                    record = {name: row[name].item() for name in names}
                    record["group"] = new_group
                    out_records.append(tuple(record[name] for name in names))
                    overall_bbox = self._update_bbox(record, overall_bbox, group_bbox)
                old_size = int(dset_out.shape[0])
                dset_out.resize((old_size + len(out_records),))
                dset_out[old_size:old_size + len(out_records)] = out_records
            self._write_bbox_attrs(fout, dset_out, overall_bbox, group_bbox)
        return out_path

    def _materialize_current(self) -> VBumpCollection:
        if not self.proxy_h5_path:
            return VBumpCollection()
        return load_hdf5(self.proxy_h5_path, only_bounding_boxes=False)

    def _current_source_count(self) -> int:
        return int(getattr(self.current_vbumps, "source_count", len(self.current_vbumps)))

    def _get_existing_groups(self) -> set[int]:
        groups: set[int] = set()
        if not self.proxy_h5_path:
            return groups
        with h5py.File(self.proxy_h5_path, "r") as fin:
            if "groups" in fin:
                for name in fin["groups"].keys():
                    try:
                        groups.add(int(name))
                    except ValueError:
                        continue
            elif "vbump" in fin:
                dset = fin["vbump"]
                for start in range(0, int(dset.shape[0]), HDF5_CHUNK_SIZE):
                    end = min(start + HDF5_CHUNK_SIZE, int(dset.shape[0]))
                    arr = dset[start:end]
                    for gid in arr["group"]:
                        groups.add(int(gid))
        return groups

    def _replace_proxy(self, new_path: str, message: str) -> None:
        old = self.proxy_h5_path
        self._set_active_proxy(new_path)
        self.log(message)
        if old and Path(old) != Path(new_path):
            try:
                if str(old).startswith(str(self.proxy_dir.resolve())):
                    Path(old).unlink(missing_ok=True)
            except Exception:
                pass

    def closeEvent(self, event):
        if hasattr(self, "canvas") and self.canvas is not None:
            try:
                self.canvas.setParent(None)
            except Exception:
                pass
            try:
                del self.canvas
            except Exception:
                pass
        super().closeEvent(event)

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
                incoming_proxy = self._build_proxy_from_dxf(path)
                if incoming_proxy is None:
                    return
                self.log("✅ Loading DXF format and converting to proxy hdf5")
            elif h5py.is_hdf5(path):
                incoming_proxy = self._copy_hdf5_to_proxy(path)
                self.log("✅ Loading hdf5 format (proxy copy)")
            else:
                incoming_proxy = self._build_proxy_from_csv(path)
                self.log("✅ Loading csv format and converting to proxy hdf5")

            reply = QMessageBox.question(
                self,
                "Reassign Group ID",
                "Do you want to assign a new group ID to the newly loaded bumps?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                from PySide6.QtWidgets import QInputDialog

                new_gid, ok = QInputDialog.getInt(self, "New Group ID", "Enter new group ID:", 1, 1, 9999)
                if ok:
                    incoming_proxy = self._copy_proxy_with_single_group(incoming_proxy, new_gid)
                    self.log(f"🔢 Newly loaded bumps reassigned to group {new_gid}.")

            if self.proxy_h5_path:
                merged = self._merge_proxy_paths([self.proxy_h5_path, incoming_proxy])
                self._replace_proxy(merged, f"✅ Loaded and appended {path} (total {self._current_source_count():,} bumps)")
            else:
                self._replace_proxy(incoming_proxy, f"✅ Loaded {path} ({self._current_source_count():,} bumps)")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def save_csv(self):
        if not self._ensure_proxy_loaded():
            return

        reply = QMessageBox.question(
            self,
            "Save as HDF5?",
            "Do you want to save the file as HDF5 format?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            path, _ = QFileDialog.getSaveFileName(self, "Save HDF5", "", "HDF5 Files (*.h5 *.hdf5)")
            if path:
                shutil.copy2(self.proxy_h5_path, path)
                self.log(f"💾 Saved proxy HDF5 to {path}")
        else:
            path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
            if path:
                vbumps = self._materialize_current()
                to_csv(path, vbumps)
                self.log(f"💾 Materialized and saved CSV to {path}")

    def create_pitch(self):
        dialog_result = request_pitch_parameters(self)
        if not dialog_result:
            return

        p0 = dialog_result.p0
        p1 = dialog_result.p1
        x_pitch = dialog_result.x_pitch
        y_pitch = dialog_result.y_pitch
        dia = dialog_result.diameter
        group = dialog_result.group
        z = dialog_result.z
        h = dialog_result.h

        out_proxy = self._next_proxy_path("create_pitch")
        try:
            written = create_rectangular_area_XY_by_pitch_to_hdf5(
                out_proxy,
                p0,
                p1,
                x_pitch,
                y_pitch,
                dia,
                group,
                z,
                h,
                log_callback=self.log,
            )
            if self.proxy_h5_path:
                merged = self._merge_proxy_paths([self.proxy_h5_path, out_proxy])
                self._replace_proxy(merged, f"📐 Appended {written:,} bumps by pitch in proxy mode")
            else:
                self._replace_proxy(out_proxy, f"📐 Created {written:,} bumps by pitch in proxy mode")
            if self.substrate_p0 and self.substrate_p1:
                self.plot_aabb()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def create_count(self):
        dialog_result = request_count_parameters(self)
        if not dialog_result:
            return

        p0 = dialog_result.p0
        p1 = dialog_result.p1
        x_num = dialog_result.x_count
        y_num = dialog_result.y_count
        dia = dialog_result.diameter
        group = dialog_result.group
        z = dialog_result.z
        h = dialog_result.h

        out_proxy = self._next_proxy_path("create_count")
        try:
            written = create_rectangular_area_XY_by_number_to_hdf5(
                out_proxy,
                p0,
                p1,
                x_num,
                y_num,
                dia,
                group,
                z,
                h,
                log_callback=self.log,
            )
            if self.proxy_h5_path:
                merged = self._merge_proxy_paths([self.proxy_h5_path, out_proxy])
                self._replace_proxy(merged, f"📏 Appended {written:,} bumps by count in proxy mode")
            else:
                self._replace_proxy(out_proxy, f"📏 Created {written:,} bumps by count in proxy mode")
            if self.substrate_p0 and self.substrate_p1:
                self.plot_aabb()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def modify_diameter(self):
        if not self._ensure_proxy_loaded():
            return
        dialog_result = request_modify_value(self, "Modify Diameter", "New Diameter:")
        if not dialog_result:
            return

        gid = dialog_result.group_filter
        new_d = dialog_result.new_value

        def transform(record: dict) -> list[dict]:
            if gid is not None and int(record["group"]) != gid:
                return [record]
            record["D"] = float(new_d)
            return [record]

        try:
            out_path, written = self._transform_proxy(transform, "modify_diameter")
            self._replace_proxy(out_path, f"🔧 Updated diameter to {new_d} (rows now: {written:,})")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def modify_height(self):
        if not self._ensure_proxy_loaded():
            return

        dialog_result = request_modify_value(self, "Modify Height", "New Height:")
        if not dialog_result:
            return

        gid = dialog_result.group_filter
        new_h = dialog_result.new_value

        def transform(record: dict) -> list[dict]:
            if gid is not None and int(record["group"]) != gid:
                return [record]
            x0, y0, z0 = float(record["x0"]), float(record["y0"]), float(record["z0"])
            x1, y1, z1 = float(record["x1"]), float(record["y1"]), float(record["z1"])
            dx = x1 - x0
            dy = y1 - y0
            dz = z1 - z0
            length = (dx * dx + dy * dy + dz * dz) ** 0.5
            if length == 0:
                return [record]
            scale = float(new_h) / length
            record["x1"] = x0 + scale * dx
            record["y1"] = y0 + scale * dy
            record["z1"] = z0 + scale * dz
            return [record]

        try:
            out_path, written = self._transform_proxy(transform, "modify_height")
            self._replace_proxy(out_path, f"📐 Updated height to {new_h} (rows now: {written:,})")
            if self.substrate_p0 and self.substrate_p1:
                self.plot_aabb()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def delete_group(self):
        if not self._ensure_proxy_loaded():
            return
        from PySide6.QtWidgets import QInputDialog

        gid, ok = QInputDialog.getInt(self, "Delete Group", "Enter group ID to delete:", 0, 1, 9999)
        if not ok:
            return

        before = self._current_source_count()

        def transform(record: dict) -> list[dict]:
            if int(record["group"]) == gid:
                return []
            return [record]

        try:
            out_path, written = self._transform_proxy(transform, "delete_group")
            removed = before - written
            self._replace_proxy(out_path, f"🗑️ Deleted group {gid} ({removed:,} bumps removed)")
            if self.substrate_p0 and self.substrate_p1:
                self.plot_aabb()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def move_bumps(self):
        if not self._ensure_proxy_loaded():
            return

        dialog_result = request_move_parameters(self)
        if not dialog_result:
            return

        gid = dialog_result.group_filter
        keep = dialog_result.keep_original
        new_g = dialog_result.new_group
        new_d = dialog_result.new_diameter
        delta_u = tuple(t - r for t, r in zip(dialog_result.target, dialog_result.reference))

        auto_group_map = {}
        if keep and gid is None and new_g is None:
            existing = self._get_existing_groups()
            max_group = max(existing) if existing else 0
            with h5py.File(self.proxy_h5_path, "r") as fin:
                dset = fin["vbump"]
                seen: set[int] = set()
                for start in range(0, int(dset.shape[0]), HDF5_CHUNK_SIZE):
                    end = min(start + HDF5_CHUNK_SIZE, int(dset.shape[0]))
                    arr = dset[start:end]
                    for group_value in arr["group"]:
                        g = int(group_value)
                        if g not in seen:
                            seen.add(g)
                            max_group += 1
                            auto_group_map[g] = max_group

        def transform(record: dict) -> list[dict]:
            current_gid = int(record["group"])
            selected = gid is None or current_gid == gid
            if not selected:
                return [record]

            moved = dict(record)
            moved["x0"] = float(moved["x0"]) + delta_u[0]
            moved["y0"] = float(moved["y0"]) + delta_u[1]
            moved["z0"] = float(moved["z0"]) + delta_u[2]
            moved["x1"] = float(moved["x1"]) + delta_u[0]
            moved["y1"] = float(moved["y1"]) + delta_u[1]
            moved["z1"] = float(moved["z1"]) + delta_u[2]

            if new_d is not None:
                moved["D"] = float(new_d)
            if auto_group_map and current_gid in auto_group_map:
                moved["group"] = int(auto_group_map[current_gid])
            elif new_g is not None:
                moved["group"] = int(new_g)

            if keep:
                return [record, moved]
            return [moved]

        try:
            out_path, written = self._transform_proxy(transform, "move_copy")
            if auto_group_map:
                assigned = ", ".join(str(v) for v in sorted(auto_group_map.values()))
                self._replace_proxy(out_path, f"📤 Duplicated bumps with auto-groups {assigned} (rows now: {written:,})")
            else:
                self._replace_proxy(out_path, f"📤 Move/Copy applied (rows now: {written:,})")
            if self.substrate_p0 and self.substrate_p1:
                self.plot_aabb()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def export_weldline(self):
        if not self._ensure_proxy_loaded():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save WDL (weldline)", "", "WDL Files (*.wdl)")
        if not path:
            return
        vbumps = self._materialize_current()
        if len(vbumps) < 20000:
            vbump_2_wdl_as_weldline(path, vbumps)
        else:
            vbump_2_wdl_as_weldline_AABB(path, vbumps)
        self.log(f"🧵 Weldline exported to {path} (materialized {len(vbumps):,} rows)")

    def export_airtrap(self):
        if not self._ensure_proxy_loaded():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save WDL (airtrap)", "", "WDL Files (*.wdl)")
        if not path:
            return
        vbumps = self._materialize_current()
        vbump_2_wdl_as_airtrap(path, vbumps)
        self.log(f"💨 Airtrap exported to {path} (materialized {len(vbumps):,} rows)")

    def export_vtp(self):
        if not self._ensure_proxy_loaded():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save VTP", "", "VTP Files (*.vtp)")
        if not path:
            return
        vbumps = self._materialize_current()
        write_vbumps_vtp(vbumps, path)
        self.log(f"🧪 VTP exported to {path} (materialized {len(vbumps):,} rows)")

    def plot_aabb(self):
        if not self._ensure_proxy_loaded():
            return

        if not self.substrate_p0 or not self.substrate_p1:
            self.set_substrate_box()
            if not self.substrate_p0 or not self.substrate_p1:
                return

        self.figure.clear()
        ax = self.figure.add_subplot(111, projection="3d")

        source_count = self._current_source_count()
        if source_count <= PLOT_MATERIALIZE_THRESHOLD:
            vbumps = self._materialize_current()
            if len(vbumps) < 9000:
                plot_vbumps(vbumps, self.substrate_p0, self.substrate_p1, ax=ax)
            else:
                plot_vbumps_aabb(vbumps, self.substrate_p0, self.substrate_p1, ax=ax)
            self.log(f"📊 Plot rendered with materialized data ({len(vbumps):,} rows).")
        else:
            plot_vbumps_aabb(self.current_vbumps, self.substrate_p0, self.substrate_p1, ax=ax)
            self.log(
                f"📊 Plot rendered from proxy markers (source {source_count:,} rows > {PLOT_MATERIALIZE_THRESHOLD:,})."
            )

        self.canvas.draw()

    def set_substrate_box(self):
        auto_bounds = None
        if self.current_vbumps:
            bounds = self._compute_bounding_box(self.current_vbumps)
            if bounds is not None:
                min_pt, max_pt = bounds
                max_x, max_y, max_z = max_pt
                max_z *= -1
                auto_bounds = (min_pt, (max_x, max_y, max_z))

        initial = None
        if self.substrate_p0 and self.substrate_p1:
            initial = (self.substrate_p0, self.substrate_p1)

        dialog_result = request_substrate_box(
            self,
            initial=initial,
            auto_bounds=auto_bounds,
        )
        if not dialog_result:
            return

        self.substrate_p0 = dialog_result.p0
        self.substrate_p1 = dialog_result.p1
        self.log(f"🧱 Substrate box set to {dialog_result.p0} - {dialog_result.p1}")


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    ui = VBumpUI()
    ui.show()
    sys.exit(app.exec())
