"""Closed triangle-mesh loft for analytic transverse board sections.

Additive path: the legacy BoardStation generator remains unchanged. Each
station is sampled on one shared normalized lateral grid.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from src.board.sections import BoardCrossSection


@dataclass(frozen=True)
class SectionLoftMesh:
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]

    def edge_use_counts(self) -> dict[tuple[int, int], int]:
        counts: dict[tuple[int, int], int] = {}
        for a, b, c in self.faces:
            for p, q in ((a, b), (b, c), (c, a)):
                edge = (p, q) if p < q else (q, p)
                counts[edge] = counts.get(edge, 0) + 1
        return counts

    @property
    def is_watertight(self) -> bool:
        return bool(self.faces) and all(n == 2 for n in self.edge_use_counts().values())

    def signed_volume_mm3(self) -> float:
        total = 0.0
        for a, b, c in self.faces:
            p, q, r = self.vertices[a], self.vertices[b], self.vertices[c]
            total += (p[0] * (q[1]*r[2] - q[2]*r[1])
                      - p[1] * (q[0]*r[2] - q[2]*r[0])
                      + p[2] * (q[0]*r[1] - q[1]*r[0]))
        return total / 6.0

    @property
    def volume_litres(self) -> float:
        return abs(self.signed_volume_mm3()) / 1_000_000.0


def generate_section_loft_mesh(
    sections: Sequence[BoardCrossSection], lateral_samples: int = 48
) -> SectionLoftMesh:
    """Loft sections into a closed hull; end rings are fan-capped to centres."""
    if len(sections) < 2:
        raise ValueError("At least two longitudinal sections are required")
    if lateral_samples < 4 or lateral_samples % 2:
        raise ValueError("lateral_samples must be even and >= 4")
    xs = [section.x_mm for section in sections]
    if any(not math.isfinite(x) for x in xs) or any(b <= a for a, b in zip(xs, xs[1:])):
        raise ValueError("Sections must have strictly increasing x_mm")
    for section in sections:
        section.validate()

    # Deck runs port -> starboard; bottom returns starboard -> port.
    ring_size = 2 * (lateral_samples + 1)
    vertices: list[tuple[float, float, float]] = []
    for section in sections:
        for i in range(lateral_samples + 1):
            u = -1.0 + 2.0 * i / lateral_samples
            _, deck_z = section.evaluate(u)
            vertices.append((section.x_mm, u * section.width_mm / 2.0, deck_z))
        for i in range(lateral_samples, -1, -1):
            u = -1.0 + 2.0 * i / lateral_samples
            bottom_z, _ = section.evaluate(u)
            vertices.append((section.x_mm, u * section.width_mm / 2.0, bottom_z))

    faces: list[tuple[int, int, int]] = []
    for station_index in range(len(sections) - 1):
        a0, b0 = station_index * ring_size, (station_index + 1) * ring_size
        for j in range(ring_size):
            j2 = (j + 1) % ring_size
            faces.append((a0 + j, b0 + j, b0 + j2))
            faces.append((a0 + j, b0 + j2, a0 + j2))

    for end_index, section in ((0, sections[0]), (len(sections)-1, sections[-1])):
        bottom, deck = section.evaluate(0.0)
        cap_id = len(vertices)
        vertices.append((section.x_mm, 0.0, (bottom + deck) / 2.0))
        base = end_index * ring_size
        for j in range(ring_size):
            j2 = (j + 1) % ring_size
            if end_index == 0:
                # Nose cap perimeter edge must oppose the first loft ring.
                faces.append((cap_id, base + j, base + j2))
            else:
                # Tail cap perimeter edge must oppose the last loft ring.
                faces.append((cap_id, base + j2, base + j))

    mesh = SectionLoftMesh(tuple(vertices), tuple(faces))
    if not mesh.is_watertight:
        raise RuntimeError("Section loft is not watertight")
    if not math.isfinite(mesh.volume_litres) or mesh.volume_litres <= 1e-9:
        raise RuntimeError("Section loft has zero or invalid volume")
    return mesh
