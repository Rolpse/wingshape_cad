"""Closed triangle-mesh loft for analytic transverse board sections.

Additive path: legacy BoardStation mesh generation remains unchanged. Deck and
bottom samples share a normalized lateral grid; longitudinal interpolation is
performed on evaluated surface samples, not profile-control-point indices.
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
    sections: Sequence[BoardCrossSection],
    lateral_samples: int = 48,
    longitudinal_samples_per_interval: int = 1,
) -> SectionLoftMesh:
    """Loft sections to a closed hull.

    Each interval is linearly interpolated in X, width, and evaluated deck/
    bottom sample values. With the default of one longitudinal sample, the
    station-only ring layout is retained. The first and last rings are fan-capped.
    """
    if len(sections) < 2:
        raise ValueError("At least two longitudinal sections are required")
    if lateral_samples < 4 or lateral_samples % 2:
        raise ValueError("lateral_samples must be even and >= 4")
    if longitudinal_samples_per_interval < 1:
        raise ValueError("longitudinal_samples_per_interval must be >= 1")
    xs = [section.x_mm for section in sections]
    if any(not math.isfinite(x) for x in xs) or any(b <= a for a, b in zip(xs, xs[1:])):
        raise ValueError("Sections must have strictly increasing x_mm")
    for section in sections:
        section.validate()

    u_values = [-1.0 + 2.0*i/lateral_samples for i in range(lateral_samples+1)]
    source_samples = []
    for section in sections:
        deck = [section.evaluate(u)[1] for u in u_values]
        bottom = [section.evaluate(u)[0] for u in u_values]
        source_samples.append((section.x_mm, section.width_mm, deck, bottom))

    # Interpolate surface samples on the same u-grid; no control-point pairing.
    ring_samples = []
    for interval in range(len(source_samples)-1):
        left, right = source_samples[interval], source_samples[interval+1]
        for step in range(longitudinal_samples_per_interval):
            t = step/longitudinal_samples_per_interval
            x = left[0] + (right[0]-left[0])*t
            width = left[1] + (right[1]-left[1])*t
            deck = [a+(b-a)*t for a,b in zip(left[2],right[2])]
            bottom = [a+(b-a)*t for a,b in zip(left[3],right[3])]
            if width <= 0 or any(d-b <= 0.1 for d,b in zip(deck,bottom)):
                raise ValueError(f"Interpolated section at x={x:g} mm has invalid width/thickness")
            ring_samples.append((x,width,deck,bottom))
    ring_samples.append(source_samples[-1])
    if any(b[0] <= a[0] for a,b in zip(ring_samples,ring_samples[1:])):
        raise ValueError("Interpolated loft rings must be strictly increasing in x")

    ring_size = 2*(lateral_samples+1)
    vertices: list[tuple[float,float,float]] = []
    for x,width,deck,bottom in ring_samples:
        for i,u in enumerate(u_values):
            vertices.append((x,u*width/2.0,deck[i]))
        for i in range(lateral_samples,-1,-1):
            u=u_values[i]
            vertices.append((x,u*width/2.0,bottom[i]))

    faces: list[tuple[int,int,int]]=[]
    for station_index in range(len(ring_samples)-1):
        a0,b0=station_index*ring_size,(station_index+1)*ring_size
        for j in range(ring_size):
            j2=(j+1)%ring_size
            faces.append((a0+j,b0+j,b0+j2))
            faces.append((a0+j,b0+j2,a0+j2))

    for end_index,section in ((0,sections[0]),(len(ring_samples)-1,sections[-1])):
        bottom,deck=section.evaluate(0.0)
        cap_id=len(vertices)
        vertices.append((section.x_mm,0.0,(bottom+deck)/2.0))
        base=end_index*ring_size
        for j in range(ring_size):
            j2=(j+1)%ring_size
            if end_index==0:
                faces.append((cap_id,base+j,base+j2))
            else:
                faces.append((cap_id,base+j2,base+j))

    mesh=SectionLoftMesh(tuple(vertices),tuple(faces))
    if not mesh.is_watertight:
        raise RuntimeError("Section loft is not watertight")
    if not math.isfinite(mesh.volume_litres) or mesh.volume_litres<=1e-9:
        raise RuntimeError("Section loft has zero or invalid volume")
    return mesh
