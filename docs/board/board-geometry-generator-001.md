# Parametric board geometry generator 001

Initial code builds a closed triangle mesh from longitudinal stations. Parameters include X, width, thickness, bottom height, deck crown and bottom concave. Cross-sections are interpolated and triangulated, with nose/tail caps. OBJ and binary STL export are supported.

## Limitations
Not an interactive CAD GUI or B-rep kernel. No STEP export, control-point editor, scan import, curvature analysis or manufacturing qualification. Rail cross-sections are approximate. Volume is mesh-derived and needs independent validation.

## Demo
Starter JSON: examples/board/wingfoil-1600x520-starter.json
Run: python -m src.board.generate_demo build/board-demo examples/board/wingfoil-1600x520-starter.json

Outputs OBJ and STL. Generator checks mesh closure and positive volume; tests cover envelope, watertightness, exports and sampling stability.
