"""Independent transverse deck/bottom section profiles.

This additive module deliberately leaves the legacy BoardStation mesh generator
unchanged. All persisted and evaluated dimensions are millimetres.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class TransverseProfile:
    """Analytic transverse profile, evaluated in normalized lateral coordinate u.

    Supported kinds: flat, v, single_concave, double_concave, dome,
    standing_area. Depth/crown values are non-negative millimetres.
    """

    kind: str = "flat"
    depth_mm: float = 0.0
    half_width_u: float = 0.6
    center_u: float = 0.45
    left_depth_mm: float | None = None
    right_depth_mm: float | None = None
    standing_half_width_u: float = 0.35
    blend_width_u: float = 0.15

    def __post_init__(self) -> None:
        if self.kind not in {"flat", "v", "single_concave",
                             "double_concave", "dome", "standing_area"}:
            raise ValueError(f"Unsupported transverse profile kind: {self.kind}")
        values = (self.depth_mm, self.half_width_u, self.center_u,
                  self.standing_half_width_u, self.blend_width_u)
        optional = tuple(v for v in (self.left_depth_mm, self.right_depth_mm) if v is not None)
        if not all(math.isfinite(v) for v in (*values, *optional)):
            raise ValueError("Profile parameters must be finite")
        if self.depth_mm < 0 or any(v < 0 for v in optional):
            raise ValueError("Profile depths must be non-negative")
        if not 0 < self.half_width_u <= 1:
            raise ValueError("half_width_u must be in (0, 1]")
        if not 0 < self.center_u < 1:
            raise ValueError("center_u must be in (0, 1)")
        if not 0 < self.standing_half_width_u < 1:
            raise ValueError("standing_half_width_u must be in (0, 1)")
        if not 0 < self.blend_width_u <= 1:
            raise ValueError("blend_width_u must be in (0, 1]")

    @staticmethod
    def _smoothstep(t: float) -> float:
        t = min(1.0, max(0.0, t))
        return t * t * (3.0 - 2.0 * t)

    def evaluate(self, u: float) -> float:
        """Return vertical offset in mm relative to the profile baseline."""
        if not math.isfinite(u) or not -1.0 <= u <= 1.0:
            raise ValueError("u must be finite and within [-1, 1]")
        a = abs(u)
        if self.kind == "flat":
            return 0.0
        if self.kind == "v":
            depth = self.left_depth_mm if u < 0 and self.left_depth_mm is not None else self.depth_mm
            depth = self.right_depth_mm if u >= 0 and self.right_depth_mm is not None else depth
            return depth * a
        if self.kind == "single_concave":
            t = min(1.0, a / self.half_width_u)
            return -self.depth_mm * (1.0 - t * t) ** 2
        if self.kind == "double_concave":
            depth = self.left_depth_mm if u < 0 and self.left_depth_mm is not None else self.depth_mm
            depth = self.right_depth_mm if u >= 0 and self.right_depth_mm is not None else depth
            local = abs(a - self.center_u)
            t = min(1.0, local / self.half_width_u)
            return -depth * (1.0 - t * t) ** 2
        if self.kind == "dome":
            return self.depth_mm * (1.0 - u * u)
        # Flat central standing zone, smoothly blending to the surrounding deck.
        edge = self.standing_half_width_u
        t = max(0.0, (a - edge) / self.blend_width_u)
        return self.depth_mm * self._smoothstep(t)


@dataclass(frozen=True)
class BoardCrossSection:
    """A transverse board section with independent deck and bottom profiles."""

    section_id: str
    x_mm: float
    width_mm: float
    thickness_mm: float
    bottom_z_mm: float = 0.0
    symmetry: str = "symmetric"
    bottom: TransverseProfile = TransverseProfile()
    deck: TransverseProfile = TransverseProfile()

    def __post_init__(self) -> None:
        values = (self.x_mm, self.width_mm, self.thickness_mm, self.bottom_z_mm)
        if not self.section_id:
            raise ValueError("section_id must not be empty")
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Section values must be finite")
        if self.width_mm <= 0 or self.thickness_mm <= 0:
            raise ValueError("A regular section requires positive width and thickness")
        if self.symmetry not in {"symmetric", "asymmetric"}:
            raise ValueError("symmetry must be 'symmetric' or 'asymmetric'")
        self.validate()

    def evaluate(self, u: float) -> tuple[float, float]:
        """Return (bottom_z_mm, deck_z_mm) at normalized lateral position u."""
        bottom = self.bottom_z_mm + self.bottom.evaluate(u)
        deck = self.bottom_z_mm + self.thickness_mm + self.deck.evaluate(u)
        return bottom, deck

    def validate(self, samples: int = 401, min_thickness_mm: float = 0.1) -> None:
        if samples < 3:
            raise ValueError("At least three validation samples are required")
        for i in range(samples):
            u = -1.0 + 2.0 * i / (samples - 1)
            bottom, deck = self.evaluate(u)
            thickness = deck - bottom
            if not math.isfinite(bottom) or not math.isfinite(deck):
                raise ValueError(f"{self.section_id}: non-finite surface at u={u:.6f}")
            if thickness <= min_thickness_mm:
                raise ValueError(
                    f"{self.section_id}: thickness {thickness:.6f} mm "
                    f"at u={u:.6f} is not above {min_thickness_mm} mm"
                )
        if self.symmetry == "symmetric":
            for i in range(samples // 2):
                u = (i + 0.5) * 2.0 / samples
                left, right = self.evaluate(-u), self.evaluate(u)
                if any(abs(a - b) > 1e-8 for a, b in zip(left, right)):
                    raise ValueError(f"{self.section_id}: asymmetric profile in symmetric mode")
