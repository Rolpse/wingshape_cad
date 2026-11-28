import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.domain.outline_editor_adapter import merge_outline_into_shape_document
from src.domain.shape_document import validate_shape_document

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = json.loads((ROOT / "examples/domain/wingfoil-board-0.1.json").read_text(encoding="utf-8"))


def outline_fixture():
    return {
        "document_type": "surfwing.outline",
        "schema_version": "0.2.0",
        "name": "Editor test board 1600 x 520",
        "units": "mm",
        "closed": True,
        "length_mm": 1600,
        "width_mm": 520,
        "anchors": [
            {"id": "nose", "position": [0, -800], "incoming_handle": [0, -800], "outgoing_handle": [0, -800], "continuity": "corner"},
            {"id": "starboard-beam", "position": [260, 0], "incoming_handle": [260, -500], "outgoing_handle": [260, 500], "continuity": "symmetric"},
            {"id": "tail", "position": [0, 800], "incoming_handle": [140, 800], "outgoing_handle": [-140, 800], "continuity": "symmetric"},
            {"id": "port-beam", "position": [-260, 0], "incoming_handle": [-260, 500], "outgoing_handle": [-260, -500], "continuity": "symmetric"}
        ]
    }


class OutlineEditorAdapterTests(unittest.TestCase):
    def test_builds_schema_valid_shape_document_and_maps_editor_axes(self):
        outline = outline_fixture()
        base = copy.deepcopy(TEMPLATE)
        document = merge_outline_into_shape_document(outline, base)
        validate_shape_document(document)
        curve_id = document["board"]["outline_curve_id"]
        curve = next(c for c in document["curves"] if c["id"] == curve_id)
        self.assertEqual(curve["revision"], 1)
        self.assertEqual(curve["role"], "outline_xy")
        self.assertEqual(len(curve["anchors"]), 4)
        self.assertEqual(curve["anchors"][0]["position"], [-800.0, 0.0])
        self.assertEqual(curve["anchors"][1]["continuity"], "symmetric")
        self.assertEqual(document["name"], outline["name"])
        self.assertEqual(document["board"]["nose"]["shape_family"], "custom")
        self.assertEqual(document["board"]["tail"]["shape_family"], "custom")
        self.assertEqual(document["derived"]["properties"], [])
        self.assertEqual(document["derived"]["source_revision"], None)
        self.assertIn("template-derived", document["derived"]["validation"][0]["message"])

    def test_station_widths_are_sampled_and_section_frames_follow_station_x(self):
        document = merge_outline_into_shape_document(outline_fixture(), copy.deepcopy(TEMPLATE))
        stations = document["board"]["stations"]
        self.assertEqual([s["x_mm"] for s in stations], [-600.0, -300.0, 0.0, 300.0, 600.0])
        self.assertTrue(all(s["width_mm"] > 0 for s in stations))
        self.assertAlmostEqual(stations[2]["width_mm"], 520.0, delta=0.5)
        frames = {f["id"]: f for f in document["frames"]}
        for station in stations:
            frame = frames[station["frame_id"]]
            self.assertAlmostEqual(frame["origin_mm"][0], station["x_mm"])
            self.assertAlmostEqual(frame["origin_mm"][2], station["bottom_z_mm"])

    def test_rocker_and_stringer_guides_scale_to_new_length(self):
        document = merge_outline_into_shape_document(outline_fixture(), copy.deepcopy(TEMPLATE))
        for curve_id in (document["board"]["rocker_curve_id"], document["board"]["stringer_curve_id"]):
            curve = next(c for c in document["curves"] if c["id"] == curve_id)
            xs = [a["position"][0] for a in curve["anchors"]]
            self.assertEqual(min(xs), -800.0)
            self.assertEqual(max(xs), 800.0)

    def test_input_template_and_outline_are_not_mutated(self):
        outline = outline_fixture()
        base = copy.deepcopy(TEMPLATE)
        before_outline = copy.deepcopy(outline)
        before_template = copy.deepcopy(base)
        merge_outline_into_shape_document(outline, base)
        self.assertEqual(outline, before_outline)
        self.assertEqual(base, before_template)

    def test_self_intersecting_outline_is_rejected(self):
        outline = outline_fixture()
        outline["anchors"] = [
            {"id": "p1", "position": [-100, -100], "incoming_handle": [-100, -100], "outgoing_handle": [-100, -100], "continuity": "corner"},
            {"id": "p2", "position": [100, 100], "incoming_handle": [100, 100], "outgoing_handle": [100, 100], "continuity": "corner"},
            {"id": "p3", "position": [-100, 100], "incoming_handle": [-100, 100], "outgoing_handle": [-100, 100], "continuity": "corner"},
            {"id": "p4", "position": [100, -100], "incoming_handle": [100, -100], "outgoing_handle": [100, -100], "continuity": "corner"}
        ]
        with self.assertRaisesRegex(ValueError, "self-intersection"):
            merge_outline_into_shape_document(outline, copy.deepcopy(TEMPLATE))


    def test_cli_writes_schema_valid_shape_document(self):
        outline_path = None
        output_path = None
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            outline_path = temp / "editor outline.json"
            output_path = temp / "converted shape.json"
            outline_path.write_text(json.dumps(outline_fixture()), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.domain.outline_editor_adapter",
                    str(outline_path),
                    "--template",
                    str(ROOT / "examples/domain/wingfoil-board-0.1.json"),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(output_path.is_file())
            converted = json.loads(output_path.read_text(encoding="utf-8"))
            validate_shape_document(converted)
            self.assertEqual(converted["board"]["outline_curve_id"], "curve-outline")
            self.assertEqual(converted["board"]["stations"][2]["width_mm"], 520.0)
            self.assertIn("Validated Shape Document", completed.stdout)

    def test_duplicate_anchor_ids_and_non_finite_coordinates_are_rejected(self):
        outline = outline_fixture()
        outline["anchors"][1]["id"] = outline["anchors"][0]["id"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            merge_outline_into_shape_document(outline, copy.deepcopy(TEMPLATE))
        outline = outline_fixture()
        outline["anchors"][1]["position"][0] = float("nan")
        with self.assertRaisesRegex(ValueError, "non-finite"):
            merge_outline_into_shape_document(outline, copy.deepcopy(TEMPLATE))


if __name__ == "__main__":
    unittest.main()
