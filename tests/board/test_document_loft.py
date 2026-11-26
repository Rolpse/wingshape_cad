import json
import unittest
from pathlib import Path

from src.board.document_loft import generate_board_mesh_from_document
from src.domain.shape_document import validate_shape_document

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/"examples"/"domain"


def load_fixture(name):
    return json.loads((FIXTURES/name).read_text(encoding="utf-8"))


class DocumentLoftAdapterTests(unittest.TestCase):
    def test_surfboard_document_lofts_to_closed_positive_solid(self):
        doc=load_fixture("surfboard-0.1.json")
        mesh=generate_board_mesh_from_document(doc,lateral_samples=24,longitudinal_samples_per_interval=2)
        self.assertTrue(mesh.is_watertight)
        self.assertGreater(mesh.signed_volume_mm3(),0)
        self.assertGreater(mesh.volume_litres,0)

    def test_wingfoil_board_document_lofts(self):
        doc=load_fixture("wingfoil-board-0.1.json")
        mesh=generate_board_mesh_from_document(doc,lateral_samples=24)
        self.assertTrue(mesh.is_watertight)
        self.assertGreater(mesh.signed_volume_mm3(),0)

    def test_foil_document_rejected_by_board_loft(self):
        doc=load_fixture("foil-assembly-0.1.json")
        with self.assertRaisesRegex(ValueError,"requires product_kind"):
            generate_board_mesh_from_document(doc)

    def test_longitudinal_samples_densify_ring_count(self):
        doc=load_fixture("surfboard-0.1.json")
        mesh=generate_board_mesh_from_document(doc,lateral_samples=24,longitudinal_samples_per_interval=3)
        ring_size=2*(24+1)
        expected_rings=(len(doc["board"]["stations"])-1)*3+1
        self.assertEqual(len(mesh.vertices),expected_rings*ring_size+2)

    def test_asymmetric_profile_is_lofted_when_declared(self):
        doc=load_fixture("wingfoil-board-0.1.json")
        station=doc["board"]["stations"][2]
        station["symmetry"]="asymmetric"
        station["bottom_profile"]={"kind":"v","left_depth_mm":2,"right_depth_mm":5}
        validate_shape_document(doc)
        mesh=generate_board_mesh_from_document(doc,lateral_samples=24)
        self.assertTrue(mesh.is_watertight)
        self.assertGreater(mesh.signed_volume_mm3(),0)

    def test_curve_backed_profile_rejected_by_adapter(self):
        doc=load_fixture("surfboard-0.1.json")
        doc["board"]["stations"][0]["bottom_profile"]={"kind":"flat","curve_id":"curve-rocker"}
        validate_shape_document(doc)
        with self.assertRaisesRegex(ValueError,"curve-backed"):
            generate_board_mesh_from_document(doc)

    def test_longitudinal_sample_count_must_be_positive(self):
        doc=load_fixture("surfboard-0.1.json")
        with self.assertRaisesRegex(ValueError,"longitudinal_samples_per_interval"):
            generate_board_mesh_from_document(doc,longitudinal_samples_per_interval=0)


if __name__=="__main__":
    unittest.main()
