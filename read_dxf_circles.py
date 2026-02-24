from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any, Iterable
import math
import numpy as np

from VBump.Basic import VBump, to_csv
from VBump.VBumpPlot import plot_vbumps

from VBump.ExportVTP import write_vbumps_vtp


@dataclass
class Polyline2D:
    layer: str = ""
    is_closed: bool = False
    vertices: List[Tuple[float, float]] = None

    def __post_init__(self):
        if self.vertices is None:
            self.vertices = []


@dataclass
class CircleFit:
    cx: float
    cy: float
    r: float
    rms: float
    npts: int
    layer: str
    is_closed: bool


@dataclass
class BlockDef:
    name: str
    base_x: float = 0.0
    base_y: float = 0.0
    polylines: List[Polyline2D] = None

    def __post_init__(self):
        if self.polylines is None:
            self.polylines = []


@dataclass
class InsertRef:
    layer: str = ""
    block_name: str = ""
    x: float = 0.0
    y: float = 0.0
    sx: float = 1.0
    sy: float = 1.0
    rot_deg: float = 0.0


def _iter_pairs(lines: List[str]):
    """Yield (group_code:int, value:str) pairs from DXF ASCII lines."""
    it = iter(lines)
    for code_line in it:
        code_line = code_line.strip()
        if code_line == "":
            continue
        try:
            code = int(code_line)
        except ValueError:
            # bad DXF line; skip
            continue
        try:
            value = next(it).rstrip("\n")
        except StopIteration:
            break
        yield code, value.strip()


