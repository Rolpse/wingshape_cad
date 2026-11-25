"""Transparent first-order hydrofoil performance calculations.

These equations are screening tools, not a substitute for CFD or test data.
All quantities use SI units.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Fluid:
    density_kg_m3: float
    dynamic_viscosity_pa_s: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.density_kg_m3) or self.density_kg_m3 <= 0:
            raise ValueError("fluid density must be finite and > 0")
        if not math.isfinite(self.dynamic_viscosity_pa_s) or self.dynamic_viscosity_pa_s <= 0:
            raise ValueError("dynamic viscosity must be finite and > 0")


FRESH_WATER_20C = Fluid(density_kg_m3=998.2, dynamic_viscosity_pa_s=1.002e-3)


def reynolds_number(speed_m_s: float, chord_m: float, fluid: Fluid) -> float:
    """Chord-based Reynolds number Re = rho * U * c / mu."""
    _positive_finite("speed_m_s", speed_m_s, allow_zero=True)
    _positive_finite("chord_m", chord_m)
    return fluid.density_kg_m3 * speed_m_s * chord_m / fluid.dynamic_viscosity_pa_s


def froude_number_submergence(speed_m_s: float, submergence_m: float, gravity_m_s2: float = 9.80665) -> float:
    """Submergence Froude number Fr_h = U / sqrt(g h)."""
    _positive_finite("speed_m_s", speed_m_s, allow_zero=True)
    _positive_finite("submergence_m", submergence_m)
    _positive_finite("gravity_m_s2", gravity_m_s2)
    return speed_m_s / math.sqrt(gravity_m_s2 * submergence_m)


def froude_number_chord(speed_m_s: float, chord_m: float, gravity_m_s2: float = 9.80665) -> float:
    """Chord Froude number Fr_c = U / sqrt(g c)."""
    _positive_finite("speed_m_s", speed_m_s, allow_zero=True)
    _positive_finite("chord_m", chord_m)
    _positive_finite("gravity_m_s2", gravity_m_s2)
    return speed_m_s / math.sqrt(gravity_m_s2 * chord_m)


def dynamic_pressure_pa(speed_m_s: float, fluid: Fluid) -> float:
    """Dynamic pressure q = 0.5 * rho * U^2."""
    _positive_finite("speed_m_s", speed_m_s, allow_zero=True)
    return 0.5 * fluid.density_kg_m3 * speed_m_s**2


def force_from_coefficient(speed_m_s: float, reference_area_m2: float, coefficient: float, fluid: Fluid) -> float:
    """Signed force magnitude component F = q * S * coefficient."""
    _positive_finite("speed_m_s", speed_m_s, allow_zero=True)
    _positive_finite("reference_area_m2", reference_area_m2)
    if not math.isfinite(coefficient):
        raise ValueError("coefficient must be finite")
    return dynamic_pressure_pa(speed_m_s, fluid) * reference_area_m2 * coefficient


def moment_from_coefficient(speed_m_s: float, reference_area_m2: float, reference_chord_m: float, coefficient: float, fluid: Fluid) -> float:
    """Moment M = q * S * c_ref * Cm about the declared reference point."""
    _positive_finite("speed_m_s", speed_m_s, allow_zero=True)
    _positive_finite("reference_area_m2", reference_area_m2)
    _positive_finite("reference_chord_m", reference_chord_m)
    if not math.isfinite(coefficient):
        raise ValueError("coefficient must be finite")
    return dynamic_pressure_pa(speed_m_s, fluid) * reference_area_m2 * reference_chord_m * coefficient


def buoyant_force_n(displaced_volume_m3_value: float, fluid: Fluid, gravity_m_s2: float = 9.80665) -> float:
    """Archimedean buoyancy B = rho * g * V."""
    _positive_finite("displaced_volume_m3_value", displaced_volume_m3_value, allow_zero=True)
    _positive_finite("gravity_m_s2", gravity_m_s2)
    return fluid.density_kg_m3 * gravity_m_s2 * displaced_volume_m3_value


def vertical_equilibrium_residual_n(mass_kg: float, displaced_volume_m3_value: float, fluid: Fluid, gravity_m_s2: float = 9.80665) -> float:
    """Positive means net upward force; zero is static vertical equilibrium."""
    _positive_finite("mass_kg", mass_kg, allow_zero=True)
    return buoyant_force_n(displaced_volume_m3_value, fluid, gravity_m_s2) - mass_kg * gravity_m_s2


def displaced_volume_m3(mass_kg: float, fluid: Fluid) -> float:
    """Static equilibrium displacement V = m / rho (no dynamic lift/planing)."""
    _positive_finite("mass_kg", mass_kg, allow_zero=True)
    return mass_kg / fluid.density_kg_m3


def _positive_finite(name: str, value: float, *, allow_zero: bool = False) -> None:
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        qualifier = ">= 0" if allow_zero else "> 0"
        raise ValueError(f"{name} must be finite and {qualifier}")
