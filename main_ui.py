from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLineEdit, QLabel, QFileDialog, QTextEdit, QCheckBox, QMessageBox, QGroupBox
)
from PySide6.QtCore import QThread
from PySide6.QtGui import QTextCursor
from typing import Tuple
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import main
import h5py

from VBump.Basic import VBumpCollection

from ui.dialogs import (
    request_count_parameters,
    request_modify_value,
    request_move_parameters,
    request_pitch_parameters,
    request_substrate_box,
)
from ui.streaming import HDF5StreamWorker

class VBumpUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Virtual Bump CSV Generator (GUI)")
        self.setMinimumSize(1000, 700)

        # 狀態變數
        self.loaded_vbumps: VBumpCollection = VBumpCollection()
        self.current_vbumps: VBumpCollection = VBumpCollection()
        self.substrate_p0: Tuple[float, float, float] | None = None
        self.substrate_p1: Tuple[float, float, float] | None = None
        self._stream_threads: list[QThread] = []

        # 主容器
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setCentralWidget(central)

        # === File 操作 ===
        file_box = QGroupBox("📂 File Operations")
        flayout = QHBoxLayout(file_box)
        self.btn_load = QPushButton("Load CSV")
        self.btn_save = QPushButton("Save CSV")
        flayout.addWidget(self.btn_load)
        flayout.addWidget(self.btn_save)
        layout.addWidget(file_box)

        # === Create Area ===
        create_box = QGroupBox("📐 Create Rectangular Area")
        form_create = QFormLayout(create_box)
        self.btn_create_pitch = QPushButton("Generate by Pitch")
        self.btn_create_count = QPushButton("Generate by Count")
        form_create.addRow(self.btn_create_pitch, self.btn_create_count)
        layout.addWidget(create_box)

        # === Modify / Move ===
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

        # === Export / Plot ===
        exp_box = QGroupBox("📤 Export / Plot")
        explayout = QHBoxLayout(exp_box)
        self.btn_weldline = QPushButton("Export WDL (Weldline)")
        self.btn_airtrap = QPushButton("Export WDL (Airtrap)")
        self.btn_plot = QPushButton("Plot")
        explayout.addWidget(self.btn_weldline)
        explayout.addWidget(self.btn_airtrap)
        explayout.addWidget(self.btn_plot)
        layout.addWidget(exp_box)

        # === Log & Plot (並排顯示) ===
        layout.addWidget(QLabel("🧾 Log Output:"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        self.plot_box = QGroupBox("📊 Plot Preview")
        plot_layout = QVBoxLayout(self.plot_box)
        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        plot_layout.addWidget(self.canvas)
        # === View Control Buttons ===
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

        # 綁定事件
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
        self.btn_plot.clicked.connect(self.plot_aabb)

        # 初始 log
        self.log("🐢 Virtual Bump Generator (GUI mode) started.")

    # === 工具函式 ===
    def log(self, text):
        self.log_view.append(text)
        self.log_view.moveCursor(QTextCursor.End)
        QApplication.processEvents()

    def _ensure_collection(self, bumps) -> VBumpCollection:
        if isinstance(bumps, VBumpCollection):
            return bumps
        return VBumpCollection(list(bumps))

    def _clone_vbumps(self, bumps) -> list[main.VBump]:
        return [main.VBump.from_other(b) for b in bumps]

    def _collection_from(self, items, template: VBumpCollection | None = None, **overrides) -> VBumpCollection:
        data = list(items)
        if template is not None:
            collection = VBumpCollection(
                data,
                bounding_box=template.bounding_box,
                group_bounding_boxes=dict(template.group_bounding_boxes or {}),
                source_count=template.source_count,
                is_bounding_box_only=template.is_bounding_box_only,
                link_h5_filepath=template.link_h5_filepath,
            )
        else:
            collection = VBumpCollection(
                data,
                bounding_box=None,
                group_bounding_boxes={},
                source_count=len(data),
                is_bounding_box_only=False,
                link_h5_filepath=None,
            )
        for key, value in overrides.items():
            setattr(collection, key, value)
        return collection

    def _mark_collection_modified(self, collection: VBumpCollection) -> None:
        collection.bounding_box = None
        collection.group_bounding_boxes = {}
        collection.link_h5_filepath = None
        collection.is_bounding_box_only = False
        collection.source_count = len(collection)

    def _append_to_current(
        self,
        bumps,
        *,
        metadata_template: VBumpCollection | None = None,
        metadata_overrides: dict | None = None,
    ) -> None:
        source = self._ensure_collection(bumps)
        clones = self._clone_vbumps(source)
        template = metadata_template or source
        if not self.current_vbumps:
            self.current_vbumps = self._collection_from(clones, template)
        else:
            self.current_vbumps.extend(clones)
            self._mark_collection_modified(self.current_vbumps)
            return
        if metadata_overrides:
            for key, value in metadata_overrides.items():
                setattr(self.current_vbumps, key, value)

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

    def f(self, edit: QLineEdit, default=None, cast=float):
        t = edit.text().strip()
        if not t:
            return default
        try:
            return cast(t)
        except ValueError:
            return default

    def _start_stream_worker(self, task, dialog=None):
        worker = HDF5StreamWorker(task)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.log)
        worker.finished.connect(lambda written, path, markers: self._stream_finished(thread, worker, written, path, markers))
        worker.error.connect(lambda message: self._stream_error(thread, worker, message))
        thread.start()
        thread.worker = worker  # retain reference for the lifetime of the thread
        self._stream_threads.append(thread)
        if dialog is not None:
            dialog.accept()

    def _stream_finished(self, thread: QThread, worker: HDF5StreamWorker, written: int, path: str, markers: list[main.VBump]):
        if markers:
            overrides = {
                "source_count": written,
                "is_bounding_box_only": True,
                "link_h5_filepath": path,
            }
            bbox = self._compute_bounding_box(markers)
            if bbox is not None:
                overrides["bounding_box"] = bbox
            self._append_to_current(markers, metadata_overrides=overrides)
            self.log(f"📏 Stored {len(markers)} bounding-box markers in memory after streaming {written:,} bumps from {path}.")
            if self.substrate_p0 and self.substrate_p1:
                self.plot_aabb()
        self._teardown_stream_thread(thread, worker)

    def _stream_error(self, thread: QThread, worker: HDF5StreamWorker, message: str):
        self.log(f"❌ Streaming failed: {message}")
        QMessageBox.critical(self, "Stream Error", message)
        self._teardown_stream_thread(thread, worker)

    def _teardown_stream_thread(self, thread: QThread, worker: HDF5StreamWorker):
        thread.quit()
        thread.wait()
        worker.deleteLater()
        thread.deleteLater()
        if thread in self._stream_threads:
            self._stream_threads.remove(thread)
        # Detach to avoid double-free on QApplication teardown
        try:
            thread.setParent(None)
        except Exception:
            pass

    def closeEvent(self, event):
        # Gracefully stop any worker threads
        for t in list(self._stream_threads):
            try:
                t.quit()
                t.wait()
                try:
                    t.setParent(None)
                except Exception:
                    pass
            except Exception:
                pass
        self._stream_threads.clear()
        # Explicitly detach and delete matplotlib canvas to avoid double free
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

    # === 檔案操作 ===
    def load_csv(self):
        path, _ = QFileDialog.getOpenFileName(
                        self,
                        "Select File",
                        "",
                        "CSV/h5/VBump Files (*.csv *.CSV *.hdf5 *h5 *.vbump *.VBUMP);;All Files (*)"
                    )
        if not path:
            return
        try:
            new_vbumps = []
            if h5py.is_hdf5(path):
                new_vbumps = main.load_hdf5(path, max_rows=main.LARGE_VBUMP_THRESHOLD)
                self.log(f"✅ Loading hdf5 format")
                if getattr(new_vbumps, "is_bounding_box_only", False):
                    msg = (
                        f"Source contains {new_vbumps.source_count:,} bumps. Loaded bounding-box markers instead "
                        f"because the dataset exceeds the threshold {main.LARGE_VBUMP_THRESHOLD:,}."
                    )
                    self.log(f"⚠️ {msg}")
                    QMessageBox.information(self, "Large Dataset", msg)
            else:
                new_vbumps = main.load_csv(path)
                self.log(f"✅ Loading csv format")
            new_collection = self._ensure_collection(new_vbumps)
            self.loaded_vbumps.extend(new_collection)
            self._mark_collection_modified(self.loaded_vbumps)
            self._append_to_current(new_collection)
            self.log(f"✅ Loaded {len(new_vbumps)} bumps from {path} (total {len(self.loaded_vbumps)})")
            reply = QMessageBox.question(
                self,
                "Reassign Group ID",
                "Do you want to assign a new group ID to the newly loaded bumps?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                from PySide6.QtWidgets import QInputDialog
                new_gid, ok = QInputDialog.getInt(self, "New Group ID", "Enter new group ID:", 1, 1, 9999)
                if ok:
                    for b in self.current_vbumps[-len(new_vbumps):]:
                        b.group = new_gid
                    self.log(f"🔢 Newly loaded bumps reassigned to group {new_gid}.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def save_csv(self):
        if not self.current_vbumps:
            QMessageBox.warning(self, "Warning", "No bumps to save.")
            return
        # Ask the user if they want to save as HDF5
        reply = QMessageBox.question(
            self,
            "Save as HDF5?",
            "Do you want to save the file as HDF5 format?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            path, _ = QFileDialog.getSaveFileName(self, "Save HDF5", "", "HDF5 Files (*.h5 *.hdf5)")
            if path:
                self.log(f"🚀 Streaming {len(self.current_vbumps):,} bumps to {path}.")
                main.to_hdf5(path, self.current_vbumps, log_callback=self.log)
                self.log(f"💾 Saved to {path}")
        else:
            path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
            if path:
                main.to_csv(path, self.current_vbumps)
                self.log(f"💾 Saved to {path}")

    # === 建立矩形 ===
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

        estimated = main.estimate_rectangular_area_XY_by_pitch_count(p0, p1, x_pitch, y_pitch)
        try:
            if estimated >= main.LARGE_VBUMP_THRESHOLD:
                QMessageBox.information(
                    self,
                    "Large Dataset",
                    (
                        f"The requested grid would generate {estimated:,} vbumps, which exceeds the in-memory limit "
                        f"({main.LARGE_VBUMP_THRESHOLD:,}). The full dataset will be written to an HDF5 file."
                        " Only two bounding-box markers will remain in memory."
                    ),
                )
                path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Save HDF5",
                    "",
                    "HDF5 Files (*.h5 *.hdf5)",
                )
                if not path:
                    self.log("⚠️ Large dataset generation cancelled (no file selected).")
                    return

                def task(log_emit):
                    written = main.create_rectangular_area_XY_by_pitch_to_hdf5(
                        path,
                        p0,
                        p1,
                        x_pitch,
                        y_pitch,
                        dia,
                        group,
                        z,
                        h,
                        log_callback=log_emit,
                    )
                    markers = main.bounding_box_vbumps_for_rectangular_area(p0, p1, z, h, dia, group)
                    return written, path, markers

                self.log(
                    f"🚀 Streaming {estimated:,} bumps to {path}. Live progress will appear below."
                )
                self._start_stream_worker(task)
                return

            new_vbumps = main.create_rectangular_area_XY_by_pitch(p0, p1, x_pitch, y_pitch, dia, group, z, h)
            self.log(f"📐 Created {len(new_vbumps)} bumps by pitch")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self._append_to_current(new_vbumps)
        if self.substrate_p0 and self.substrate_p1:
            self.plot_aabb()

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

        estimated = main.estimate_rectangular_area_XY_by_number_count(x_num, y_num)
        try:
            if estimated >= main.LARGE_VBUMP_THRESHOLD:
                QMessageBox.information(
                    self,
                    "Large Dataset",
                    (
                        f"The requested grid would generate {estimated:,} vbumps, which exceeds the in-memory limit "
                        f"({main.LARGE_VBUMP_THRESHOLD:,}). The full dataset will be written to an HDF5 file."
                        " Only two bounding-box markers will remain in memory."
                    ),
                )
                path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Save HDF5",
                    "",
                    "HDF5 Files (*.h5 *.hdf5)",
                )
                if not path:
                    self.log("⚠️ Large dataset generation cancelled (no file selected).")
                    return

                def task(log_emit):
                    new_p0, new_p1, x_pitch, y_pitch = main.normalize_rectangular_area_from_counts(
                        p0, p1, x_num, y_num
                    )
                    written = main.create_rectangular_area_XY_by_number_to_hdf5(
                        path,
                        p0,
                        p1,
                        x_num,
                        y_num,
                        dia,
                        group,
                        z,
                        h,
                        log_callback=log_emit,
                    )
                    markers = main.bounding_box_vbumps_for_rectangular_area(new_p0, new_p1, z, h, dia, group)
                    return written, path, markers

                self.log(
                    f"🚀 Streaming {estimated:,} bumps to {path}. Live progress will appear below."
                )
                self._start_stream_worker(task)
                return

            new_vbumps = main.create_rectangular_area_XY_by_number(p0, p1, x_num, y_num, dia, group, z, h)
            self.log(f"📏 Created {len(new_vbumps)} bumps by count")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self._append_to_current(new_vbumps)
        if self.substrate_p0 and self.substrate_p1:
            self.plot_aabb()

    # === 修改與移動 ===
    def modify_diameter(self):
        if not self.current_vbumps:
            QMessageBox.warning(self, "Warning", "No bumps loaded.")
            return
        dialog_result = request_modify_value(self, "Modify Diameter", "New Diameter:")
        if not dialog_result:
            return

        gid = dialog_result.group_filter
        new_d = dialog_result.new_value
        selected = [b for b in self.current_vbumps if gid is None or b.group == gid]
        main.modify_diameter(selected, new_d)
        self._mark_collection_modified(self.current_vbumps)
        self.log(f"🔧 Updated diameter to {new_d} for {len(selected)} bumps")

    def modify_height(self):
        if not self.current_vbumps:
            QMessageBox.warning(self, "Warning", "No bumps loaded.")
            return

        dialog_result = request_modify_value(self, "Modify Height", "New Height:")
        if not dialog_result:
            return

        gid = dialog_result.group_filter
        new_h = dialog_result.new_value
        selected = [b for b in self.current_vbumps if gid is None or b.group == gid]
        if not selected:
            QMessageBox.information(self, "Info", "No bumps matched the filter.")
            return
        main.modify_height(selected, new_h)
        self._mark_collection_modified(self.current_vbumps)
        self.log(f"📐 Updated height to {new_h} for {len(selected)} bumps")
        if self.substrate_p0 and self.substrate_p1:
            self.plot_aabb()

    def delete_group(self):
        if not self.current_vbumps:
            QMessageBox.warning(self, "Warning", "No bumps loaded.")
            return
        from PySide6.QtWidgets import QInputDialog
        gid, ok = QInputDialog.getInt(self, "Delete Group", "Enter group ID to delete:", 0, 1, 9999)
        if not ok:
            return
        before = len(self.current_vbumps)
        remaining = [b for b in self.current_vbumps if b.group != gid]
        self.current_vbumps = self._collection_from(remaining)
        self._mark_collection_modified(self.current_vbumps)
        after = len(self.current_vbumps)
        removed = before - after
        self.log(f"🗑️ Deleted group {gid} ({removed} bumps removed).")
        if self.substrate_p0 and self.substrate_p1:
            self.plot_aabb()

    def move_bumps(self):
        if not self.current_vbumps:
            QMessageBox.warning(self, "Warning", "No bumps loaded.")
            return

        dialog_result = request_move_parameters(self)
        if not dialog_result:
            return

        gid = dialog_result.group_filter
        selected = [b for b in self.current_vbumps if gid is None or b.group == gid]
        if not selected:
            QMessageBox.information(self, "Info", "No bumps matched the filter.")
            return

        keep = dialog_result.keep_original
        new_g = dialog_result.new_group
        new_d = dialog_result.new_diameter

        auto_group_map = {}
        if keep and gid is None and new_g is None:
            existing_groups = [b.group for b in self.current_vbumps if isinstance(b.group, int)]
            max_group = max(existing_groups) if existing_groups else 0
            for b in selected:
                g = b.group
                if g not in auto_group_map:
                    max_group += 1
                    auto_group_map[g] = max_group

        delta_u = tuple(t - r for t, r in zip(dialog_result.target, dialog_result.reference))

        moved = main.move_vbumps(
            selected,
            delta_u,
            new_g,
            new_d,
            keep,
            auto_group_map if auto_group_map else None,
        )
        copies = moved[len(selected):] if keep else moved

        if gid is not None and not keep:
            remaining = [b for b in self.current_vbumps if b.group != gid]
            updated = remaining + moved
            self.current_vbumps = self._collection_from(updated)
            self._mark_collection_modified(self.current_vbumps)
        elif gid is None and not keep:
            self.current_vbumps = self._collection_from(moved)
            self._mark_collection_modified(self.current_vbumps)
        else:
            self._append_to_current(copies)

        if auto_group_map:
            assigned = ", ".join(str(v) for v in sorted(auto_group_map.values()))
            self.log(f"📤 Duplicated {len(selected)} bumps with new groups {assigned}")
        else:
            self.log(f"📤 Moved/duplicated {len(selected)} bumps")
        if self.substrate_p0 and self.substrate_p1:
            self.plot_aabb()

    # === 匯出 / 繪圖 ===
    def export_weldline(self):
        if not self.current_vbumps:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save WDL (weldline)", "", "WDL Files (*.wdl)")
        if not path:
            return
        if len(self.current_vbumps) < 20000:
            main.vbump_2_wdl_as_weldline(path, self.current_vbumps)
        else:
            main.vbump_2_wdl_as_weldline_AABB(path, self.current_vbumps)
        self.log(f"🧵 Weldline exported to {path}")

    def export_airtrap(self):
        if not self.current_vbumps:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save WDL (airtrap)", "", "WDL Files (*.wdl)")
        if not path:
            return
        main.vbump_2_wdl_as_airtrap(path, self.current_vbumps)
        self.log(f"💨 Airtrap exported to {path}")

    def plot_aabb(self):        
        if not self.current_vbumps:
            return
        # 若尚未設定 substrate box，自動彈出設定視窗
        if not self.substrate_p0 or not self.substrate_p1:
            self.set_substrate_box()
            # 若使用者取消設定則不繪圖
            if not self.substrate_p0 or not self.substrate_p1:
                return
        # 清空舊圖
        self.figure.clear()

        # 傳入 ax 給 main 模組繪圖
        ax = self.figure.add_subplot(111, projection='3d')
        if len(self.current_vbumps) < 9000:
            main.plot_vbumps(self.current_vbumps, self.substrate_p0, self.substrate_p1, ax=ax)
        else:
            main.plot_vbumps_aabb(self.current_vbumps, self.substrate_p0, self.substrate_p1, ax=ax)
        self.canvas.draw()
        self.log("📊 AABB plotted.")

    def set_substrate_box(self):
        auto_bounds = None
        if self.current_vbumps:
            min_pt, max_pt = self._compute_bounding_box(self.current_vbumps)
            max_x, max_y, max_z = max_pt
            max_z *= -1 #set under vbumps and twice as height of vbump
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
