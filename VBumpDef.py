from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List
import csv


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


def to_hdf5(filepath: str, bumps: List[VBump], *, compression: str | int | None = 'gzip') -> None:
    """Persist vbumps to an HDF5 file using a structured dataset and record the bounding box.

    Requires h5py and numpy. When bumps are present a `bounding_box` attribute is attached to
    the dataset with rows `[min, max]` and columns `[x, y, z]`, with x/y extents expanded by
    half the bump diameter.
    """
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
    data = np.empty((len(bumps),), dtype=dtype)
    bbox_min = [float("inf"), float("inf"), float("inf")]
    bbox_max = [float("-inf"), float("-inf"), float("-inf")]
    for idx, bump in enumerate(bumps):
        data[idx] = (
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
    with h5py.File(filepath, 'w') as handle:
        dset = handle.create_dataset('vbump', data=data, compression=compression)
        if len(bumps) > 0:
            dset.attrs['bounding_box'] = np.array([bbox_min, bbox_max], dtype=np.float64)
    print(f"📦 Successfully saved {len(bumps)} vbumps to {filepath}.")


def load_hdf5(filepath: str) -> List[VBump]:
    """Load vbumps from an HDF5 file produced by to_hdf5. Requires h5py and numpy."""
    h5py = _require_h5py()
    with h5py.File(filepath, 'r') as handle:
        if 'vbump' not in handle:
            raise KeyError("Dataset 'vbump' not found in file.")
        data = handle['vbump'][...]
    result: List[VBump] = []
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
    print(f"📥 Successfully loaded {len(result)} vbumps from {filepath}.")
    return result


if __name__ == "__main__":
    to_csv('h5_model_Run1.csv',load_hdf5('model_Run1.h5'))
