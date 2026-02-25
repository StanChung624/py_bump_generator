# DXF Circle (Bump) Extraction Specification  
**for `read_dxf_circles.py`**

## 1. Purpose
This specification defines the **required CAD / DXF structure** for extracting circular bumps using `read_dxf_circles.py`.

The script identifies circles by:
- Fitting **closed POLYLINE geometry** inside **BLOCK definitions**
- Instantiating circles via **INSERT references**

Only DXF files that comply with this specification are guaranteed to produce correct bump extraction results.

---

## 2. Supported DXF Format
- **DXF Type**: ASCII DXF
- **Recommended Version**: AutoCAD R12–R2000 compatible
- **Geometry Style**: Classic `POLYLINE / VERTEX / SEQEND`
- **Coordinate System**: 2D XY (Z is ignored)

Binary DXF is **not supported**.

---

## 3. Required Geometry Representation

### 3.1 Circle Representation (MANDATORY)
Each bump **must be represented as a closed POLYLINE approximating a circle**.

**Requirements**

| Item | Requirement |
|---|---|
| Entity type | `POLYLINE` |
| Closure | `70` flag includes bit `1` (closed) |
| Vertex type | `VERTEX` |
| Minimum vertices | ≥ **6** (recommended ≥ **12**) |
| Planarity | All vertices lie in XY plane |
| Shape | Approximately circular (low RMS error) |

> ⚠️ Native DXF entities such as `CIRCLE`, `ARC`, `ELLIPSE`, or `LWPOLYLINE` are **not recognized**.

---

### 3.2 Block Definition (MANDATORY)
Each unique bump geometry **must be defined inside a BLOCK**.

**Required BLOCK structure**
```
0
BLOCK
2
<BLOCK_NAME>
10
<BASE_X>
20
<BASE_Y>
...
0
POLYLINE
...
0
ENDBLK
```

**Rules**
- The circle polyline **must be inside the BLOCK**
- `BLOCK` base point (`10/20`) should represent the logical origin of the bump
- One BLOCK may contain **one or more circular polylines**
- Non-circular geometry inside the block is ignored

---

### 3.3 INSERT Placement (MANDATORY)
Each bump instance **must be placed via INSERT**.

**Supported INSERT fields**

| Group code | Meaning | Required |
|---|---|---|
| `2` | Block name | ✅ |
| `10`, `20` | Insert position (XY) | ✅ |
| `41`, `42` | Scale X / Y | Optional (default = 1.0) |
| `50` | Rotation (degrees) | Optional (default = 0) |
| `8` | Layer name | Optional |

**Rules**
- Uniform scaling is recommended (`sx == sy`)
- Non-uniform scaling is supported but treated as **approximate circle**
- Z-related fields are ignored

---

## 4. Layer Usage
- BLOCK internal polyline layer is **not preserved**
- Output bump layer is taken from the **INSERT layer (`code 8`)**
- Layer name has no functional effect on geometry extraction

---

## 5. Units & Coordinate System

### 5.1 Units
- DXF units are assumed to be **micrometers (µm)** by default
- Conversion factor in code:
```
um2mm = 0.001
```
- Users must ensure CAD geometry is authored in the expected unit system

> ⚠️ `$INSUNITS` is ignored — units are **user responsibility**

---

### 5.2 Coordinate Constraints
- 2D geometry only (Z ignored)
- Extremely small or large coordinates may affect fitting accuracy
- Circle RMS error must be below the configured threshold

---

## 6. Circle Qualification Criteria
Each candidate polyline is fitted using least-squares circle fitting and must satisfy:

| Criterion | Default |
|---|---|
| Closed polyline | Required |
| Minimum points | ≥ 6 |
| RMS error | ≤ `1e-2` (DXF units) |
| Radius | > 0 |

These parameters are configurable in:
```
extract_circles_from_inserts(
    require_closed=True,
    min_points=6,
    max_rms=1e-2
)
```

---

## 7. Unsupported / Ignored Features
The following DXF features are ignored and should not be relied upon:

- `CIRCLE`, `ARC`, `ELLIPSE`, `SPLINE`
- `LWPOLYLINE`
- 3D geometry (`Z`, `UCS`, `OCS`)
- Attributes (`ATTRIB`, `ATTDEF`)
- `$INSUNITS`, `$UCS`, `$EXTMIN/MAX`
- Nested INSERTs (BLOCK within BLOCK)

---

## 8. Recommended CAD Authoring Workflow

1. Draw a circle using native CIRCLE
2. Convert circle to **POLYLINE** (≥ 12 segments recommended)
3. Ensure polyline is **closed**
4. Create a BLOCK from the polyline
5. Insert the BLOCK at all bump locations using INSERT
6. Export as **ASCII DXF**

---

## 9. Validation Checklist
Before running the parser, confirm:

- [ ] DXF is ASCII
- [ ] Circles are POLYLINE (not CIRCLE)
- [ ] POLYLINE is closed
- [ ] Geometry is inside BLOCK
- [ ] Bumps are placed using INSERT
- [ ] Units match script assumptions
- [ ] No reliance on Z coordinates

---

## 10. Known Limitations
- Non-uniform scaling creates elliptical geometry (approximated)
- Poorly segmented circles may fail RMS threshold
- Malformed DXF (missing SEQEND) may produce undefined results
