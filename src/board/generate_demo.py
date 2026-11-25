"""Generate a starter board mesh: python -m src.board.generate_demo [output-dir] [board-definition.json]."""
from pathlib import Path
import sys

from .geometry import default_board_definition, generate_board_mesh, load_board_definition

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build/board-demo")
out.mkdir(parents=True, exist_ok=True)
definition = load_board_definition(Path(sys.argv[2])) if len(sys.argv) > 2 else default_board_definition()
mesh = generate_board_mesh(definition)
mesh.write_obj(out / "surfwing-board-demo.obj")
mesh.write_stl(out / "surfwing-board-demo.stl")
print(f"vertices={len(mesh.vertices)} faces={len(mesh.faces)} "
      f"watertight={mesh.is_watertight} volume_l={mesh.volume_litres:.2f}")