def parse_dxf_polylines(path: str) -> List[Polyline2D]:
    """
    Parse ASCII DXF and extract POLYLINE entities (with VERTEX points).

    Notes:
    - This targets classic R12-style POLYLINE/VERTEX/SEQEND.
    - We collect 2D XY from group codes 10/20 (Z ignored).
    - POLYLINE can appear in BLOCKS or ENTITIES; we accept it anywhere.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    polylines: List[Polyline2D] = []

    cur_pl: Optional[Polyline2D] = None
    in_vertex = False
    vx: Optional[float] = None
    vy: Optional[float] = None

    def commit_vertex():
        nonlocal vx, vy, in_vertex, cur_pl
        if cur_pl is None:
            vx = vy = None
            in_vertex = False
            return
        if in_vertex and vx is not None and vy is not None:
            cur_pl.vertices.append((vx, vy))
        vx = vy = None
        in_vertex = False

    for code, value in _iter_pairs(lines):
        # Entity boundaries
        if code == 0 and value == "POLYLINE":
            # Starting a new polyline: close any dangling vertex/polyline safely
            commit_vertex()
            # If there was an un-SEQEND'ed polyline (malformed DXF), store it
            if cur_pl is not None:
                polylines.append(cur_pl)
            cur_pl = Polyline2D(layer="", is_closed=False, vertices=[])
            continue

        if code == 0 and value == "VERTEX":
            # New vertex begins: commit the previous one
            commit_vertex()
            if cur_pl is not None:
                in_vertex = True
            continue

        if code == 0 and value == "SEQEND":
            # End of vertex sequence for current polyline
            commit_vertex()
            if cur_pl is not None:
                polylines.append(cur_pl)
            cur_pl = None
            continue

        # Polyline-level properties
        if cur_pl is not None and not in_vertex:
            if code == 8:
                cur_pl.layer = value
            elif code == 70:
                try:
                    flags = int(value)
                    cur_pl.is_closed = bool(flags & 1)
                except ValueError:
                    pass

        # Vertex coordinates (only meaningful while inside a VERTEX)
        if cur_pl is not None and in_vertex:
            if code == 10:
                try:
                    vx = float(value)
                except ValueError:
                    vx = None
            elif code == 20:
                try:
                    vy = float(value)
                except ValueError:
                    vy = None

    # EOF: commit anything pending
    commit_vertex()
    if cur_pl is not None:
        polylines.append(cur_pl)

    return polylines


def fit_circle_least_squares(points: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    """
    Algebraic least squares fit:
        x^2 + y^2 + D x + E y + F = 0
    Returns (cx, cy, r, rms_error).
    """
    if len(points) < 3:
        raise ValueError("Need at least 3 points to fit a circle.")

    x = np.array([p[0] for p in points], dtype=float)
    y = np.array([p[1] for p in points], dtype=float)

    A = np.column_stack([x, y, np.ones_like(x)])
    b = -(x * x + y * y)

    # Solve A*[D,E,F]^T = b
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    D, E, F = sol.tolist()

    cx = -D / 2.0
    cy = -E / 2.0
    rr = cx * cx + cy * cy - F
    r = math.sqrt(rr) if rr > 0 else float("nan")

    # RMS error based on radial residuals
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    resid = dist - r
    rms = float(np.sqrt(np.mean(resid ** 2)))

    return cx, cy, r, rms


def extract_circles_from_polylines(
    polylines: List[Polyline2D],
    *,
    require_closed: bool = True,
    min_points: int = 8,
    max_rms: float = 1e-2,
) -> List[CircleFit]:
    """
    Fit circles for each polyline and filter by heuristics.
    - require_closed: only consider closed polylines (flag 70 bit 1)
    - min_points: skip small point sets
    - max_rms: skip if fitting RMS too large (units same as DXF coords)
    """
    results: List[CircleFit] = []

    for pl in polylines:
        if require_closed and not pl.is_closed:
            continue
        if len(pl.vertices) < min_points:
            continue

        # Some exporters repeat the first point at the end; remove duplicate tail if present
        pts = pl.vertices[:]
        if len(pts) >= 2 and (abs(pts[0][0] - pts[-1][0]) < 1e-12 and abs(pts[0][1] - pts[-1][1]) < 1e-12):
            pts = pts[:-1]

        try:
            cx, cy, r, rms = fit_circle_least_squares(pts)
        except Exception:
            continue

        if not math.isfinite(r) or r <= 0:
            continue
        if rms > max_rms:
            continue

        results.append(CircleFit(cx=cx, cy=cy, r=r, rms=rms, npts=len(pts), layer=pl.layer, is_closed=pl.is_closed))

    return results


def _transform_point_local_to_world(
    x: float,
    y: float,
    ins: InsertRef,
    base_x: float,
    base_y: float,
) -> Tuple[float, float]:
    """Apply DXF INSERT transform to a local (block) point."""
    # Translate to block base point, then scale
    lx = (x - base_x) * ins.sx
    ly = (y - base_y) * ins.sy

    # Rotate (degrees)
    th = math.radians(ins.rot_deg)
    c = math.cos(th)
    s = math.sin(th)
    rx = lx * c - ly * s
    ry = lx * s + ly * c

    # Translate to insert point
    return ins.x + rx, ins.y + ry


def parse_blocks_and_inserts(path: str) -> Tuple[Dict[str, BlockDef], List[InsertRef]]:
    """Parse ASCII DXF: collect BLOCK definitions and INSERT references."""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    blocks: Dict[str, BlockDef] = {}
    inserts: List[InsertRef] = []

    cur_block: Optional[BlockDef] = None
    in_block_header = False

    cur_insert: Optional[InsertRef] = None
    in_insert = False

    # POLYLINE/VERTEX state (within a BLOCK)
    cur_pl: Optional[Polyline2D] = None
    in_vertex = False
    vx: Optional[float] = None
    vy: Optional[float] = None

    def commit_vertex():
        nonlocal vx, vy, in_vertex, cur_pl
        if cur_pl is not None and in_vertex and vx is not None and vy is not None:
            cur_pl.vertices.append((vx, vy))
        vx = vy = None
        in_vertex = False

    def commit_polyline_into_block():
        nonlocal cur_pl
        if cur_pl is None:
            return
        commit_vertex()
        if cur_block is not None:
            cur_block.polylines.append(cur_pl)
        cur_pl = None

    def commit_insert():
        nonlocal cur_insert, in_insert
        if cur_insert is not None and cur_insert.block_name:
            inserts.append(cur_insert)
        cur_insert = None
        in_insert = False

    for code, value in _iter_pairs(lines):
        if code == 0:
            # Entity boundaries
            if value == "BLOCK":
                commit_insert()
                commit_polyline_into_block()
                cur_block = BlockDef(name="")
                in_block_header = True
                continue

            if value == "ENDBLK":
                commit_insert()
                commit_polyline_into_block()
                if cur_block is not None and cur_block.name:
                    blocks[cur_block.name] = cur_block
                cur_block = None
                in_block_header = False
                continue

            if value == "INSERT":
                commit_polyline_into_block()
                commit_insert()
                cur_insert = InsertRef()
                in_insert = True
                continue

            if value == "POLYLINE":
                # We only care about polylines that are inside a BLOCK (template geometry)
                commit_polyline_into_block()
                if cur_block is not None:
                    cur_pl = Polyline2D(layer="", is_closed=False, vertices=[])
                else:
                    cur_pl = None
                continue

            if value == "VERTEX":
                # Start a new vertex (commit previous one)
                commit_vertex()
                if cur_pl is not None:
                    in_vertex = True
                continue

            if value == "SEQEND":
                commit_polyline_into_block()
                continue

            # Any other entity starts
            commit_vertex()
            commit_polyline_into_block()
            commit_insert()
            continue

        # BLOCK header
        if cur_block is not None and in_block_header and not in_insert and cur_pl is None:
            if code == 2:
                cur_block.name = value
            elif code == 10:
                try:
                    cur_block.base_x = float(value)
                except ValueError:
                    pass
            elif code == 20:
                try:
                    cur_block.base_y = float(value)
                except ValueError:
                    pass
            continue

        # INSERT fields
        if in_insert and cur_insert is not None:
            if code == 8:
                cur_insert.layer = value
            elif code == 2:
                cur_insert.block_name = value
            elif code == 10:
                try:
                    cur_insert.x = float(value)
                except ValueError:
                    pass
            elif code == 20:
                try:
                    cur_insert.y = float(value)
                except ValueError:
                    pass
            elif code == 41:
                try:
                    cur_insert.sx = float(value)
                except ValueError:
                    pass
            elif code == 42:
                try:
                    cur_insert.sy = float(value)
                except ValueError:
                    pass
            elif code == 50:
                try:
                    cur_insert.rot_deg = float(value)
                except ValueError:
                    pass
            continue

        # POLYLINE-level properties (only when not in vertex)
        if cur_pl is not None and not in_vertex:
            if code == 8:
                cur_pl.layer = value
            elif code == 70:
                try:
                    flags = int(value)
                    cur_pl.is_closed = bool(flags & 1)
                except ValueError:
                    pass
            continue

        # VERTEX coordinates
        if cur_pl is not None and in_vertex:
            if code == 10:
                try:
                    vx = float(value)
                except ValueError:
                    vx = None
            elif code == 20:
                try:
                    vy = float(value)
                except ValueError:
                    vy = None
            continue

    # EOF flush
    commit_vertex()
    commit_polyline_into_block()
    commit_insert()
    if cur_block is not None and cur_block.name:
        blocks[cur_block.name] = cur_block

    return blocks, inserts


def extract_circles_from_inserts(
    dxf_path: str,
    *,
    require_closed: bool = True,
    min_points: int = 6,
    max_rms: float = 1e-2,
    scale_tol: float = 1e-6,
) -> List[CircleFit]:
    """
    Extract circles from DXF where a BLOCK contains a circle-like POLYLINE,
    and many instances are placed via INSERT.

    Returns one CircleFit per INSERT (per template circle; typically one).
    """
    blocks, inserts = parse_blocks_and_inserts(dxf_path)

    # Fit template circles for each block name
    tmpl: Dict[str, List[CircleFit]] = {}
    for bname, b in blocks.items():
        fitted = extract_circles_from_polylines(
            b.polylines,
            require_closed=require_closed,
            min_points=min_points,
            max_rms=max_rms,
        )
        if fitted:
            tmpl[bname] = fitted

    out: List[CircleFit] = []
    for ins in inserts:
        if ins.block_name not in tmpl:
            continue
        b = blocks.get(ins.block_name)
        if b is None:
            continue

        for tc in tmpl[ins.block_name]:
            # Transform template center
            cxw, cyw = _transform_point_local_to_world(tc.cx, tc.cy, ins, b.base_x, b.base_y)

            # Radius scaling: exact only for uniform scale
            if abs(ins.sx - ins.sy) <= scale_tol:
                rw = tc.r * ins.sx
            else:
                # Non-uniform scale makes a circle into an ellipse; use geometric mean as an approximation
                rw = tc.r * math.sqrt(abs(ins.sx * ins.sy))

            out.append(CircleFit(
                cx=cxw,
                cy=cyw,
                r=rw,
                rms=tc.rms,
                npts=tc.npts,
                layer=ins.layer,
                is_closed=True,
            ))

    return out


if __name__ == "__main__":
    dxf_path = "Package with multiple bumps.DXF"  # <- 改成你的檔名

    # INSERT-based extraction (recommended for your DXF: many circles are instances of the same BLOCK)
    circles = extract_circles_from_inserts(
        dxf_path,
        require_closed=True,
        min_points=6,
        max_rms=1e-2,  # 依你 DXF 單位調整：越小越嚴格
    )

    print(f"Found {len(circles)} circles (via INSERT)")

    # Fallback / debug: direct POLYLINE extraction (template geometry only)
    # polylines = parse_dxf_polylines(dxf_path)
    # print(f"Found {len(polylines)} polylines")
    # circles = extract_circles_from_polylines(polylines, require_closed=True, min_points=6, max_rms=1e-2)
    # print(f"Found {len(circles)} circles (via POLYLINE)")

    um2mm = 0.001

    vbumps = []
    for c in circles:
        vbumps.append(VBump(
            x0=c.cx*um2mm, y0=c.cy*um2mm, z0=0,
            x1=c.cx*um2mm, y1=c.cy*um2mm, z1=10,
            D = c.r *2*um2mm
        ))

    write_vbumps_vtp(vbumps, "single_chip.vtp")      
    to_csv("single_chip.csv", vbumps)
    # plot_vbumps(vbumps)