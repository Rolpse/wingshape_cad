"""Parametric board geometry primitives for SurfWing CAD."""

from .geometry import BoardDefinition, BoardMesh, BoardStation, generate_board_mesh, load_board_definition

__all__ = ["BoardDefinition", "BoardMesh", "BoardStation", "generate_board_mesh", "load_board_definition"]
