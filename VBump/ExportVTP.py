from __future__ import annotations

import base64
import struct
from pathlib import Path
from typing import Iterable, List
from VBump.Basic import VBump

def _pack_f32_le(values: Iterable[float]) -> bytes:
    # little-endian float32
    return struct.pack("<%sf" % len(values), *values)


def _pack_i32_le(values: Iterable[int]) -> bytes:
    return struct.pack("<%si" % len(values), *values)


def _pack_u8_le(values: Iterable[int]) -> bytes:
    return struct.pack("<%sB" % len(values), *values)


def _vtk_b64_block(raw: bytes) -> str:
    """
    VTK XML inline binary DataArray (format="binary", encoding="base64"):
    [4-byte little-endian header = raw_byte_length] + raw_bytes
    """
    header = struct.pack("<I", len(raw))
    blob = header + raw
    return base64.b64encode(blob).decode("ascii")


def write_vbumps_vtp(
    vbumps: List["VBump"],
    out_path: str | Path,
    *,
    include_point_data: bool = False,
) -> None:
    """
    每個 VBump -> 一條線段 (2 points, 1 line cell)
    CellData: D(float32), group(int32)
    Points: float32
    Lines: connectivity(int32), offsets(int32)
    """
    n = len(vbumps)
    out_path = Path(out_path)

    # --- Points: 2*n points, each 3 floats ---
    # point index for i-th segment: p0=2*i, p1=2*i+1
    pts = []
    for b in vbumps:
        pts.extend([b.x0, b.y0, b.z0, b.x1, b.y1, b.z1])
    pts_bytes = _pack_f32_le(pts)

    # --- Lines connectivity & offsets ---
    # VTK PolyData Lines: connectivity is flattened point indices
    # offsets is cumulative length (2,4,6,...)
    conn = []
    offsets = []
    for i in range(n):
        conn.extend([2 * i, 2 * i + 1])
        offsets.append(2 * (i + 1))
    conn_bytes = _pack_i32_le(conn)
    offsets_bytes = _pack_i32_le(offsets)

    # --- Cell data ---
    Ds = [float(b.D) for b in vbumps]
    groups = [int(b.group) for b in vbumps]
    D_bytes = _pack_f32_le(Ds)
    group_bytes = _pack_i32_le(groups)

    # Optional: PointData（通常不需要；而且 VBump 的屬性是線段層級）
    point_data_xml = ""
    if include_point_data:
        # 這裡示範：把 group/D 複製到兩端點（2*n 個）
        pD = []
        pG = []
        for b in vbumps:
            pD.extend([float(b.D), float(b.D)])
            pG.extend([int(b.group), int(b.group)])
        pD_bytes = _pack_f32_le(pD)
        pG_bytes = _pack_i32_le(pG)

        point_data_xml = f"""
    <PointData>
      <DataArray type="Float32" Name="D" NumberOfComponents="1" format="binary" encoding="base64">
        {_vtk_b64_block(pD_bytes)}
      </DataArray>
      <DataArray type="Int32" Name="group" NumberOfComponents="1" format="binary" encoding="base64">
        {_vtk_b64_block(pG_bytes)}
      </DataArray>
    </PointData>
"""

    xml = f"""<?xml version="1.0"?>
<VTKFile type="PolyData" version="0.1" byte_order="LittleEndian">
  <PolyData>
    <Piece NumberOfPoints="{2*n}" NumberOfLines="{n}">
      <Points>
        <DataArray type="Float32" NumberOfComponents="3" format="binary" encoding="base64">
          {_vtk_b64_block(pts_bytes)}
        </DataArray>
      </Points>
{point_data_xml}
      <CellData>
        <DataArray type="Float32" Name="D" NumberOfComponents="1" format="binary" encoding="base64">
          {_vtk_b64_block(D_bytes)}
        </DataArray>
        <DataArray type="Int32" Name="group" NumberOfComponents="1" format="binary" encoding="base64">
          {_vtk_b64_block(group_bytes)}
        </DataArray>
      </CellData>

      <Lines>
        <DataArray type="Int32" Name="connectivity" format="binary" encoding="base64">
          {_vtk_b64_block(conn_bytes)}
        </DataArray>
        <DataArray type="Int32" Name="offsets" format="binary" encoding="base64">
          {_vtk_b64_block(offsets_bytes)}
        </DataArray>
      </Lines>
    </Piece>
  </PolyData>
</VTKFile>
"""
    out_path.write_text(xml, encoding="utf-8")
