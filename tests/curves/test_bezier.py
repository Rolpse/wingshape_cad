import unittest

from src.curves.bezier import (Anchor, BezierCurve, Continuity,
                               CurveFitToleranceError)


def sample_curve():
    return BezierCurve((
        Anchor("A", (0, 0), (-10, 0), (20, 40), Continuity.CORNER),
        Anchor("B", (100, 0), (80, 40), (110, 0), Continuity.CORNER),
    ))


class BezierControlPointTests(unittest.TestCase):
    def test_exact_insertion_preserves_original_curve(self):
        curve = sample_curve()
        split = curve.insert_on_segment(0, 0.37, "inserted")
        self.assertEqual(split.anchors[1].id, "inserted")
        for i in range(101):
            t = i / 100
            if t <= 0.37:
                actual = split.evaluate(0, t / 0.37)
            else:
                actual = split.evaluate(1, (t - 0.37) / (1 - 0.37))
            expected = curve.evaluate(0, t)
            for a, b in zip(actual, expected):
                self.assertAlmostEqual(a, b, places=9)

    def test_insertion_relaxes_symmetric_mode_to_smooth_without_changing_curve(self):
        curve = sample_curve().set_continuity("A", Continuity.SYMMETRIC)
        split = curve.insert_on_segment(0, 0.3, "split")
        self.assertEqual(split.anchors[0].continuity, Continuity.SMOOTH)
        for i in range(101):
            t = i / 100
            actual = split.evaluate(0, t / 0.3) if t <= 0.3 else split.evaluate(1, (t-0.3)/0.7)
            expected = curve.evaluate(0, t)
            for a, b in zip(actual, expected):
                self.assertAlmostEqual(a, b, places=9)

    def test_insertion_rejects_endpoints_and_duplicate_ids(self):
        curve = sample_curve()
        for t in (0.0, 1.0):
            with self.subTest(t=t), self.assertRaises(ValueError):
                curve.insert_on_segment(0, t)
        with self.assertRaises(ValueError):
            curve.insert_on_segment(0, 0.5, "A")

    def test_move_anchor_moves_handles_with_it(self):
        curve = sample_curve()
        moved = curve.move_anchor("A", (5, 7))
        self.assertEqual(moved.anchors[0].position, (5.0, 7.0))
        self.assertEqual(moved.anchors[0].incoming, (-5.0, 7.0))
        self.assertEqual(moved.anchors[0].outgoing, (25.0, 47.0))

    def test_corner_handles_are_independent(self):
        curve = sample_curve().set_handle("A", "outgoing", (15, 5))
        self.assertEqual(curve.anchors[0].incoming, (-10.0, 0.0))
        self.assertEqual(curve.anchors[0].outgoing, (15.0, 5.0))

    def test_smooth_handle_edit_keeps_tangents_collinear(self):
        curve = sample_curve().set_continuity("A", Continuity.SMOOTH)
        edited = curve.set_handle("A", "outgoing", (0, 20))
        anchor = edited.anchors[0]
        self.assertEqual(anchor.outgoing, (0.0, 20.0))
        self.assertEqual(anchor.incoming, (0.0, -10.0))

    def test_symmetric_handle_edit_keeps_equal_lengths(self):
        curve = sample_curve().set_continuity("A", Continuity.SYMMETRIC)
        edited = curve.set_handle("A", "outgoing", (0, 20))
        anchor = edited.anchors[0]
        self.assertAlmostEqual(
            sum((anchor.incoming[i]-anchor.position[i])**2 for i in range(2))**0.5,
            sum((anchor.outgoing[i]-anchor.position[i])**2 for i in range(2))**0.5,
        )

    def test_delete_protects_open_curve_endpoints(self):
        curve = sample_curve().insert_on_segment(0, 0.5, "middle")
        for endpoint in ("A", "B"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                curve.delete_anchor(endpoint)

    def test_delete_interior_anchor_reduces_anchor_count(self):
        curve = sample_curve().insert_on_segment(0, 0.5, "middle")
        deleted = curve.delete_anchor("middle")
        self.assertEqual([a.id for a in deleted.anchors], ["A", "B"])


    def test_bounded_delete_restores_exactly_split_curve(self):
        original = sample_curve()
        split = original.insert_on_segment(0, 0.43, "middle")
        restored, report = split.delete_anchor_bounded("middle", 0.5)
        self.assertTrue(report.accepted)
        self.assertLessEqual(report.max_sampled_deviation, 0.5)
        self.assertLess(report.rms_deviation, 0.1)
        self.assertEqual([a.id for a in restored.anchors], ["A", "B"])
    def test_bounded_delete_rejects_shape_change_over_tolerance(self):
        curve = BezierCurve((
            Anchor("A", (0, 0), (0, 0), (20, 0)),
            Anchor("M", (40, 35), (30, 35), (50, 35)),
            Anchor("B", (100, 0), (90, 0), (100, 0)),
        ))
        with self.assertRaises(CurveFitToleranceError) as caught:
            curve.delete_anchor_bounded("M", 0.01)
        self.assertFalse(caught.exception.report.accepted)
        self.assertGreater(caught.exception.report.max_sampled_deviation, 0.01)

    def test_bounded_delete_validates_tolerance_and_sample_count(self):
        curve = sample_curve().insert_on_segment(0, 0.5, "middle")
        with self.assertRaises(ValueError):
            curve.delete_anchor_bounded("middle", -1)
        with self.assertRaises(ValueError):
            curve.delete_anchor_bounded("middle", 1, samples_per_segment=4)

    def test_serialization_round_trip(self):
        curve = sample_curve().insert_on_segment(0, 0.4, "new")
        restored = BezierCurve.from_dict(curve.to_dict())
        self.assertEqual(restored, curve)

    def test_invalid_duplicate_ids_rejected(self):
        a = Anchor("same", (0, 0), (0, 0), (0, 0))
        b = Anchor("same", (10, 0), (10, 0), (10, 0))
        with self.assertRaises(ValueError):
            BezierCurve((a, b))

    def test_invalid_non_finite_point_rejected(self):
        with self.assertRaises(ValueError):
            Anchor("bad", (float("nan"), 0), (0, 0), (1, 1))

    def test_3d_curve_supported(self):
        curve = BezierCurve((
            Anchor("p0", (0, 0, 0), (0, 0, 0), (1, 2, 0)),
            Anchor("p1", (3, 0, 0), (2, 2, 0), (3, 0, 0)),
        ), dimension=3)
        self.assertEqual(len(curve.evaluate(0, 0.5)), 3)


if __name__ == "__main__":
    unittest.main()
