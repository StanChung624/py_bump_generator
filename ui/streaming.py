"""Background worker objects used by the Qt UI."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot


class HDF5StreamWorker(QObject):
    """Run long running HDF5 streaming tasks without blocking the UI."""

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
        except Exception as exc:  # pragma: no cover - UI feedback path
            self.error.emit(str(exc))
