import unittest
from pathlib import Path
from src.cam.estlcam_nc_validator import AxisLimit, EstlcamNCValidator

class EstlcamNCValidatorTests(unittest.TestCase):
    def setUp(self):
        self.validator = EstlcamNCValidator(expected_unit="mm", axis_limits={
            "X": AxisLimit(0, 1000), "Y": AxisLimit(0, 500), "Z": AxisLimit(-100, 100)})

    def test_accepts_explicit_linear_xyz_moves(self):
        report = self.validator.validate("G00 X0 Y0 Z10\nG01 X250 Y30 Z-2 F1200")
        self.assertTrue(report.ok, report.errors)
        self.assertEqual(report.motion_lines, 2)
        self.assertEqual(report.final_position, {"X": 250.0, "Y": 30.0, "Z": -2.0})

    def test_accepts_parenthesized_comment_and_line_number(self):
        report = self.validator.validate("(safe start)\nN10 G00 X0 Y0 Z5")
        self.assertTrue(report.ok, report.errors)

    def test_rejects_implicit_modal_motion(self):
        report = self.validator.validate("G00 X0 Y0 Z5\nX10 Y10")
        self.assertFalse(report.ok)
        self.assertTrue(any("explicit G00 or G01" in e for e in report.errors))

    def test_rejects_unknown_g_codes(self):
        for code in ("G20", "G21", "G90", "G91", "G81", "G54"):
            with self.subTest(code=code):
                self.assertFalse(self.validator.validate(f"{code} X0").ok)

    def test_rejects_arcs_in_linear_only_mvp(self):
        self.assertFalse(self.validator.validate("G02 X10 Y10 I5 J0").ok)

    def test_rejects_multiple_g_codes_on_one_line(self):
        self.assertFalse(self.validator.validate("G00 G01 X0 Y0 Z5").ok)

    def test_rejects_rotary_axes_and_unknown_words(self):
        for line in ("G01 X0 Y0 Z0 A90", "G01 X0 Y0 Z0 T1"):
            with self.subTest(line=line):
                self.assertFalse(self.validator.validate(line).ok)

    def test_rejects_spindle_word_until_output_is_verified(self):
        self.assertFalse(self.validator.validate("G01 X10 Y10 Z0 F500 S12000").ok)

    def test_rejects_out_of_envelope_coordinate(self):
        report = self.validator.validate("G00 X1001 Y0 Z5")
        self.assertFalse(report.ok)
        self.assertTrue(any("outside configured range" in e for e in report.errors))

    def test_rejects_zero_or_negative_feed(self):
        for feed in ("F0", "F-1"):
            with self.subTest(feed=feed):
                self.assertFalse(self.validator.validate(f"G01 X10 Y0 Z0 {feed}").ok)

    def test_rejects_empty_program(self):
        self.assertFalse(self.validator.validate("  \n ").ok)

    def test_synthetic_smoke_fixture_parses(self):
        fixture = Path(__file__).parent / "fixtures" / "linear_xyz_smoke.nc"
        report = self.validator.validate(fixture.read_text(encoding="utf-8"))
        self.assertTrue(report.ok, report.errors)
        self.assertEqual(report.motion_lines, 5)

if __name__ == "__main__":
    unittest.main()
