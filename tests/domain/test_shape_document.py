import copy
import json
import unittest
from pathlib import Path

from src.domain.shape_document import (
    ShapeDocumentError, apply_variant, convert_length, load_schema, loads_document,
    validate_document, validate_shape_document, import_legacy_board_json, dumps_document,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "examples" / "domain"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class ShapeDocumentSchemaTests(unittest.TestCase):
    def test_schema_is_draft_2020_12_and_well_formed(self):
        schema = load_schema()
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema dependency not installed")
        jsonschema.Draft202012Validator.check_schema(schema)

    def test_three_product_fixtures_validate(self):
        for name in ("surfboard-0.1.json", "wingfoil-board-0.1.json", "foil-assembly-0.1.json"):
            with self.subTest(name=name):
                doc=fixture(name)
                self.assertEqual(validate_document(doc), [])
                try:
                    import jsonschema
                except ImportError:
                    continue
                jsonschema.Draft202012Validator(load_schema()).validate(doc)

    def test_round_trip_preserves_semantic_ids_and_handles(self):
        original=fixture("wingfoil-board-0.1.json")
        loaded=loads_document(dumps_document(original))
        self.assertEqual(original["model_id"],loaded["model_id"])
        self.assertEqual([c["id"] for c in original["curves"]],[c["id"] for c in loaded["curves"]])
        self.assertEqual(original["curves"][0]["anchors"],loaded["curves"][0]["anchors"])
        self.assertEqual([s["id"] for s in original["board"]["stations"]],[s["id"] for s in loaded["board"]["stations"]])

    def test_units_convert_once_to_mm(self):
        self.assertAlmostEqual(convert_length(1,"m"),1000)
        self.assertAlmostEqual(convert_length(1,"in"),25.4)
        self.assertAlmostEqual(convert_length(1,"ft"),304.8)
        with self.assertRaises(ValueError):
            convert_length(1,"yard")

    def test_duplicate_ids_rejected(self):
        doc=fixture("surfboard-0.1.json")
        doc["board"]["stations"][0]["id"]=doc["curves"][0]["anchors"][0]["id"]
        self.assertTrue(any("duplicate semantic id" in e for e in validate_document(doc)))

    def test_bad_frame_basis_rejected(self):
        doc=fixture("surfboard-0.1.json")
        doc["frames"][0]["basis_axes"][0]=[2,0,0]
        self.assertTrue(any("orthonormal" in e or "determinant" in e for e in validate_document(doc)))

    def test_outline_self_intersection_rejected_with_curve_id(self):
        doc=fixture("surfboard-0.1.json")
        outline=doc["curves"][0]
        points=[[0,0],[100,100],[0,100],[100,0]]
        outline["anchors"]=[]
        for i,p in enumerate(points):
            outline["anchors"].append({"id":f"bowtie-anchor-{i}","position":p,"incoming_handle":p[:],"outgoing_handle":p[:],"continuity":"corner"})
        errors=validate_document(doc)
        self.assertTrue(any("curve curve-outline: self-intersection" in e for e in errors),errors)

    def test_deck_bottom_crossing_rejected(self):
        doc=fixture("surfboard-0.1.json")
        station=doc["board"]["stations"][2]
        station["deck_profile"]={"kind":"single_concave","depth_mm":80,"half_width_u":0.6}
        self.assertTrue(any("crossing/thickness" in e for e in validate_document(doc)))

    def test_declared_symmetric_section_rejects_asymmetric_profile(self):
        doc=fixture("surfboard-0.1.json")
        station=doc["board"]["stations"][1]
        station["bottom_profile"]={"kind":"v","left_depth_mm":1,"right_depth_mm":3}
        station["symmetry"]="symmetric"
        self.assertTrue(any("asymmetric profile declared symmetric" in e for e in validate_document(doc)))

    def test_missing_outline_reference_rejected(self):
        doc=fixture("surfboard-0.1.json")
        doc["board"]["outline_curve_id"]="missing-outline"
        self.assertTrue(any("closed 2D curve" in e for e in validate_document(doc)))

    def test_feature_graph_cycles_rejected(self):
        doc=fixture("surfboard-0.1.json")
        doc["feature_graph"]["nodes"]=[
            {"id":"feature-a","type":"custom","inputs":["feature-b"],"outputs":[],"parameters":{},"revision":0,"enabled":True},
            {"id":"feature-b","type":"custom","inputs":["feature-a"],"outputs":[],"parameters":{},"revision":0,"enabled":True},
        ]
        errors=validate_document(doc)
        self.assertTrue(any("feature graph cycle" in e for e in errors),errors)

    def test_variant_changes_copy_without_mutating_base(self):
        base=fixture("surfboard-0.1.json")
        original=json.dumps(base,sort_keys=True)
        variant=base["variants"][0]
        changed=apply_variant(base,variant)
        self.assertEqual(base["board"]["stations"][2]["width_mm"],480)
        self.assertEqual(changed["board"]["stations"][2]["width_mm"],500)
        self.assertEqual(original,json.dumps(base,sort_keys=True))
        validate_shape_document(changed)

    def test_variant_cannot_change_identity(self):
        base=fixture("surfboard-0.1.json")
        variant={"changes":[{"target_id":"station-2","operation":"set","field_path":["id"],"value":"other"}]}
        with self.assertRaises(ShapeDocumentError):
            apply_variant(base,variant)

    def test_foil_attachment_cycle_rejected(self):
        doc=fixture("foil-assembly-0.1.json")
        comps=doc["foil_assembly"]["components"]
        comps[0]["attachment"]["parent_component_id"]=comps[1]["id"]
        comps[1]["attachment"]["parent_component_id"]=comps[0]["id"]
        self.assertTrue(any("attachment cycle" in e for e in validate_document(doc)))

    def test_smooth_aligned_handles_accept_unequal_lengths(self):
        doc=fixture("surfboard-0.1.json")
        anchor=doc["curves"][1]["anchors"][1]
        x,z=anchor["position"]
        anchor["incoming_handle"]=[x-10,z]
        anchor["outgoing_handle"]=[x+25,z]
        anchor["continuity"]="smooth_aligned"
        self.assertEqual(validate_document(doc),[])

    def test_smooth_aligned_rejects_non_collinear_handles(self):
        doc=fixture("surfboard-0.1.json")
        anchor=doc["curves"][1]["anchors"][1]
        x,z=anchor["position"]
        anchor["incoming_handle"]=[x-10,z]
        anchor["outgoing_handle"]=[x,z+10]
        anchor["continuity"]="smooth_aligned"
        self.assertTrue(any("not opposed/collinear" in e for e in validate_document(doc)))

    def test_symmetric_handles_reject_unequal_lengths(self):
        doc=fixture("surfboard-0.1.json")
        anchor=doc["curves"][1]["anchors"][1]
        x,z=anchor["position"]
        anchor["incoming_handle"]=[x-10,z]
        anchor["outgoing_handle"]=[x+25,z]
        anchor["continuity"]="symmetric"
        self.assertTrue(any("symmetric handles differ" in e for e in validate_document(doc)))

    def test_schema_rejects_unknown_document_field(self):
        doc=fixture("surfboard-0.1.json")
        doc["unexpected_field"]=True
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema dependency not installed")
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(load_schema()).validate(doc)

    def test_variant_remove_optional_curve_frame(self):
        base=fixture("surfboard-0.1.json")
        variant={"changes":[{"target_id":"curve-rocker","operation":"remove","field_path":["frame_id"]}]}
        changed=apply_variant(base,variant)
        self.assertNotIn("frame_id",changed["curves"][1])
        self.assertIn("frame_id",base["curves"][1])
        validate_shape_document(changed)

    def test_missing_feature_input_rejected(self):
        doc=fixture("surfboard-0.1.json")
        doc["feature_graph"]["nodes"]=[{"id":"feature-1","type":"custom","inputs":["missing-semantic"],"outputs":[],"parameters":{},"revision":0,"enabled":True}]
        self.assertTrue(any("missing semantic input" in e for e in validate_document(doc)))

    def test_legacy_import_deterministic_and_source_preserved(self):
        legacy={"name":"Legacy test","perimeter_samples":48,"longitudinal_samples_per_interval":8,
                "stations":[{"x_mm":-300,"width_mm":0,"thickness_mm":50},
                           {"x_mm":-150,"width_mm":200,"thickness_mm":55,"bottom_z_mm":2},
                           {"x_mm":0,"width_mm":300,"thickness_mm":60,"bottom_z_mm":4,"deck_crown_mm":3,"bottom_concave_mm":1},
                           {"x_mm":150,"width_mm":200,"thickness_mm":55,"bottom_z_mm":2},
                           {"x_mm":300,"width_mm":0,"thickness_mm":50}]}
        one=import_legacy_board_json(legacy)
        two=import_legacy_board_json(legacy)
        self.assertEqual(one["model_id"],two["model_id"])
        self.assertEqual(one["board"]["stations"][0]["width_mm"],0.001)
        self.assertEqual(one["board"]["legacy_source"],legacy)
        self.assertTrue(any(v["code"]=="LEGACY_APPROX" for v in one["derived"]["validation"]))
        validate_shape_document(one)


if __name__ == "__main__":
    unittest.main()
