from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Callable, Tuple, Iterable

import h5py
from VBump.Basic import VBump, VBumpCollection, load_csv, load_hdf5, to_csv, to_hdf5
from VBump.CreateRectangularArea import (
    create_rectangular_area_XY_by_number_to_hdf5,
    create_rectangular_area_XY_by_pitch_to_hdf5,
)
from VBump.DXFImport import DXFVBumpImporter

HDF5_CHUNK_SIZE = 1_000_000

class VBumpLogic:
    def __init__(self, proxy_dir: Path, log_callback: Callable[[str], None]):
        self.proxy_dir = proxy_dir
        self.log = log_callback
        self.proxy_dir.mkdir(parents=True, exist_ok=True)
        self.proxy_h5_path: str | None = None
        self.current_vbumps: VBumpCollection = VBumpCollection()
        self.loaded_vbumps: VBumpCollection = VBumpCollection()
        self._dxf_importer = DXFVBumpImporter(log_callback=self.log)

    def next_proxy_path(self, stem: str) -> str:
        return str((self.proxy_dir / f"{stem}_{uuid.uuid4().hex}.h5").resolve())

    def set_active_proxy(self, path: str) -> None:
        self.proxy_h5_path = path
        proxy_markers = load_hdf5(path, only_bounding_boxes=True, log_callback=self.log)
        self.current_vbumps = proxy_markers
        self.loaded_vbumps = VBumpCollection(proxy_markers)

    def build_proxy_from_csv(self, csv_path: str) -> str:
        vbumps = load_csv(csv_path)
        target = self.next_proxy_path("load_csv")
        to_hdf5(target, vbumps, log_callback=self.log)
        return target

    def get_dxf_layers(self, dxf_path: str) -> dict[str, int]:
        return self._dxf_importer.get_layer_counts(dxf_path)

    def build_proxy_from_dxf(self, dxf_path: str, group: int, height: float, base_z: float, unit_scale: float, selected_layers: list[str] | None = None) -> str:
        self._dxf_importer.unit_scale = unit_scale
        self._dxf_importer.base_z = base_z
        vbumps, report = self._dxf_importer.import_file(dxf_path, group=group, height=height, selected_layers=selected_layers)
        self.log(
            f"✅ DXF parsed: {len(vbumps):,} bumps "
            f"(geometry={report.used_geometry}, diagnostics={report.diagnostics_count})"
        )
        target = self.next_proxy_path("load_dxf")
        to_hdf5(target, vbumps, log_callback=self.log)
        return target

    def copy_hdf5_to_proxy(self, src_path: str) -> str:
        target = self.next_proxy_path("load_h5")
        shutil.copy2(src_path, target)
        return target

    def merge_proxy_paths(self, paths: list[str]) -> str:
        out_path = self.next_proxy_path("merge")
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
                        names = list(dset_in.dtype.names or [])
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
                            overall_bbox = self._update_bbox_state(record, overall_bbox, group_bbox)

            if dset_out is None:
                raise RuntimeError("No proxy data to merge.")
            self._write_bbox_attrs(fout, dset_out, overall_bbox, group_bbox)
        return out_path

    def transform_proxy(self, transform: Callable[[dict], list[dict]], label: str) -> tuple[str, int]:
        if not self.proxy_h5_path:
            raise RuntimeError("No active proxy dataset.")

        out_path = self.next_proxy_path(label)
        written = 0
        with h5py.File(self.proxy_h5_path, "r") as fin, h5py.File(out_path, "w") as fout:
            if "vbump" not in fin:
                raise KeyError("Dataset 'vbump' not found.")
            dset_in = fin["vbump"]
            names = list(dset_in.dtype.names or [])
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
                        overall_bbox = self._update_bbox_state(item, overall_bbox, group_bbox)
                if out_records:
                    old_size = int(dset_out.shape[0])
                    chunk = len(out_records)
                    dset_out.resize((old_size + chunk,))
                    dset_out[old_size:old_size + chunk] = out_records
                    written += chunk
            self._write_bbox_attrs(fout, dset_out, overall_bbox, group_bbox)
        return out_path, written

    def copy_proxy_with_single_group(self, src_path: str, new_group: int) -> str:
        out_path = self.next_proxy_path("reassign_group")
        with h5py.File(src_path, "r") as fin, h5py.File(out_path, "w") as fout:
            if "vbump" not in fin:
                raise KeyError("Dataset 'vbump' not found.")
            dset_in = fin["vbump"]
            names = list(dset_in.dtype.names or [])
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
                    overall_bbox = self._update_bbox_state(record, overall_bbox, group_bbox)
                old_size = int(dset_out.shape[0])
                dset_out.resize((old_size + len(out_records),))
                dset_out[old_size:old_size + len(out_records)] = out_records
            self._write_bbox_attrs(fout, dset_out, overall_bbox, group_bbox)
        return out_path

    def materialize_current(self) -> VBumpCollection:
        if not self.proxy_h5_path:
            return VBumpCollection()
        return load_hdf5(self.proxy_h5_path, only_bounding_boxes=False)

    def current_source_count(self) -> int:
        return int(getattr(self.current_vbumps, "source_count", len(self.current_vbumps)))

    def get_existing_groups(self) -> set[int]:
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

    def replace_proxy(self, new_path: str, message: str) -> None:
        old = self.proxy_h5_path
        self.set_active_proxy(new_path)
        self.log(message)
        if old and Path(old) != Path(new_path):
            try:
                if str(old).startswith(str(self.proxy_dir.resolve())):
                    Path(old).unlink(missing_ok=True)
            except Exception:
                pass

    def _update_bbox_state(
        self,
        record: dict,
        overall_bbox: list[float] | None,
        group_bbox: dict[int, list[float]],
    ) -> list[float]:
        x0, y0, z0 = float(record["x0"]), float(record["y0"]), float(record["z0"])
        x1, y1, z1 = float(record["x1"]), float(record["y1"]), float(record["z1"])
        diameter = float(record["D"])
        gid = int(record["group"])
        half_d = diameter / 2.0

        x_min, x_max = min(x0, x1) - half_d, max(x0, x1) + half_d
        y_min, y_max = min(y0, y1) - half_d, max(y0, y1) + half_d
        z_min, z_max = min(z0, z1), max(z0, z1)

        if overall_bbox is None:
            overall_bbox = [x_min, y_min, z_min, x_max, y_max, z_max]
        else:
            overall_bbox[0], overall_bbox[1], overall_bbox[2] = min(overall_bbox[0], x_min), min(overall_bbox[1], y_min), min(overall_bbox[2], z_min)
            overall_bbox[3], overall_bbox[4], overall_bbox[5] = max(overall_bbox[3], x_max), max(overall_bbox[4], y_max), max(overall_bbox[5], z_max)

        bbox = group_bbox.get(gid)
        if bbox is None:
            group_bbox[gid] = [x_min, y_min, z_min, x_max, y_max, z_max]
        else:
            bbox[0], bbox[1], bbox[2] = min(bbox[0], x_min), min(bbox[1], y_min), min(bbox[2], z_min)
            bbox[3], bbox[4], bbox[5] = max(bbox[3], x_max), max(bbox[4], y_max), max(bbox[5], z_max)

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

    def compute_bounding_box(self, bumps: Iterable[VBump]) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
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
