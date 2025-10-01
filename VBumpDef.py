from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List
import csv


def _emit_log(
    callback: Callable[[str], None] | None,
    message: str,
    *,
    flush: bool = False,
) -> None:
    """Send progress messages to the UI log callback when available."""
    if callback:
        callback(message)
    else:
        print(message, flush=flush)


def _require_h5py():
    try:
        import h5py  # type: ignore
    except ImportError as exc:
        raise RuntimeError("h5py is required for HDF5 support. Install it via 'pip install h5py'.") from exc
    return h5py


def _require_numpy():
    try:
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise RuntimeError("NumPy is required for HDF5 support. Install it via 'pip install numpy'.") from exc
    return np


@dataclass(slots=True)
class VBump:
    x0: float = 0.0
    y0: float = 0.0
    z0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    z1: float = 0.0
    D: float = 0.0
    group: int = 0

    @classmethod
    def from_line(cls, line: str) -> "VBump":
        splitted = line.strip().split(",")
        if len(splitted) < 7:
            raise ValueError(f"Malformed line: {line}")
        x0, y0, z0, x1, y1, z1, diameter, *rest = splitted
        group = rest[0] if rest else 0
        return cls(
            float(x0),
            float(y0),
            float(z0),
            float(x1),
            float(y1),
            float(z1),
            float(diameter),
            int(group),
        )

    @classmethod
    def from_coords(
        cls,
        x0: float,
        y0: float,
        z0: float,
        x1: float,
        y1: float,
        z1: float,
        diameter: float,
        group: int,
    ) -> "VBump":
        return cls(x0, y0, z0, x1, y1, z1, diameter, group)

    @classmethod
    def from_other(cls, other: "VBump") -> "VBump":
        return cls(
            other.x0,
            other.y0,
            other.z0,
            other.x1,
            other.y1,
            other.z1,
            other.D,
            other.group,
        )

    def __add__(self, delta: Iterable[float]) -> "VBump":
        dx, dy, dz = delta
        return VBump(
            self.x0 + dx,
            self.y0 + dy,
            self.z0 + dz,
            self.x1 + dx,
            self.y1 + dy,
            self.z1 + dz,
            self.D,
            self.group,
        )

    def __iadd__(self, delta: Iterable[float]) -> "VBump":
        dx, dy, dz = delta
        object.__setattr__(self, "x0", self.x0 + dx)
        object.__setattr__(self, "y0", self.y0 + dy)
        object.__setattr__(self, "z0", self.z0 + dz)
        object.__setattr__(self, "x1", self.x1 + dx)
        object.__setattr__(self, "y1", self.y1 + dy)
        object.__setattr__(self, "z1", self.z1 + dz)
        return self

    def mid_point(self):
        return (
            (self.x0 + self.x1) / 2,
            (self.y0 + self.y1) / 2,
            (self.z0 + self.z1) / 2,
        )

    def p0(self):
        return (self.x0, self.y0, self.z0)

    def p1(self):
        return (self.x1, self.y1, self.z1)


class VBumpCollection(list[VBump]):
    """List-like container that exposes aggregate and per-group bounding boxes."""

    def __init__(
        self,
        bumps: Iterable[VBump] | None = None,
        *,
        bounding_box: tuple[tuple[float, float, float], tuple[float, float, float]] | None = None,
        group_bounding_boxes: dict[int | str, tuple[tuple[float, float, float], tuple[float, float, float]]] | None = None,
        source_count: int | None = None,
    ) -> None:
        super().__init__(bumps or ())
        self.bounding_box = bounding_box
        self.group_bounding_boxes = group_bounding_boxes or {}
        self.source_count = source_count if source_count is not None else len(self)
        self.is_bounding_box_only = False


def to_csv(filepath, bumps: List[VBump]):
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        f.write("# Virtual Bump Configuration file. Unit:mm\n")
        f.write("# x0, y0, z0, x1, y1, z1, diameter, group\n")
        writer = csv.writer(f)
        for bump in bumps:
            writer.writerow(
                [
                    bump.x0,
                    bump.y0,
                    bump.z0,
                    bump.x1,
                    bump.y1,
                    bump.z1,
                    bump.D,
                    bump.group,
                ]
            )
    print(f"📦 Successfully saved {len(bumps)} vbumps to {filepath}.")


def load_csv(filepath) -> List[VBump]:
    ret: List[VBump] = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                ret.append(VBump.from_line(line))
            except Exception as e:
                print(f"⚠️ Skipping line due to error: {e}")
    print(f"📥 Successfully loaded {len(ret)} vbumps from {filepath}.")
    return ret


