import unittest

from src.board.sections import BoardCrossSection, TransverseProfile


class TransverseProfileTests(unittest.TestCase):
    def test_flat_is_constant(self):
        p = TransverseProfile("flat")
        self.assertEqual([p.evaluate(u) for u in (-1, -0.5, 0, 0.5, 1)], [0] * 5)

    def test_v_rises_from_keel_to_rails(self):
        p = TransverseProfile("v", depth_mm=4)
        self.assertEqual(p.evaluate(0), 0)
        self.assertAlmostEqual(p.evaluate(1), 4)
        self.assertAlmostEqual(p.evaluate(-1), 4)

    def test_single_concave_has_center_depression(self):
        p = TransverseProfile("single_concave", depth_mm=3, half_width_u=0.6)
        self.assertAlmostEqual(p.evaluate(0), -3)
        self.assertAlmostEqual(p.evaluate(0.6), 0)
        self.assertAlmostEqual(p.evaluate(1), 0)

    def test_double_concave_has_two_depressions(self):
        p = TransverseProfile("double_concave", depth_mm=2,
                              center_u=0.4, half_width_u=0.2)
        self.assertAlmostEqual(p.evaluate(-0.4), -2)
        self.assertAlmostEqual(p.evaluate(0.4), -2)
        self.assertGreater(p.evaluate(0), p.evaluate(0.4))

    def test_dome_is_highest_at_center(self):
        p = TransverseProfile("dome", depth_mm=5)
        self.assertAlmostEqual(p.evaluate(0), 5)
        self.assertAlmostEqual(p.evaluate(1), 0)

    def test_asymmetric_v_allowed_only_when_declared_asymmetric(self):
        profile = TransverseProfile("v", depth_mm=0,
                                    left_depth_mm=2, right_depth_mm=5)
        BoardCrossSection("asym", 0, 500, 80, symmetry="asymmetric",
                          bottom=profile)
        with self.assertRaisesRegex(ValueError, "asymmetric profile"):
            BoardCrossSection("wrong-mode", 0, 500, 80, symmetry="symmetric",
                              bottom=profile)

    def test_deck_bottom_crossing_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "thickness"):
            BoardCrossSection(
                "crossing", 0, 500, 2,
                bottom=TransverseProfile("single_concave", depth_mm=2),
                deck=TransverseProfile("flat"),
            )

    def test_u_outside_domain_rejected(self):
        with self.assertRaises(ValueError):
            TransverseProfile().evaluate(1.01)

    def test_section_evaluates_independent_surfaces(self):
        section = BoardCrossSection(
            "mid", 0, 520, 90, bottom_z_mm=8,
            bottom=TransverseProfile("single_concave", depth_mm=2),
            deck=TransverseProfile("dome", depth_mm=4),
        )
        b, d = section.evaluate(0)
        self.assertAlmostEqual(b, 6)
        self.assertAlmostEqual(d, 102)


if __name__ == "__main__":
    unittest.main()
