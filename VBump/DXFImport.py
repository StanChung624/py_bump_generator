from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import sys
from typing import Iterable, List, Callable
from VBump.Basic import VBump, _require_numpy


@dataclass(slots=True)
class DXFImportReport:
    source_path: str
    used_geometry: str
    circles_used: int
    polylines_used: int
    diagnostics_count: int


def _ensure_dxfextractor_available() -> None:
    # When running as a PyInstaller frozen exe, dxf_extract is already bundled
    # into the exe — no sys.path manipulation needed.
    if getattr(sys, "frozen", False):
        return
    root_dir = Path(__file__).resolve().parents[1]
    extractor_root = root_dir / "external" / "dxfextractor"
    if extractor_root.exists():
        root_text = str(extractor_root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)


def _fit_circle_least_squares(points: Iterable[tuple[float, float]]) -> tuple[float, float, float, float]:
    np = _require_numpy()
    pts = list(points)
    if len(pts) < 3:
        raise ValueError("Need at least 3 points to fit a circle.")

    x = np.array([p[0] for p in pts], dtype=float)
    y = np.array([p[1] for p in pts], dtype=float)
    a = np.column_stack([x, y, np.ones_like(x)])
    b = -(x * x + y * y)

    sol, *_ = np.linalg.lstsq(a, b, rcond=None)
    d, e, f = sol.tolist()
    cx = -d / 2.0
    cy = -e / 2.0
    rr = cx * cx + cy * cy - f
    r = math.sqrt(rr) if rr > 0 else float("nan")
    if not math.isfinite(r) or r <= 0.0:
        raise ValueError("Invalid fitted radius.")

    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    rms = float(np.sqrt(np.mean((dist - r) ** 2)))
    return cx, cy, r, rms


def _sample_segment_with_bulge(
    p0: tuple[float, float],
    p1: tuple[float, float],
    bulge: float,
    max_step_deg: float = 15.0,
) -> list[tuple[float, float]]:
    if math.isclose(bulge, 0.0, abs_tol=1e-12):
        return [p0, p1]

    x0, y0 = p0
    x1, y1 = p1
    dx = x1 - x0
    dy = y1 - y0
    chord = math.hypot(dx, dy)
    if chord <= 1e-12:
        return [p0]

    theta = 4.0 * math.atan(bulge)
    radius = chord * (1.0 + bulge * bulge) / (4.0 * abs(bulge))

    mx = (x0 + x1) * 0.5
    my = (y0 + y1) * 0.5
    half_chord = chord * 0.5
    h2 = max(radius * radius - half_chord * half_chord, 0.0)
    h = math.sqrt(h2)
    nx = -dy / chord
    ny = dx / chord
    sign = 1.0 if bulge > 0.0 else -1.0
    cx = mx + sign * nx * h
    cy = my + sign * ny * h

    a0 = math.atan2(y0 - cy, x0 - cx)
    n_steps = max(2, int(math.ceil(abs(math.degrees(theta)) / max_step_deg)) + 1)
    ret: list[tuple[float, float]] = []
    for i in range(n_steps):
        t = i / (n_steps - 1)
        ang = a0 + t * theta
        ret.append((cx + radius * math.cos(ang), cy + radius * math.sin(ang)))
    return ret


def _polyline_to_points(polyline) -> list[tuple[float, float]]:
    verts = list(polyline.vertices)
    if len(verts) < 2:
        return []

    points: list[tuple[float, float]] = []
    n = len(verts)
    for i in range(n):
        v0 = verts[i]
        v1 = verts[(i + 1) % n]
        seg = _sample_segment_with_bulge((v0.x, v0.y), (v1.x, v1.y), float(v0.bulge))
        if points:
            points.extend(seg[1:])
        else:
            points.extend(seg)
    return points


class DXFVBumpImporter:
    def __init__(
        self,
        *,
        unit_scale: float = 0.001,
        base_z: float = 0.0,
        min_points: int = 6,
        max_rms: float = 1e-2,
        prefer_circles: bool = True,
        log_callback:Callable[[str], None] | None = None,
    ) -> None:
        self.unit_scale = unit_scale
        self.base_z = base_z
        self.min_points = min_points
        self.max_rms = max_rms
        self.prefer_circles = prefer_circles
        self.log = log_callback
        self._cached_result = None
        self._cached_path = None

    def _get_extraction_result(self, path: str):
        if self._cached_path == path and self._cached_result is not None:
            return self._cached_result
        
        _ensure_dxfextractor_available()
        try:
            from dxf_extract import extract_geometry
        except Exception as exc:
            raise RuntimeError(
                f"Failed to import dxf_extract. Error: {exc}. Ensure external/dxfextractor is present and ezdxf is installed."
            ) from exc

        result = extract_geometry(path, log_callback=self.log)
        self._cached_path = path
        self._cached_result = result
        return result

    def get_layer_counts(self, path: str) -> dict[str, int]:
        result = self._get_extraction_result(path)
        counts = {}
        
        # We also want to include all layers from the document even if they have 0 geometry
        import ezdxf
        doc = ezdxf.readfile(path)
        for layer in doc.layers:
            counts[layer.dxf.name] = 0

        for c in result.circles:
            layer = c.source.layer if c.source else "0"
            counts[layer] = counts.get(layer, 0) + 1
            
        for p in result.closed_polylines:
            layer = p.source.layer if p.source else "0"
            counts[layer] = counts.get(layer, 0) + 1
            
        return counts

    def import_file(self, path: str, *, group: int = 1, height: float = 10.0, selected_layers: list[str] | None = None) -> tuple[List[VBump], DXFImportReport]:
        if height == 0.0:
            raise ValueError("height must not be zero.")
        if self.unit_scale == 0.0:
            raise ValueError("unit_scale must not be zero.")

        result = self._get_extraction_result(path)
        circles_to_use = result.circles
        polylines_to_use = result.closed_polylines

        if selected_layers is not None:
            circles_to_use = [c for c in circles_to_use if c.source and c.source.layer in selected_layers]
            polylines_to_use = [p for p in polylines_to_use if p.source and p.source.layer in selected_layers]

        if self.prefer_circles and circles_to_use:
            polylines_to_use = []

        vbumps: List[VBump] = []
        for circle in circles_to_use:
            x = circle.center[0] * self.unit_scale
            y = circle.center[1] * self.unit_scale
            diameter = 2.0 * circle.radius * abs(self.unit_scale)
            vbumps.append(
                VBump.from_coords(
                    x,
                    y,
                    self.base_z,
                    x,
                    y,
                    self.base_z + height,
                    diameter,
                    int(group),
                )
            )

        polylines_used = 0
        if polylines_to_use:
            for pl in polylines_to_use:
                pts = _polyline_to_points(pl)
                if len(pts) < self.min_points:
                    continue
                try:
                    cx, cy, r, rms = _fit_circle_least_squares(pts)
                except Exception:
                    continue
                if rms > self.max_rms:
                    continue
                x = cx * self.unit_scale
                y = cy * self.unit_scale
                diameter = 2.0 * r * abs(self.unit_scale)
                vbumps.append(
                    VBump.from_coords(
                        x,
                        y,
                        self.base_z,
                        x,
                        y,
                        self.base_z + height,
                        diameter,
                        int(group),
                    )
                )
                polylines_used += 1

        used_geometry = "circle" if circles_to_use else ("polyline_fit" if polylines_used else "none")
        report = DXFImportReport(
            source_path=path,
            used_geometry=used_geometry,
            circles_used=len(circles_to_use),
            polylines_used=polylines_used,
            diagnostics_count=len(result.diagnostics),
        )
        return vbumps, report