def to_hdf5(
    filepath: str,
    bumps: List[VBump],
    *,
    compression: str | int | None = 'gzip',
    chunk_size: int = 1_000_000,
    progress: bool = True,
    progress_interval: int | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> None:
    """Persist vbumps to an HDF5 file chunk-by-chunk and record bounding boxes.

    Requires h5py and numpy. Data is streamed into a structured dataset using chunks so that
    very large bump collections do not require an intermediate NumPy allocation. When bumps
    are present a `bounding_box` attribute is attached to the dataset with rows `[min, max]`
    and columns `[x, y, z]`, with x/y extents expanded by half the bump diameter. Bounding
    boxes are also recorded per group under `groups/<group>` in the HDF5 output so consumers
    can query spatial extents without filtering the dataset. Progress updates are emitted via
    ``log_callback`` when supplied.
    """
    if chunk_size <= 0:
        raise ValueError('chunk_size must be positive.')
    h5py = _require_h5py()
    np = _require_numpy()
    dtype = np.dtype([
        ('x0', np.float64),
        ('y0', np.float64),
        ('z0', np.float64),
        ('x1', np.float64),
        ('y1', np.float64),
        ('z1', np.float64),
        ('D', np.float64),
        ('group', np.int32),
    ])
    total = len(bumps)
    if total == 0:
        with h5py.File(filepath, 'w') as handle:
            handle.create_dataset('vbump', shape=(0,), maxshape=(None,), dtype=dtype)
        if progress:
            _emit_log(log_callback, '... 0/0 (0.0%)', flush=True)
        _emit_log(log_callback, f"📦 Successfully saved 0 vbumps to {filepath}.")
        return

    chunk_len = max(1, min(chunk_size, total))
    if progress:
        if progress_interval is None:
            progress_interval = max(chunk_len, total // 100 or 1)
        else:
            progress_interval = max(1, progress_interval)
    else:
        progress_interval = None

    bbox_min = [float('inf'), float('inf'), float('inf')]
    bbox_max = [float('-inf'), float('-inf'), float('-inf')]
    group_bbox: dict[int, tuple[List[float], List[float]]] = {}

    with h5py.File(filepath, 'w') as handle:
        dset = handle.create_dataset(
            'vbump',
            shape=(total,),
            maxshape=(total,),
            dtype=dtype,
            compression=compression,
            chunks=(chunk_len,),
        )
        buffer = np.empty((chunk_len,), dtype=dtype)
        buf_pos = 0
        written = 0
        last_report = 0

        for bump in bumps:
            buffer[buf_pos] = (
                bump.x0,
                bump.y0,
                bump.z0,
                bump.x1,
                bump.y1,
                bump.z1,
                bump.D,
                bump.group,
            )
            half_d = bump.D / 2.0
            x_min = min(bump.x0, bump.x1) - half_d
            x_max = max(bump.x0, bump.x1) + half_d
            y_min = min(bump.y0, bump.y1) - half_d
            y_max = max(bump.y0, bump.y1) + half_d
            z_min = min(bump.z0, bump.z1)
            z_max = max(bump.z0, bump.z1)
            if x_min < bbox_min[0]:
                bbox_min[0] = x_min
            if y_min < bbox_min[1]:
                bbox_min[1] = y_min
            if z_min < bbox_min[2]:
                bbox_min[2] = z_min
            if x_max > bbox_max[0]:
                bbox_max[0] = x_max
            if y_max > bbox_max[1]:
                bbox_max[1] = y_max
            if z_max > bbox_max[2]:
                bbox_max[2] = z_max

            group_entry = group_bbox.get(bump.group)
            if group_entry is None:
                group_entry = ([float('inf'), float('inf'), float('inf')], [float('-inf'), float('-inf'), float('-inf')])
                group_bbox[bump.group] = group_entry
            g_min, g_max = group_entry
            if x_min < g_min[0]:
                g_min[0] = x_min
            if y_min < g_min[1]:
                g_min[1] = y_min
            if z_min < g_min[2]:
                g_min[2] = z_min
            if x_max > g_max[0]:
                g_max[0] = x_max
            if y_max > g_max[1]:
                g_max[1] = y_max
            if z_max > g_max[2]:
                g_max[2] = z_max

            buf_pos += 1
            if buf_pos == chunk_len:
                dset[written:written + buf_pos] = buffer
                written += buf_pos
                buf_pos = 0
                if progress_interval and written - last_report >= progress_interval:
                    last_report = written
                    pct = written / total * 100
                    _emit_log(log_callback, f"... {written}/{total} ({pct:.1f}%)", flush=True)

        if buf_pos:
            dset[written:written + buf_pos] = buffer[:buf_pos]
            written += buf_pos
            if progress_interval and written - last_report >= progress_interval:
                last_report = written
                pct = written / total * 100
                _emit_log(log_callback, f"... {written}/{total} ({pct:.1f}%)", flush=True)

        if written:
            bbox_array = np.array([bbox_min, bbox_max], dtype=np.float64)
            dset.attrs['bounding_box'] = bbox_array
            groups_root = handle.create_group('groups')
            for group_id, (g_min, g_max) in sorted(group_bbox.items()):
                group_node = groups_root.create_group(str(group_id))
                group_node.attrs['bounding_box'] = np.array([g_min, g_max], dtype=np.float64)

    if progress_interval and written != last_report:
        pct = written / total * 100
        _emit_log(log_callback, f"... {written}/{total} ({pct:.1f}%)", flush=True)
    _emit_log(log_callback, f"📦 Successfully saved {total} vbumps to {filepath}.")


def _normalize_group_id(raw: int | str) -> int:
    if isinstance(raw, int):
        return raw
    try:
        return int(str(raw))
    except ValueError:
        return 0


def _markers_from_bbox(
    bbox_min: Iterable[float],
    bbox_max: Iterable[float],
    group: int | str,
) -> list[VBump]:
    x0, y0, z0 = bbox_min
    x1, y1, z1 = bbox_max
    gid = _normalize_group_id(group)
    return [
        VBump.from_coords(x0, y0, z0, x0, y0, z1, 0.0, gid),
        VBump.from_coords(x1, y1, z0, x1, y1, z1, 0.0, gid),
    ]


def load_hdf5(
    filepath: str,
    *,
    max_rows: int | None = None,
    only_bounding_boxes: bool | None = None,
) -> VBumpCollection:
    """Load vbumps and bounding boxes from an HDF5 file produced by to_hdf5."""
    h5py = _require_h5py()
    with h5py.File(filepath, 'r') as handle:
        if 'vbump' not in handle:
            raise KeyError("Dataset 'vbump' not found in file.")
        dataset = handle['vbump']
        total_rows = int(dataset.shape[0]) if dataset.shape else 0
        dataset_bbox_attr = dataset.attrs.get('bounding_box')

        def _normalize_bbox(raw) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
            if raw is None:
                return None
            rows = []
            for row in raw:
                if len(row) != 3:
                    raise ValueError(
                        "Expected bounding_box rows to provide three coordinates (x, y, z)."
                    )
                rows.append(tuple(float(coord) for coord in row))
            if len(rows) != 2:
                raise ValueError("Expected bounding_box to contain two rows for [min, max].")
            return (rows[0], rows[1])

        dataset_bbox = _normalize_bbox(dataset_bbox_attr)
        group_bounding_boxes: dict[int | str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {}
        if 'groups' in handle:
            groups_root = handle['groups']
            for name, subgroup in groups_root.items():
                bbox_attr = subgroup.attrs.get('bounding_box')
                if bbox_attr is None:
                    continue
                try:
                    group_id: int | str = int(name)
                except ValueError:
                    group_id = name
                normalized = _normalize_bbox(bbox_attr)
                if normalized is not None:
                    group_bounding_boxes[group_id] = normalized
        if only_bounding_boxes is None:
            use_bounding_boxes = max_rows is not None and total_rows >= max_rows
        else:
            use_bounding_boxes = bool(only_bounding_boxes)

        result = VBumpCollection(
            bounding_box=dataset_bbox,
            group_bounding_boxes=group_bounding_boxes,
            source_count=total_rows,
        )
        result.is_bounding_box_only = use_bounding_boxes

        if use_bounding_boxes:
            markers: list[VBump] = []
            if group_bounding_boxes:
                for group_id, (g_min, g_max) in group_bounding_boxes.items():
                    markers.extend(_markers_from_bbox(g_min, g_max, group_id))
            elif dataset_bbox is not None:
                markers.extend(_markers_from_bbox(dataset_bbox[0], dataset_bbox[1], 0))
            result.extend(markers)
        else:
            data = dataset[...]
            for row in data:
                result.append(
                    VBump.from_coords(
                        float(row['x0']),
                        float(row['y0']),
                        float(row['z0']),
                        float(row['x1']),
                        float(row['y1']),
                        float(row['z1']),
                        float(row['D']),
                        int(row['group']),
                    )
                )
        print(f"📥 Successfully loaded {len(result)} vbumps from {filepath} (source rows: {total_rows}).")
        return result


if __name__ == "__main__":
    to_csv('h5_model_Run1.csv',load_hdf5('model_Run1.h5'))
