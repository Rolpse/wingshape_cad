"""Deterministic parametric surf/wing-foil board mesh generator.

The first implementation is deliberately dependency-free. It generates a closed,
triangulated board hull from longitudinal stations and exports OBJ or binary STL.
It is a geometry prototype, not yet a boundary-representation CAD kernel.
All dimensions are millimetres; coordinates are X=length, Y=width, Z=up.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import struct
from pathlib import Path


@dataclass(frozen=True)
class BoardStation:
    """Cross-section control station, measured from board centre in X."""

    x_mm: float
    width_mm: float
    thickness_mm: float
    bottom_z_mm: float = 0.0
    deck_crown_mm: float = 3.0
    bottom_concave_mm: float = 0.0

    def __post_init__(self) -> None:
        values = (self.x_mm, self.width_mm, self.thickness_mm,
                  self.bottom_z_mm, self.deck_crown_mm, self.bottom_concave_mm)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Station values must be finite")
        if self.width_mm < 0 or self.thickness_mm <= 0:
            raise ValueError("Width must be non-negative and thickness positive")
        if self.deck_crown_mm < 0 or self.bottom_concave_mm < 0:
            raise ValueError("Crown and concave must be non-negative")


@dataclass(frozen=True)
class BoardDefinition:
    name: str
    stations: tuple[BoardStation, ...]
    perimeter_samples: int = 96
    longitudinal_samples_per_interval: int = 16

    def __post_init__(self) -> None:
        if len(self.stations) < 3:
            raise ValueError("At least three longitudinal stations are required")
        xs = [s.x_mm for s in self.stations]
        if any(b <= a for a, b in zip(xs, xs[1:])):
            raise ValueError("Stations must be strictly ordered from nose to tail")
        if self.stations[0].width_mm != 0 or self.stations[-1].width_mm != 0:
            raise ValueError("First and last stations must be zero-width nose/tail tips")
        if self.perimeter_samples < 12 or self.perimeter_samples % 4:
            raise ValueError("perimeter_samples must be >=12 and divisible by 4")
        if self.longitudinal_samples_per_interval < 1:
            raise ValueError("longitudinal_samples_per_interval must be >=1")

    @property
    def length_mm(self) -> float:
        return self.stations[-1].x_mm - self.stations[0].x_mm

    @property
    def max_width_mm(self) -> float:
        return max(s.width_mm for s in self.stations)


@dataclass(frozen=True)
class BoardMesh:
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]

    def signed_volume_mm3(self) -> float:
        volume6 = 0.0
        for a, b, c in self.faces:
            p, q, r = self.vertices[a], self.vertices[b], self.vertices[c]
            volume6 += (
                p[0] * (q[1] * r[2] - q[2] * r[1])
                - p[1] * (q[0] * r[2] - q[2] * r[0])
                + p[2] * (q[0] * r[1] - q[1] * r[0])
            )
        return volume6 / 6.0

    @property
    def volume_litres(self) -> float:
        return abs(self.signed_volume_mm3()) / 1_000_000.0

    def edge_use_counts(self) -> dict[tuple[int, int], int]:
        counts: dict[tuple[int, int], int] = {}
        for face in self.faces:
            for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
                edge = (a, b) if a < b else (b, a)
                counts[edge] = counts.get(edge, 0) + 1
        return counts

    @property
    def is_watertight(self) -> bool:
        return bool(self.faces) and all(count == 2 for count in self.edge_use_counts().values())

    def write_obj(self, path: str | Path) -> None:
        path = Path(path)
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write("# SurfWing CAD parametric board mesh\n")
            for x, y, z in self.vertices:
                stream.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
            for a, b, c in self.faces:
                stream.write(f"f {a + 1} {b + 1} {c + 1}\n")

    def write_stl(self, path: str | Path, name: str = "SurfWing CAD board") -> None:
        path = Path(path)
        header = name.encode("ascii", errors="replace")[:80].ljust(80, b" ")
        with path.open("wb") as stream:
            stream.write(header)
            stream.write(struct.pack("<I", len(self.faces)))
            for a, b, c in self.faces:
                p, q, r = self.vertices[a], self.vertices[b], self.vertices[c]
                ux, uy, uz = q[0]-p[0], q[1]-p[1], q[2]-p[2]
                vx, vy, vz = r[0]-p[0], r[1]-p[1], r[2]-p[2]
                nx, ny, nz = (uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx)
                norm = math.sqrt(nx*nx + ny*ny + nz*nz)
                if norm:
                    nx, ny, nz = nx/norm, ny/norm, nz/norm
                stream.write(struct.pack("<12fH", nx, ny, nz,
                    *p, *q, *r, 0))


def _catmull_rom(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    return 0.5 * ((2*p1) + (-p0+p2)*t + (2*p0-5*p1+4*p2-p3)*t*t
                  + (-p0+3*p1-3*p2+p3)*t*t*t)


def _sample_stations(definition: BoardDefinition) -> list[BoardStation]:
    source = definition.stations
    sampled: list[BoardStation] = []
    fields = ("width_mm", "thickness_mm", "bottom_z_mm", "deck_crown_mm", "bottom_concave_mm")
    for i in range(len(source) - 1):
        left, right = source[i], source[i + 1]
        for step in range(definition.longitudinal_samples_per_interval):
            t = step / definition.longitudinal_samples_per_interval
            values: dict[str, float] = {}
            for field in fields:
                p0 = getattr(source[max(0, i - 1)], field)
                p1 = getattr(left, field)
                p2 = getattr(right, field)
                p3 = getattr(source[min(len(source) - 1, i + 2)], field)
                values[field] = _catmull_rom(p0, p1, p2, p3, t)
            values["width_mm"] = min(max(values["width_mm"], min(left.width_mm, right.width_mm)),
                                     max(left.width_mm, right.width_mm))
            values["thickness_mm"] = max(0.1, values["thickness_mm"])
            values["deck_crown_mm"] = max(0.0, values["deck_crown_mm"])
            values["bottom_concave_mm"] = max(0.0, values["bottom_concave_mm"])
            sampled.append(BoardStation(x_mm=left.x_mm + (right.x_mm-left.x_mm)*t, **values))
    sampled.append(source[-1])
    return [s for s in sampled if s.width_mm > 1e-6]


def generate_board_mesh(definition: BoardDefinition) -> BoardMesh:
    """Loft closed rounded-rail sections through the supplied stations."""
    stations = _sample_stations(definition)
    n = definition.perimeter_samples
    vertices: list[tuple[float, float, float]] = []
    for station in stations:
        half_width = station.width_mm / 2.0
        bottom_center = station.bottom_z_mm
        deck_center = bottom_center + station.thickness_mm
        rail_z = (bottom_center + deck_center) / 2.0
        for j in range(n):
            theta = 2.0 * math.pi * j / n
            sin_t, cos_t = math.sin(theta), math.cos(theta)
            lateral = abs(sin_t)
            y = half_width * sin_t
            if cos_t >= 0:
                z = (deck_center - (deck_center - rail_z) * lateral**1.35
                     + station.deck_crown_mm * (1.0-lateral)**2)
            else:
                z = (bottom_center + (rail_z-bottom_center) * lateral**1.35
                     - station.bottom_concave_mm * (1.0-lateral)**2)
            vertices.append((station.x_mm, y, z))

    faces: list[tuple[int, int, int]] = []
    for i in range(len(stations) - 1):
        ring_a, ring_b = i*n, (i+1)*n
        for j in range(n):
            j2 = (j + 1) % n
            faces.append((ring_a+j, ring_b+j, ring_b+j2))
            faces.append((ring_a+j, ring_b+j2, ring_a+j2))

    nose = definition.stations[0]
    tail = definition.stations[-1]
    nose_id = len(vertices)
    vertices.append((nose.x_mm, 0.0, nose.bottom_z_mm + nose.thickness_mm/2.0))
    tail_id = len(vertices)
    vertices.append((tail.x_mm, 0.0, tail.bottom_z_mm + tail.thickness_mm/2.0))
    for j in range(n):
        j2 = (j + 1) % n
        faces.append((nose_id, j2, j))
        last_ring = (len(stations)-1)*n
        faces.append((tail_id, last_ring+j, last_ring+j2))

    mesh = BoardMesh(tuple(vertices), tuple(faces))
    if not mesh.is_watertight:
        raise RuntimeError("Generated board mesh is not watertight")
    if mesh.volume_litres <= 0:
        raise RuntimeError("Generated board mesh has zero volume")
    return mesh


def load_board_definition(path: str | Path) -> BoardDefinition:
    """Load a board definition from the documented JSON station format."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Board definition root must be a JSON object")
    allowed = {"name", "perimeter_samples", "longitudinal_samples_per_interval", "stations"}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"Unknown board definition fields: {', '.join(sorted(unknown))}")
    raw_stations = data.get("stations")
    if not isinstance(raw_stations, list):
        raise ValueError("stations must be a JSON array")
    stations = []
    station_fields = {"x_mm", "width_mm", "thickness_mm", "bottom_z_mm",
                      "deck_crown_mm", "bottom_concave_mm"}
    for index, raw in enumerate(raw_stations):
        if not isinstance(raw, dict):
            raise ValueError(f"Station {index} must be a JSON object")
        unknown_station_fields = set(raw) - station_fields
        if unknown_station_fields:
            raise ValueError(f"Unknown fields in station {index}: "
                             f"{', '.join(sorted(unknown_station_fields))}")
        if "x_mm" not in raw or "width_mm" not in raw or "thickness_mm" not in raw:
            raise ValueError(f"Station {index} requires x_mm, width_mm and thickness_mm")
        stations.append(BoardStation(**raw))
    return BoardDefinition(
        name=str(data.get("name", "Untitled board")),
        stations=tuple(stations),
        perimeter_samples=int(data.get("perimeter_samples", 48)),
        longitudinal_samples_per_interval=int(data.get("longitudinal_samples_per_interval", 8)),
    )


def default_board_definition() -> BoardDefinition:
    """A neutral 1600 x 520 mm starter shape, not a user-specific final design."""
    return BoardDefinition(
        name="SurfWing 1600x520 starter",
        stations=(
            BoardStation(-800, 0, 78, 0, 2, 0),
            BoardStation(-650, 180, 82, 1, 3, 0),
            BoardStation(-400, 365, 88, 4, 4, 1),
            BoardStation(0, 520, 92, 8, 5, 2),
            BoardStation(400, 455, 88, 5, 4, 1),
            BoardStation(650, 235, 82, 2, 3, 0),
            BoardStation(800, 0, 78, 0, 2, 0),
        ),
    )
