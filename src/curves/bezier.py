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
