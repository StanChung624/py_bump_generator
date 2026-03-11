from typing import Dict, List, Tuple


def _read_lines(path: str) -> List[str]:
    with open(path, "r") as file:
        return file.readlines()


def _dir_pointer(line: str) -> str:
    # Parameter data pointer occupies columns 74-80 in IGES directory lines.
    return f"{int(line[73:80].strip()):07d}P"


def _gather_param_block(lines: List[str], pointer: str) -> str:
    """Concatenate all parameter lines that belong to the given directory pointer."""
    parts: List[str] = []
    for line in lines:
        if pointer in line:
            parts.append(line.split(pointer, 1)[0].strip())
    return "".join(parts)


def _extract_level_map(lines: List[str]) -> Dict[int, str]:
    level_map: Dict[int, str] = {}
    to_skip_next_line = False
    for line in lines:
        if line[:8].strip() != "406":
            continue
        if to_skip_next_line:
            to_skip_next_line = False
            continue
        to_skip_next_line = True
        level_id = int(line[36:42].strip())
        pointer = _dir_pointer(line)
        raw_block = _gather_param_block(lines, pointer)
        trimmed = raw_block.split(";", 1)[0]
        name_parts = [part.strip() for part in trimmed.split(",")]
        level_map[level_id] = name_parts[3] if len(name_parts) > 3 else ""
    return level_map


def _parse_numeric_params(raw_block: str) -> List[float]:
    cleaned = raw_block.replace("D", "E").replace(";", "")
    values: List[float] = []
    for token in cleaned.split(","):
        token = token.strip()
        if not token:
            continue
        values.append(float(token))
    return values


def ReadIGSNurbs126(filename: str) -> Tuple[List[List[float]], List[float], List[str]]:
    """
    Parse NURBS curves (type 126) from an IGES file.

    Returns curve centers, radii, and the level names pulled from type 406 definitions.
    """

    lines = _read_lines(filename)
    level_map = _extract_level_map(lines)

    centers: List[List[float]] = []
    radii: List[float] = []
    level_names: List[str] = []

    for line in lines:
        if line[:8].strip() != "126":
            continue

        pointer = _dir_pointer(line)
        level_id = int(line[33:40].strip())
        raw_block = _gather_param_block(lines, pointer)
        if not raw_block:
            # Parameter section for this entry is missing; skip gracefully.
            continue

        try:
            params = _parse_numeric_params(raw_block)
        except ValueError:
            # Encountered a malformed numeric token; ignore this entity instead of crashing.
            continue
        if len(params) < 7:
            continue

        h = int(params[1])
        l = int(params[2])
        n_knots = h + l + 2
        n_weights = h + 1
        n_control_points = (h + 1) * 3

        expected = 7 + n_knots + n_weights + n_control_points
        if len(params) < expected:
            continue

        control_points = params[
            7 + n_knots + n_weights : 7 + n_knots + n_weights + n_control_points
        ]

        center = [0.0, 0.0, 0.0]
        # First and last control points are identical; skip the final one when averaging.
        for i in range(0, n_control_points - 3, 3):
            center[0] += control_points[i]
            center[1] += control_points[i + 1]
            center[2] += control_points[i + 2]
        divisor = (n_control_points - 3) / 3
        center = [value / divisor for value in center]

        radius = 0.0
        for i in range(0, n_control_points - 3, 3):
            x = control_points[i]
            y = control_points[i + 1]
            z = control_points[i + 2]
            radius += ((x - center[0]) ** 2 + (y - center[1]) ** 2 + (z - center[2]) ** 2) ** 0.5
        radius /= divisor

        centers.append(center)
        radii.append(radius)
        level_names.append(level_map.get(level_id, ""))

    return centers, radii, level_names


if __name__ == "__main__":
    centers, radii, level_names = ReadIGSNurbs126("./vbump_layer.igs")
    print(f"Found {len(centers)} vbumps")
    for c, r, n in zip(centers, radii, level_names):
        print(r, n, f"center = ({c[0]},{c[1]},{c[2]})")
    
