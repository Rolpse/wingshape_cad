import json
import tempfile
import unittest
from pathlib import Path

from src.board.geometry import (
    BoardDefinition, BoardStation, default_board_definition, generate_board_mesh, load_board_definition,
)


class BoardGeometryTests(unittest.TestCase):
    def test_default_mesh_is_closed_and_has_positive_volume(self):
        mesh = generate_board_mesh(default_board_definition())
        self.assertTrue(mesh.is_watertight)
        self.assertGreater(mesh.volume_litres, 0)
        self.assertGreater(len(mesh.faces), 1000)

    def test_default_envelope_matches_control_points(self):
        definition = default_board_definition()
        mesh = generate_board_mesh(definition)
        xs = [v[0] for v in mesh.vertices]
        ys = [v[1] for v in mesh.vertices]
        self.assertAlmostEqual(max(xs)-min(xs), 1600.0)
        self.assertAlmostEqual(max(ys)-min(ys), 520.0, places=5)

    def test_volume_is_stable_under_sampling_refinement(self):
        definition = default_board_definition()
        coarse = BoardDefinition(definition.name, definition.stations, 48, 8)
        fine = BoardDefinition(definition.name, definition.stations, 96, 16)
        coarse_volume = generate_board_mesh(coarse).volume_litres
        fine_volume = generate_board_mesh(fine).volume_litres
        self.assertLess(abs(fine_volume-coarse_volume) / fine_volume, 0.02)

    def test_deck_crown_changes_geometry_volume(self):
        definition = default_board_definition()
        stations = tuple(BoardStation(
            s.x_mm, s.width_mm, s.thickness_mm, s.bottom_z_mm,
            s.deck_crown_mm + 2.0, s.bottom_concave_mm
        ) for s in definition.stations)
        raised = BoardDefinition(definition.name, stations, 48, 8)
        base_volume = generate_board_mesh(BoardDefinition(
            definition.name, definition.stations, 48, 8)).volume_litres
        raised_volume = generate_board_mesh(raised).volume_litres
        self.assertGreater(raised_volume, base_volume)

    def test_mesh_exports_obj_and_binary_stl(self):
        mesh = generate_board_mesh(default_board_definition())
        with tempfile.TemporaryDirectory() as directory:
            obj = Path(directory) / "board.obj"
            stl = Path(directory) / "board.stl"
            mesh.write_obj(obj)
            mesh.write_stl(stl)
            self.assertTrue(obj.read_text().startswith("# SurfWing CAD"))
            self.assertEqual(stl.stat().st_size, 84 + 50 * len(mesh.faces))

    def test_json_definition_loads_and_generates(self):
        payload = {
            "name": "small",
            "stations": [
                {"x_mm": -100, "width_mm": 0, "thickness_mm": 20},
                {"x_mm": 0, "width_mm": 100, "thickness_mm": 20},
                {"x_mm": 100, "width_mm": 0, "thickness_mm": 20},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "board.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            definition = load_board_definition(path)
            mesh = generate_board_mesh(definition)
            self.assertEqual(definition.name, "small")
            self.assertTrue(mesh.is_watertight)

    def test_json_unknown_fields_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "board.json"
            path.write_text('{"stations": [], "magic": true}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_board_definition(path)

    def test_invalid_station_order_rejected(self):
        with self.assertRaises(ValueError):
            BoardDefinition("bad", (
                BoardStation(-1, 0, 10), BoardStation(1, 20, 10),
                BoardStation(0, 0, 10),
            ))

    def test_nonzero_tip_width_rejected(self):
        with self.assertRaises(ValueError):
            BoardDefinition("bad", (
                BoardStation(-1, 1, 10), BoardStation(0, 20, 10),
                BoardStation(1, 0, 10),
            ))


if __name__ == "__main__":
    unittest.main()
