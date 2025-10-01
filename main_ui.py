from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLineEdit, QLabel, QFileDialog, QTextEdit, QCheckBox, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt, QThread, QObject, Signal, Slot
from PySide6.QtGui import QTextCursor
from typing import List, Tuple
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import main
import h5py


class HDF5StreamWorker(QObject):
    progress = Signal(str)
    finished = Signal(int, str, list)
    error = Signal(str)

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self._task = task

    @Slot()
    def run(self):
        try:
            written, path, markers = self._task(self.progress.emit)
            self.finished.emit(written, path, markers)
        except Exception as exc:
            self.error.emit(str(exc))


class VBumpUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Virtual Bump CSV Generator (GUI)")
        self.setMinimumSize(1000, 700)

        # 狀態變數
        self.loaded_vbumps: List[main.VBump] = []
        self.current_vbumps: List[main.VBump] = []
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
        self.btn_move = QPushButton("Move / Copy Bumps")
        self.btn_delete_group = QPushButton("Delete Group")
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_modify_diam)
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
        self.btn_move.clicked.connect(self.move_bumps)
        self.btn_delete_group.clicked.connect(self.delete_group)
        self.btn_weldline.clicked.connect(self.export_weldline)
        self.btn_airtrap.clicked.connect(self.export_airtrap)
        self.btn_plot.clicked.connect(self.plot_aabb)

        # 初始 log
        self.log("🐢 Virtual Bump Generator (GUI mode) started.")

    # === 工具函式 ===
    def _pair(self, edits):
        box = QWidget(self)
        layout = QHBoxLayout(box)
        for e in edits:
            layout.addWidget(e)
        return box

    def _triple(self, edits):
        box = QWidget(self)
        layout = QHBoxLayout(box)
        for e in edits:
            layout.addWidget(e)
        return box

    def log(self, text):
        self.log_view.append(text)
        self.log_view.moveCursor(QTextCursor.End)
        QApplication.processEvents()

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
            self.current_vbumps.extend(markers)
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
        import copy
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
            self.loaded_vbumps.extend(new_vbumps)
            self.current_vbumps.extend(copy.deepcopy(new_vbumps))
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
        from PySide6.QtWidgets import QDialog
        dlg = QDialog(self)
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

        layout.addRow("Lower corner (x0, y0):", self._pair(p0_edits))
        layout.addRow("Upper corner (x1, y1):", self._pair(p1_edits))
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

        def on_ok():
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
                QMessageBox.warning(self, "Warning", "Invalid input values.")
                return

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
                    self._start_stream_worker(task, dialog=dlg)
                    return
                else:
                    new_vbumps = main.create_rectangular_area_XY_by_pitch(p0, p1, x_pitch, y_pitch, dia, group, z, h)
                    self.log(f"📐 Created {len(new_vbumps)} bumps by pitch")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
                return

            self.current_vbumps.extend(new_vbumps)
            dlg.accept()
            if self.substrate_p0 and self.substrate_p1:
                self.plot_aabb()
        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec()

    def create_count(self):
        from PySide6.QtWidgets import QDialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Create Bumps by Count")
        layout = QFormLayout(dlg)

        p0_edits = [QLineEdit(), QLineEdit()]
        p1_edits = [QLineEdit(), QLineEdit()]
        x_num_edit = QLineEdit()
        y_num_edit = QLineEdit()
        dia_edit = QLineEdit()
        group_edit = QLineEdit()
        z_edit = QLineEdit()
        h_edit = QLineEdit()

        layout.addRow("Lower corner (x0, y0):", self._pair(p0_edits))
        layout.addRow("Upper corner (x1, y1):", self._pair(p1_edits))
        layout.addRow("X count:", x_num_edit)
        layout.addRow("Y count:", y_num_edit)
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

        def on_ok():
            try:
                p0 = (float(p0_edits[0].text()), float(p0_edits[1].text()))
                p1 = (float(p1_edits[0].text()), float(p1_edits[1].text()))
                x_num = int(x_num_edit.text())
                y_num = int(y_num_edit.text())
                dia = float(dia_edit.text())
                group = int(group_edit.text()) if group_edit.text() else 1
                z = float(z_edit.text())
                h = float(h_edit.text())
            except ValueError:
                QMessageBox.warning(self, "Warning", "Invalid input values.")
                return

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
                    self._start_stream_worker(task, dialog=dlg)
                    return
                else:
                    new_vbumps = main.create_rectangular_area_XY_by_number(p0, p1, x_num, y_num, dia, group, z, h)
                    self.log(f"📏 Created {len(new_vbumps)} bumps by count")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
                return

            self.current_vbumps.extend(new_vbumps)
            dlg.accept()
            if self.substrate_p0 and self.substrate_p1:
                self.plot_aabb()
        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec()

    # === 修改與移動 ===
    def modify_diameter(self):
        if not self.current_vbumps:
            QMessageBox.warning(self, "Warning", "No bumps loaded.")
            return

        from PySide6.QtWidgets import QDialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Modify Diameter")
        layout = QFormLayout(dlg)

        group_edit = QLineEdit()
        new_diam_edit = QLineEdit()
        layout.addRow("Group Filter (optional):", group_edit)
        layout.addRow("New Diameter:", new_diam_edit)

        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_box = QHBoxLayout()
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addRow(btn_box)

        def on_ok():
            try:
                gid = int(group_edit.text()) if group_edit.text() else None
                new_d = float(new_diam_edit.text())
                selected = [b for b in self.current_vbumps if gid is None or b.group == gid]
                main.modify_diameter(selected, new_d)
                self.log(f"🔧 Updated diameter to {new_d} for {len(selected)} bumps")
                dlg.accept()
            except Exception:
                QMessageBox.warning(self, "Warning", "Invalid input values.")
        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec()

    def delete_group(self):
        if not self.current_vbumps:
            QMessageBox.warning(self, "Warning", "No bumps loaded.")
            return
        from PySide6.QtWidgets import QInputDialog
        gid, ok = QInputDialog.getInt(self, "Delete Group", "Enter group ID to delete:", 1, 1, 9999)
        if not ok:
            return
        before = len(self.current_vbumps)
        self.current_vbumps = [b for b in self.current_vbumps if b.group != gid]
        after = len(self.current_vbumps)
        removed = before - after
        self.log(f"🗑️ Deleted group {gid} ({removed} bumps removed).")
        if self.substrate_p0 and self.substrate_p1:
            self.plot_aabb()

    def move_bumps(self):
        if not self.current_vbumps:
            QMessageBox.warning(self, "Warning", "No bumps loaded.")
            return

        from PySide6.QtWidgets import QDialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Move / Copy Bumps")
        layout = QFormLayout(dlg)

        group_edit = QLineEdit()
        ref_xyz = [QLineEdit(), QLineEdit(), QLineEdit()]
        new_xyz = [QLineEdit(), QLineEdit(), QLineEdit()]
        keep_check = QCheckBox("Keep Original (Copy)")
        new_group_edit = QLineEdit()
        new_diam_edit = QLineEdit()

        layout.addRow("Group Filter (optional):", group_edit)
        layout.addRow("Reference Point (x,y,z):", self._triple(ref_xyz))
        layout.addRow("Target Point (x,y,z):", self._triple(new_xyz))
        layout.addRow(keep_check)
        layout.addRow("New Group (copy):", new_group_edit)
        layout.addRow("New Diameter (copy):", new_diam_edit)

        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_box = QHBoxLayout()
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addRow(btn_box)

        def on_ok():
            try:
                ref = tuple(float(e.text()) for e in ref_xyz)
                newp = tuple(float(e.text()) for e in new_xyz)
                gid = int(group_edit.text()) if group_edit.text() else None
                keep = keep_check.isChecked()
                new_d = float(new_diam_edit.text()) if new_diam_edit.text() else None
                new_g = int(new_group_edit.text()) if new_group_edit.text() else None
                selected = [b for b in self.current_vbumps if gid is None or b.group == gid]
                moved = main.move_vbumps(selected, ref, newp, new_g, new_d, keep)
                if gid is not None and not keep:
                    self.current_vbumps = [b for b in self.current_vbumps if b.group != gid] + moved
                elif gid is None and not keep:
                    self.current_vbumps = [b for b in self.current_vbumps if b not in selected] + moved
                else:
                    self.current_vbumps.extend(moved)
                self.log(f"📤 Moved/duplicated {len(selected)} bumps")
                # 新增: 若 substrate_p0 和 substrate_p1 已設，則繪圖
                if self.substrate_p0 and self.substrate_p1:
                    self.plot_aabb()
                dlg.accept()
            except Exception:
                QMessageBox.warning(self, "Warning", "Invalid input values.")
        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec()

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
        ax = self.figure.add_subplot(111, projection='3d')
        # 傳入 ax 給 main 模組繪圖
        main.plot_vbumps_aabb(self.current_vbumps, self.substrate_p0, self.substrate_p1, ax=ax)
        self.canvas.draw()
        self.log("📊 AABB plotted.")

    def set_substrate_box(self):
    # 彈出一個對話框，讓使用者輸入座標
        from PySide6.QtWidgets import QDialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Set Substrate Box Coordinates")
        layout = QFormLayout(dlg)

        p0_edits = [QLineEdit(), QLineEdit(), QLineEdit()]
        p1_edits = [QLineEdit(), QLineEdit(), QLineEdit()]
        layout.addRow("Lower corner (x0, y0, z0):", self._triple(p0_edits))
        layout.addRow("Upper corner (x1, y1, z1):", self._triple(p1_edits))

        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_box = QHBoxLayout()
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addRow(btn_box)

        def on_ok():
            try:
                p0 = tuple(float(e.text()) for e in p0_edits)
                p1 = tuple(float(e.text()) for e in p1_edits)
                if len(p0) != 3 or len(p1) != 3:
                    raise ValueError
                self.substrate_p0 = p0
                self.substrate_p1 = p1
                self.log(f"🧱 Substrate box set to {p0} - {p1}")
                dlg.accept()
            except Exception:
                QMessageBox.warning(self, "Warning", "Invalid input values.")

        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec()


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    ui = VBumpUI()
    ui.show()
    sys.exit(app.exec())
