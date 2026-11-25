"""Editable cubic Bezier curves for board outlines and section profiles.

Coordinates are millimetres. Anchor handles are absolute 2D/3D points rather
than direction vectors, making them directly editable in a graphical editor.
Insertion uses de Casteljau subdivision and preserves the represented curve
exactly (up to floating-point rounding).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import math
from typing import Iterable
from uuid import uuid4

Point = tuple[float, ...]


class Continuity(str, Enum):
    CORNER = "corner"
    SMOOTH = "smooth"
    SYMMETRIC = "symmetric"


def _point(values: Iterable[float], dimension: int | None = None) -> Point:
    result = tuple(float(v) for v in values)
    if dimension is not None and len(result) != dimension:
        raise ValueError(f"Expected {dimension}D point, got {len(result)}D")
    if len(result) not in (2, 3) or not all(math.isfinite(v) for v in result):
        raise ValueError("Points must be finite 2D or 3D coordinates")
    return result


def _add(a: Point, b: Point) -> Point:
    return tuple(x + y for x, y in zip(a, b))


def _sub(a: Point, b: Point) -> Point:
    return tuple(x - y for x, y in zip(a, b))


def _scale(a: Point, factor: float) -> Point:
    return tuple(x * factor for x in a)


def _lerp(a: Point, b: Point, t: float) -> Point:
    return _add(_scale(a, 1.0 - t), _scale(b, t))


def _length(a: Point) -> float:
    return math.sqrt(sum(x*x for x in a))


@dataclass(frozen=True)
class Anchor:
    id: str
    position: Point
    incoming: Point
    outgoing: Point
    continuity: Continuity = Continuity.CORNER

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("Anchor id must be a non-empty string")
        p = _point(self.position)
        object.__setattr__(self, "position", p)
        object.__setattr__(self, "incoming", _point(self.incoming, len(p)))
        object.__setattr__(self, "outgoing", _point(self.outgoing, len(p)))
        object.__setattr__(self, "continuity", Continuity(self.continuity))
        if self.continuity != Continuity.CORNER:
            _validate_handle_constraint(self.position, self.incoming,
                                        self.outgoing, self.continuity)


def _validate_handle_constraint(position: Point, incoming: Point,
                                outgoing: Point, mode: Continuity,
                                tolerance: float = 1e-7) -> None:
    a, b = _sub(incoming, position), _sub(outgoing, position)
    la, lb = _length(a), _length(b)
    if la <= tolerance or lb <= tolerance:
        if mode == Continuity.SYMMETRIC and abs(la-lb) > tolerance:
            raise ValueError("Symmetric handles must have equal lengths")
        return
    cross = tuple(a[i] / la - (-b[i] / lb) for i in range(len(a)))
    # Incoming and outgoing vectors point away from the anchor, so they must oppose.
    if _length(cross) > tolerance:
        raise ValueError(f"{mode.value} handles must be collinear and opposite")
    if mode == Continuity.SYMMETRIC and abs(la-lb) > tolerance:
        raise ValueError("Symmetric handles must have equal lengths")


def evaluate_cubic(p0: Point, p1: Point, p2: Point, p3: Point, t: float) -> Point:
    """Evaluate a cubic Bezier segment for t in [0, 1]."""
    if not math.isfinite(t) or not 0.0 <= t <= 1.0:
        raise ValueError("t must be finite and in [0, 1]")
    a = _lerp(p0, p1, t)
    b = _lerp(p1, p2, t)
    c = _lerp(p2, p3, t)
    d = _lerp(a, b, t)
    e = _lerp(b, c, t)
    return _lerp(d, e, t)


@dataclass(frozen=True)
class BezierCurve:
    anchors: tuple[Anchor, ...]
    dimension: int = 2

    def __post_init__(self) -> None:
        if self.dimension not in (2, 3):
            raise ValueError("Curve dimension must be 2 or 3")
        if len(self.anchors) < 2:
            raise ValueError("An open curve requires at least two anchors")
        ids = [a.id for a in self.anchors]
        if len(ids) != len(set(ids)):
            raise ValueError("Anchor IDs must be unique")
        for anchor in self.anchors:
            if len(anchor.position) != self.dimension:
                raise ValueError("All anchors must match curve dimension")

    @property
    def segment_count(self) -> int:
        return len(self.anchors) - 1

    def evaluate(self, segment_index: int, t: float) -> Point:
        if not 0 <= segment_index < self.segment_count:
            raise IndexError("Segment index out of range")
        a, b = self.anchors[segment_index:segment_index+2]
        return evaluate_cubic(a.position, a.outgoing, b.incoming, b.position, t)

    def move_anchor(self, anchor_id: str, position: Iterable[float]) -> "BezierCurve":
        target = _point(position, self.dimension)
        found = False
        updated = []
        for anchor in self.anchors:
            if anchor.id == anchor_id:
                delta = _sub(target, anchor.position)
                updated.append(replace(anchor, position=target,
                    incoming=_add(anchor.incoming, delta),
                    outgoing=_add(anchor.outgoing, delta)))
                found = True
            else:
                updated.append(anchor)
        if not found:
            raise KeyError(anchor_id)
        return replace(self, anchors=tuple(updated))

    def set_handle(self, anchor_id: str, side: str,
                   handle: Iterable[float]) -> "BezierCurve":
        if side not in ("incoming", "outgoing"):
            raise ValueError("side must be 'incoming' or 'outgoing'")
        value = _point(handle, self.dimension)
        updated = []
        found = False
        for anchor in self.anchors:
            if anchor.id != anchor_id:
                updated.append(anchor)
                continue
            found = True
            if anchor.continuity == Continuity.CORNER:
                updated.append(replace(anchor, **{side: value}))
                continue
            other_side = "outgoing" if side == "incoming" else "incoming"
            direction = _sub(value, anchor.position)
            other_length = _length(_sub(getattr(anchor, other_side), anchor.position))
            length = _length(direction)
            if length == 0:
                other = anchor.position
            else:
                factor = other_length if anchor.continuity == Continuity.SMOOTH else length
                if anchor.continuity == Continuity.SYMMETRIC:
                    factor = length
                other = _sub(anchor.position, _scale(direction, factor / length))
            updated.append(replace(anchor, **{side: value, other_side: other}))
        if not found:
            raise KeyError(anchor_id)
        return replace(self, anchors=tuple(updated))

    def set_continuity(self, anchor_id: str, mode: Continuity) -> "BezierCurve":
        mode = Continuity(mode)
        updated = []
        found = False
        for anchor in self.anchors:
            if anchor.id != anchor_id:
                updated.append(anchor)
                continue
            found = True
            if mode == Continuity.CORNER:
                updated.append(replace(anchor, continuity=mode))
                continue
            incoming_vec = _sub(anchor.incoming, anchor.position)
            outgoing_vec = _sub(anchor.outgoing, anchor.position)
            incoming_len, outgoing_len = _length(incoming_vec), _length(outgoing_vec)
            direction = outgoing_vec if outgoing_len > 1e-12 else _scale(incoming_vec, -1)
            norm = _length(direction)
            if norm <= 1e-12:
                updated.append(replace(anchor, continuity=mode))
                continue
            unit = _scale(direction, 1.0 / norm)
            in_len = incoming_len
            out_len = outgoing_len
            if mode == Continuity.SYMMETRIC:
                in_len = out_len = max(in_len, out_len)
            updated.append(replace(anchor, continuity=Continuity.CORNER,
                incoming=_sub(anchor.position, _scale(unit, in_len)),
                outgoing=_add(anchor.position, _scale(unit, out_len))))
            updated[-1] = replace(updated[-1], continuity=mode)
        if not found:
            raise KeyError(anchor_id)
        return replace(self, anchors=tuple(updated))

    def insert_on_segment(self, segment_index: int, t: float,
                          anchor_id: str | None = None) -> "BezierCurve":
        """Split a segment exactly at t using de Casteljau subdivision."""
        if not 0.0 < t < 1.0:
            raise ValueError("Insertion t must be strictly between 0 and 1")
        if not 0 <= segment_index < self.segment_count:
            raise IndexError("Segment index out of range")
        left, right = self.anchors[segment_index:segment_index+2]
        p0, p1, p2, p3 = left.position, left.outgoing, right.incoming, right.position
        q0, q1, q2 = _lerp(p0, p1, t), _lerp(p1, p2, t), _lerp(p2, p3, t)
        r0, r1 = _lerp(q0, q1, t), _lerp(q1, q2, t)
        split = _lerp(r0, r1, t)
        new_id = anchor_id or str(uuid4())
        if any(a.id == new_id for a in self.anchors):
            raise ValueError(f"Anchor id already exists: {new_id}")
        # Exact subdivision shortens one handle at each touched endpoint.
        # A symmetric handle pair cannot remain symmetric after a non-midpoint
        # split; preserve the exact geometry and relax only that local mode to
        # Smooth (tangent continuity is still preserved).
        left_mode = Continuity.SMOOTH if left.continuity == Continuity.SYMMETRIC else left.continuity
        right_mode = Continuity.SMOOTH if right.continuity == Continuity.SYMMETRIC else right.continuity
        new_left = replace(left, outgoing=q0, continuity=left_mode)
        new_right = replace(right, incoming=q2, continuity=right_mode)
        inserted = Anchor(new_id, split, r0, r1, Continuity.SMOOTH)
        anchors = list(self.anchors)
        anchors[segment_index:segment_index+2] = [new_left, inserted, new_right]
        return replace(self, anchors=tuple(anchors))

    def delete_anchor_bounded(
        self, anchor_id: str, max_deviation: float, samples_per_segment: int = 80
    ) -> tuple["BezierCurve", "DeletionReport"]:
        """Remove an interior anchor only when a fitted cubic stays within tolerance.

        The two original segments are sampled uniformly in their own parameter
        domains. A replacement cubic is fitted with endpoint tangent directions
        constrained by the surviving anchors' adjacent handles. The reported
        deviation is the sampled point-to-point error, not a formal Hausdorff
        bound; increase samples_per_segment for tighter validation.
        """
        if not math.isfinite(max_deviation) or max_deviation < 0:
            raise ValueError("max_deviation must be finite and non-negative")
        if samples_per_segment < 8:
            raise ValueError("samples_per_segment must be at least 8")
        index = next((i for i, a in enumerate(self.anchors) if a.id == anchor_id), None)
        if index is None:
            raise KeyError(anchor_id)
        if index == 0 or index == len(self.anchors) - 1:
            raise ValueError("Open-curve endpoints cannot be deleted")

        before, removed, after = self.anchors[index-1:index+2]
        source = []
        for j in range(samples_per_segment + 1):
            u = j / samples_per_segment
            if u <= 0.5:
                source.append(self.evaluate(index-1, u * 2.0))
            else:
                source.append(self.evaluate(index, (u - 0.5) * 2.0))

        chord = _sub(after.position, before.position)
        chord_length = _length(chord)
        if chord_length <= 1e-12:
            raise ValueError("Cannot fit deletion when surviving anchors coincide")

        def unit_or(vector: Point, fallback: Point) -> Point:
            length = _length(vector)
            return _scale(vector, 1.0 / length) if length > 1e-12 else fallback

        chord_unit = _scale(chord, 1.0 / chord_length)
        tangent_a = unit_or(_sub(before.outgoing, before.position), chord_unit)
        tangent_b = unit_or(_sub(after.position, after.incoming), chord_unit)
        # Keep the fitted handles forward-facing; optimize only their lengths.
        p0, p3 = before.position, after.position

        def candidate(alpha: float, beta: float) -> tuple[Point, Point, Point, Point]:
            return (p0, _add(p0, _scale(tangent_a, alpha)),
                    _sub(p3, _scale(tangent_b, beta)), p3)

        def point_segment_distance(point: Point, start: Point, end: Point) -> float:
            edge = _sub(end, start)
            denom = sum(v * v for v in edge)
            if denom <= 1e-24:
                return _length(_sub(point, start))
            offset = _sub(point, start)
            t = max(0.0, min(1.0, sum(a*b for a, b in zip(offset, edge)) / denom))
            return _length(_sub(point, _add(start, _scale(edge, t))))

        def polyline_distance(point: Point, polyline: list[Point]) -> float:
            return min(point_segment_distance(point, a, b)
                       for a, b in zip(polyline, polyline[1:]))

        def errors(alpha: float, beta: float) -> tuple[float, float]:
            controls = candidate(alpha, beta)
            fitted = [evaluate_cubic(*controls, i / samples_per_segment)
                      for i in range(samples_per_segment + 1)]
            # Approximate a symmetric discrete Hausdorff distance between the
            # sampled source and fitted polylines. This is geometric rather
            # than parameter-correspondence error, so exact de Casteljau splits
            # are not penalized merely because their local parameters differ.
            distances = ([polyline_distance(p, fitted) for p in source]
                         + [polyline_distance(p, source) for p in fitted])
            return sum(d*d for d in distances), max(distances)

        # Exact inverse of de Casteljau subdivision. When the removed anchor
        # was created by insert_on_segment(), its two handles encode the split
        # parameter. Reconstructing the parent cubic avoids a false failure
        # caused by comparing two different segment parameterizations.
        incoming_length = _length(_sub(removed.position, removed.incoming))
        outgoing_length = _length(_sub(removed.outgoing, removed.position))
        handle_sum = incoming_length + outgoing_length
        if handle_sum > 1e-12:
            split_t = incoming_length / handle_sum
            if 1e-9 < split_t < 1.0 - 1e-9:
                exact_p1 = _add(
                    p0, _scale(_sub(before.outgoing, p0), 1.0 / split_t)
                )
                exact_p2 = _add(
                    p3, _scale(_sub(after.incoming, p3), 1.0 / (1.0 - split_t))
                )
                exact_controls = (p0, exact_p1, exact_p2, p3)
                exact_distances = []
                for i, target in enumerate(source):
                    q = i / samples_per_segment
                    original_t = (
                        2.0 * q * split_t
                        if q <= 0.5
                        else split_t + 2.0 * (q - 0.5) * (1.0 - split_t)
                    )
                    actual = evaluate_cubic(*exact_controls, original_t)
                    exact_distances.append(_length(_sub(actual, target)))
                exact_max = max(exact_distances)
                exact_rms = math.sqrt(
                    sum(d * d for d in exact_distances) / len(exact_distances)
                )
                if exact_max <= max_deviation:
                    report = DeletionReport(
                        anchor_id, exact_rms, exact_max, max_deviation,
                        samples_per_segment, True
                    )
                    new_before = replace(
                        before, outgoing=exact_p1, continuity=Continuity.CORNER
                    )
                    new_after = replace(
                        after, incoming=exact_p2, continuity=Continuity.CORNER
                    )
                    anchors = list(self.anchors)
                    anchors[index - 1:index + 2] = [new_before, new_after]
                    return replace(self, anchors=tuple(anchors)), report

        # Coarse global search followed by deterministic two-parameter pattern
        # refinement. No numerical/scientific dependencies are required.
        upper = max(chord_length * 3.0, _length(_sub(removed.position, before.position))
                    + _length(_sub(after.position, removed.position)), 1.0)
        grid = [upper * i / 20.0 for i in range(21)]
        best = (float("inf"), chord_length / 3.0, chord_length / 3.0)
        for alpha in grid:
            for beta in grid:
                score, _ = errors(alpha, beta)
                if score < best[0]:
                    best = (score, alpha, beta)
        alpha, beta = best[1], best[2]
        step = upper / 20.0
        for _ in range(40):
            improved = False
            for da, db in ((-step, 0.0), (step, 0.0), (0.0, -step), (0.0, step),
                           (-step, -step), (-step, step), (step, -step), (step, step)):
                a, b = max(0.0, min(upper, alpha + da)), max(0.0, min(upper, beta + db))
                score, _ = errors(a, b)
                if score + 1e-18 < best[0]:
                    best, alpha, beta = (score, a, b), a, b
                    improved = True
            if not improved:
                step *= 0.5
            if step < max(1e-9, upper * 1e-8):
                break

        _, maximum = errors(alpha, beta)
        rms = math.sqrt(best[0] / len(source))
        report = DeletionReport(anchor_id, rms, maximum, max_deviation,
                                samples_per_segment, maximum <= max_deviation)
        if not report.accepted:
            raise CurveFitToleranceError(report)

        p0, p1, p2, p3 = candidate(alpha, beta)
        new_before = replace(before, outgoing=p1, continuity=Continuity.CORNER)
        new_after = replace(after, incoming=p2, continuity=Continuity.CORNER)
        anchors = list(self.anchors)
        anchors[index-1:index+2] = [new_before, new_after]
        return replace(self, anchors=tuple(anchors)), report

    def delete_anchor(self, anchor_id: str) -> "BezierCurve":
        """Delete an anchor and join its neighbors with a straight cubic.

        This first-pass operation is intentionally explicit: the replacement
        may change shape. A bounded curve-fit deletion operation is a later task.
        Endpoints are protected; callers must choose another operation to trim.
        """
        index = next((i for i, a in enumerate(self.anchors) if a.id == anchor_id), None)
        if index is None:
            raise KeyError(anchor_id)
        if index == 0 or index == len(self.anchors)-1:
            raise ValueError("Open-curve endpoints cannot be deleted")
        before, removed, after = self.anchors[index-1:index+2]
        # Join at 1/3 and 2/3 of the chord: deterministic, visibly documented fallback.
        chord = _sub(after.position, before.position)
        new_before = replace(before, outgoing=_add(before.position, _scale(chord, 1/3)),
                             continuity=Continuity.CORNER)
        new_after = replace(after, incoming=_sub(after.position, _scale(chord, 1/3)),
                            continuity=Continuity.CORNER)
        anchors = list(self.anchors)
        anchors[index-1:index+2] = [new_before, new_after]
        return replace(self, anchors=tuple(anchors))

    def to_dict(self) -> dict:
        return {"dimension": self.dimension, "anchors": [
            {"id": a.id, "position": list(a.position), "incoming": list(a.incoming),
             "outgoing": list(a.outgoing), "continuity": a.continuity.value}
            for a in self.anchors
        ]}

    @classmethod
    def from_dict(cls, data: dict) -> "BezierCurve":
        if set(data) != {"dimension", "anchors"} or not isinstance(data["anchors"], list):
            raise ValueError("Invalid BezierCurve document")
        anchors = []
        for item in data["anchors"]:
            if set(item) != {"id", "position", "incoming", "outgoing", "continuity"}:
                raise ValueError("Invalid anchor document")
            anchors.append(Anchor(item["id"], tuple(item["position"]),
                tuple(item["incoming"]), tuple(item["outgoing"]),
                Continuity(item["continuity"])))
        return cls(tuple(anchors), int(data["dimension"]))


@dataclass(frozen=True)
class DeletionReport:
    """Measured result of a bounded anchor deletion fit."""

    anchor_id: str
    rms_deviation: float
    max_sampled_deviation: float
    tolerance_mm: float
    samples_per_segment: int
    accepted: bool


class CurveFitToleranceError(ValueError):
    """Raised when deleting an anchor would exceed the requested tolerance."""

    def __init__(self, report: DeletionReport) -> None:
        self.report = report
        super().__init__(
            f"Deleting anchor {report.anchor_id!r} would produce a maximum "
            f"sampled deviation of {report.max_sampled_deviation:.6g} mm "
            f"(limit {report.tolerance_mm:.6g} mm)"
        )
