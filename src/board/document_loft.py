"""Adapter from versioned SurfWing board documents to the analytic section loft.

This adapter is additive and provisional. It consumes only analytic station
profiles; curve-backed profiles and foil assemblies are explicitly unsupported.
"""
from __future__ import annotations

from typing import Any

from src.board.section_mesh import SectionLoftMesh, generate_section_loft_mesh
from src.board.sections import BoardCrossSection, TransverseProfile
from src.domain.shape_document import validate_shape_document


_PROFILE_FIELDS = {
    "kind", "depth_mm", "half_width_u", "center_u", "left_depth_mm",
    "right_depth_mm", "standing_half_width_u", "blend_width_u",
}


def _profile_from_document(data: dict[str, Any]) -> TransverseProfile:
    if data.get("curve_id"):
        raise ValueError("curve-backed deck/bottom profiles are not yet supported by the analytic loft adapter")
    params = {key: value for key, value in data.items() if key in _PROFILE_FIELDS}
    return TransverseProfile(**params)


def generate_board_mesh_from_document(
    document: dict[str, Any],
    lateral_samples: int = 48,
    longitudinal_samples_per_interval: int = 1,
) -> SectionLoftMesh:
    """Validate a v0.1 surfboard/wingfoil-board document and loft its stations."""
    validate_shape_document(document)
    if document.get("product_kind") not in {"surfboard", "wingfoil_board"}:
        raise ValueError("document loft adapter requires product_kind surfboard or wingfoil_board")
    board = document.get("board")
    if not isinstance(board, dict):
        raise ValueError("board object is required")
    sections=[]
    for station in board.get("stations",[]):
        bottom=_profile_from_document(station["bottom_profile"])
        deck=_profile_from_document(station["deck_profile"])
        sections.append(BoardCrossSection(
            section_id=station["id"],
            x_mm=station["x_mm"],
            width_mm=station["width_mm"],
            thickness_mm=station["thickness_mm"],
            bottom_z_mm=station["bottom_z_mm"],
            symmetry=station.get("symmetry","symmetric"),
            bottom=bottom,
            deck=deck,
        ))
    return generate_section_loft_mesh(
        sections,
        lateral_samples=lateral_samples,
        longitudinal_samples_per_interval=longitudinal_samples_per_interval,
    )
