import unittest

from src.board.section_mesh import generate_section_loft_mesh
from src.board.sections import BoardCrossSection, TransverseProfile


def section(section_id, x, width, thickness, bottom=None, deck=None):
    return BoardCrossSection(section_id, x, width, thickness,
                             bottom=bottom or TransverseProfile(),
                             deck=deck or TransverseProfile())


class SectionLoftMeshTests(unittest.TestCase):
    def test_two_sections_make_closed_positive_volume_mesh(self):
        mesh = generate_section_loft_mesh([
            section("nose", 0, 180, 70), section("tail", 1000, 260, 80)
        ], lateral_samples=24)
        self.assertTrue(mesh.is_watertight)
        self.assertGreater(mesh.volume_litres, 0)
        self.assertGreater(mesh.signed_volume_mm3(), 0)

    def test_independent_asymmetric_profiles_are_lofted(self):
        profile = TransverseProfile("v", left_depth_mm=2, right_depth_mm=5)
        mesh = generate_section_loft_mesh([
            BoardCrossSection("a", 0, 300, 80, symmetry="asymmetric", bottom=profile),
            BoardCrossSection("b", 500, 420, 90, symmetry="asymmetric", bottom=profile,
                              deck=TransverseProfile("dome", depth_mm=2)),
        ])
        self.assertTrue(mesh.is_watertight)
        self.assertGreater(mesh.volume_litres, 0)

    def test_sections_must_be_ordered(self):
        with self.assertRaisesRegex(ValueError, "increasing"):
            generate_section_loft_mesh([section("b", 10, 200, 80), section("a", 0, 200, 80)])

    def test_lateral_sample_count_must_be_even(self):
        with self.assertRaisesRegex(ValueError, "even"):
            generate_section_loft_mesh([section("a", 0, 200, 80), section("b", 100, 200, 80)],
                                       lateral_samples=9)


if __name__ == "__main__":
    unittest.main()
