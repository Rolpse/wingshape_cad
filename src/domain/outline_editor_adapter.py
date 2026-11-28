"""Import standalone SurfWing outline-editor JSON into Shape Document v0.1.0.

The editor stores screen-planform coordinates as (transverse, longitudinal).
The canonical document stores board planform coordinates as (longitudinal,
transverse). This adapter performs that axis mapping, updates station widths
from the imported outline, and invalidates derived properties.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import uuid
from pathlib import Path
from typing import Any

from src.domain.shape_document import dumps_document, validate_shape_document


CONTINUITY = {
    "corner": "corner",
    "smooth": "smooth_aligned",
    "smooth_aligned": "smooth_aligned",
    "symmetric": "symmetric",
}


def _finite_pair(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{label} must contain exactly two millimetre coordinates")
    pair = (float(value[0]), float(value[1]))
    if not all(math.isfinite(v) for v in pair):
        raise ValueError(f"{label} contains a non-finite coordinate")
    return pair


def _bezier(p0, p1, p2, p3, t: float) -> tuple[float, float]:
    u = 1.0 - t
    return (
        u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0],
        u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1],
    )


def _flatten_outline(anchors: list[dict[str, Any]], steps: int = 96) -> list[tuple[float, float]]:
    points = [(anchors[0]["position"][1], anchors[0]["position"][0])]
    for i, current in enumerate(anchors):
        nxt = anchors[(i + 1) % len(anchors)]
        p0 = (current["position"][1], current["position"][0])
        p1 = (current["outgoing_handle"][1], current["outgoing_handle"][0])
        p2 = (nxt["incoming_handle"][1], nxt["incoming_handle"][0])
        p3 = (nxt["position"][1], nxt["position"][0])
        for k in range(1, steps + 1):
            points.append(_bezier(p0, p1, p2, p3, k / steps))
    return points


def _orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, p, eps: float) -> bool:
    return (
        min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps
    )


def _segments_intersect(a, b, c, d) -> bool:
    scale = max(
        1.0,
        math.dist(a, b),
        math.dist(c, d),
    )
    eps = 1e-9 * scale * scale
    o1, o2 = _orient(a, b, c), _orient(a, b, d)
    o3, o4 = _orient(c, d, a), _orient(c, d, b)
    if ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and (
        (o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps)
    ):
        return True
    if abs(o1) <= eps and _on_segment(a, b, c, eps):
        return True
    if abs(o2) <= eps and _on_segment(a, b, d, eps):
        return True
    if abs(o3) <= eps and _on_segment(c, d, a, eps):
        return True
    if abs(o4) <= eps and _on_segment(c, d, b, eps):
        return True
    return False


def _check_simple_loop(points: list[tuple[float, float]]) -> None:
    edge_count = len(points) - 1
    for i in range(edge_count):
        for j in range(i + 2, edge_count):
            if i == 0 and j == edge_count - 1:
                continue
            if _segments_intersect(points[i], points[i + 1], points[j], points[j + 1]):
                raise ValueError(f"outline self-intersection near sampled edges {i} and {j}")


def _width_at_longitudinal_x(points: list[tuple[float, float]], x_mm: float) -> float:
    intersections: list[float] = []
    for a, b in zip(points, points[1:]):
        x0, x1 = a[0], b[0]
        # Half-open intervals avoid counting a shared vertex twice.
        if (x0 <= x_mm < x1) or (x1 <= x_mm < x0):
            t = (x_mm - x0) / (x1 - x0)
            intersections.append(a[1] + t * (b[1] - a[1]))
    intersections.sort()
    unique: list[float] = []
    for y in intersections:
        if not unique or abs(y - unique[-1]) > 1e-5:
            unique.append(y)
    if len(unique) < 2:
        raise ValueError(
            f"outline must cross longitudinal station x={x_mm:.3f} mm at least twice"
        )
    return unique[-1] - unique[0]


def merge_outline_into_shape_document(
    outline_document: dict[str, Any],
    template_document: dict[str, Any],
) -> dict[str, Any]:
    """Return a validated Shape Document with the editor outline applied.

    The template supplies section-profile, rocker/stringer and mount defaults.
    Station positions are re-laid out proportionally and station widths are
    sampled from the outline. The existing section profiles are retained and
    clearly marked as template-derived; cached properties are invalidated.
    """
    if not isinstance(outline_document, dict):
        raise ValueError("outline document must be a JSON object")
    if outline_document.get("document_type") != "surfwing.outline":
        raise ValueError("document_type must be surfwing.outline")
    if outline_document.get("schema_version") != "0.2.0":
        raise ValueError("unsupported outline editor schema_version")
    if outline_document.get("units") != "mm" or outline_document.get("closed") is not True:
        raise ValueError("outline must be closed and expressed in millimetres")

    length_mm = float(outline_document.get("length_mm", 0))
    width_mm = float(outline_document.get("width_mm", 0))
    if not math.isfinite(length_mm) or not math.isfinite(width_mm) or length_mm <= 0 or width_mm <= 0:
        raise ValueError("outline length_mm and width_mm must be positive finite values")

    raw_anchors = outline_document.get("anchors")
    if not isinstance(raw_anchors, list) or len(raw_anchors) < 3:
        raise ValueError("outline requires at least three anchors")

    anchors: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for i, raw in enumerate(raw_anchors):
        if not isinstance(raw, dict):
            raise ValueError(f"anchor {i} must be an object")
        source_id = str(raw.get("id", "")).strip()
        if not source_id:
            raise ValueError(f"anchor {i} is missing a stable id")
        if source_id in seen_ids:
            raise ValueError(f"duplicate outline anchor id {source_id!r}")
        seen_ids.add(source_id)
        position = _finite_pair(raw.get("position"), f"anchor {source_id} position")
        incoming = _finite_pair(raw.get("incoming_handle"), f"anchor {source_id} incoming_handle")
        outgoing = _finite_pair(raw.get("outgoing_handle"), f"anchor {source_id} outgoing_handle")
        continuity = CONTINUITY.get(str(raw.get("continuity", "")))
        if continuity is None:
            raise ValueError(f"anchor {source_id} has unsupported continuity mode")
        stable_id = "outline-anchor-" + str(uuid.uuid5(uuid.NAMESPACE_URL, "surfwing-outline:" + source_id))
        # Editor XY = (transverse, longitudinal); schema XY = (longitudinal, transverse).
        anchors.append({
            "id": stable_id,
            "position": [position[1], position[0]],
            "incoming_handle": [incoming[1], incoming[0]],
            "outgoing_handle": [outgoing[1], outgoing[0]],
            "continuity": continuity,
        })

    if len(anchors) < 3:
        raise ValueError("outline requires at least three valid anchors")
    polyline = _flatten_outline(raw_anchors)
    _check_simple_loop(polyline)

    result = copy.deepcopy(template_document)
    board = result.get("board")
    if not isinstance(board, dict):
        raise ValueError("template must contain a board object")
    outline_curve_id = board.get("outline_curve_id")
    curves = result.get("curves")
    if not isinstance(curves, list):
        raise ValueError("template must contain a curves array")
    outline_curve = next((c for c in curves if c.get("id") == outline_curve_id), None)
    if outline_curve is None:
        raise ValueError("template board outline_curve_id does not resolve to a curve")

    outline_curve.update({
        "role": "outline_xy",
        "dimension": 2,
        "closed": True,
        "anchors": anchors,
        "revision": int(outline_curve.get("revision", 0)) + 1,
    })

    stations = board.get("stations")
    if not isinstance(stations, list) or len(stations) < 2:
        raise ValueError("template board must contain at least two section stations")
    old_span = max(abs(float(s.get("x_mm", 0))) for s in stations)
    if old_span <= 0:
        raise ValueError("template stations do not define a longitudinal span")
    new_station_span = length_mm * 0.375
    station_scale = new_station_span / old_span
    guide_scale = (length_mm / 2.0) / old_span

    frames = {frame.get("id"): frame for frame in result.get("frames", [])}
    for station in stations:
        new_x = float(station["x_mm"]) * station_scale
        station["x_mm"] = new_x
        station["width_mm"] = _width_at_longitudinal_x(polyline, new_x)
        frame = frames.get(station.get("frame_id"))
        if frame is None:
            raise ValueError(f"station {station.get('id')} references a missing frame")
        frame["origin_mm"][0] = new_x
        frame["origin_mm"][2] = float(station.get("bottom_z_mm", frame["origin_mm"][2]))

    # Stretch rocker/stringer guides to the full new board length; their Z design
    # values are kept because this UI edits planform only.
    for guide_id in (board.get("rocker_curve_id"), board.get("stringer_curve_id")):
        if not guide_id:
            continue
        guide = next((c for c in curves if c.get("id") == guide_id), None)
        if guide is None:
            raise ValueError(f"template references missing guide curve {guide_id}")
        for anchor in guide.get("anchors", []):
            for field in ("position", "incoming_handle", "outgoing_handle"):
                anchor[field][0] = float(anchor[field][0]) * guide_scale

    rail = board.setdefault("rail_definition", {})
    boundary_ids = list(rail.get("boundary_curve_ids", []))
    if outline_curve_id not in boundary_ids:
        boundary_ids.append(outline_curve_id)
    rail["boundary_curve_ids"] = boundary_ids

    # End-condition labels in the starter template do not necessarily describe
    # the edited outline; retain the outline as the authoritative custom boundary.
    board["nose"] = {
        "shape_family": "custom",
        "boundary_curve_id": outline_curve_id,
        "parameters": {"source": "outline_curve"},
    }
    board["tail"] = {
        "shape_family": "custom",
        "boundary_curve_id": outline_curve_id,
        "parameters": {"source": "outline_curve"},
    }

    result["name"] = str(outline_document.get("name") or result.get("name") or "Wingfoil board")
    derived = result.setdefault("derived", {})
    derived["source_revision"] = None
    derived["properties"] = []
    derived["validation"] = [{
        "code": "OUTLINE_EDITOR_IMPORT",
        "message": (
            "Planform imported from the standalone outline editor. Station widths were sampled "
            "from the new outline; rocker/stringer Z values and transverse section profiles remain "
            "template-derived and require review before 3D/CAM use."
        ),
        "severity": "warning",
        "entity_id": outline_curve_id,
    }]

    validate_shape_document(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert SurfWing outline-editor JSON into a validated Shape Document v0.1.0."
    )
    parser.add_argument("outline_json", type=Path, help="JSON exported by the browser outline editor")
    parser.add_argument("--template", type=Path,
                        default=Path("examples/domain/wingfoil-board-0.1.json"),
                        help="Shape Document template with station and section defaults")
    parser.add_argument("--output", type=Path, required=True, help="output Shape Document JSON path")
    args = parser.parse_args()

    outline = json.loads(args.outline_json.read_text(encoding="utf-8"))
    template = json.loads(args.template.read_text(encoding="utf-8"))
    document = merge_outline_into_shape_document(outline, template)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(dumps_document(document), encoding="utf-8")
    print(f"Validated Shape Document written to {args.output}")


if __name__ == "__main__":
    main()
