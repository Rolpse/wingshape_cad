import unittest
from src.hydrodynamics.performance import (
 FRESH_WATER_20C, buoyant_force_n, Fluid, displaced_volume_m3, force_from_coefficient,
 froude_number_chord, froude_number_submergence, dynamic_pressure_pa, moment_from_coefficient,
 vertical_equilibrium_residual_n, reynolds_number)

class HydrodynamicPerformanceTests(unittest.TestCase):
 def test_reynolds_number(self):
  self.assertAlmostEqual(reynolds_number(5.0, 0.12, FRESH_WATER_20C), 597724.5509, delta=1.0)
 def test_submergence_froude_number(self):
  self.assertAlmostEqual(froude_number_submergence(4.0, 0.48), 1.84365, delta=0.0001)
 def test_chord_froude_number(self):
  self.assertAlmostEqual(froude_number_chord(4.0, 0.12), 3.689, delta=0.002)
 def test_dynamic_pressure(self):
  self.assertAlmostEqual(dynamic_pressure_pa(5.0, FRESH_WATER_20C), 12477.5)
 def test_force_from_lift_coefficient(self):
  lift=force_from_coefficient(5.0, 0.08, 0.6, FRESH_WATER_20C)
  self.assertAlmostEqual(lift, 0.5*998.2*25*0.08*0.6)
 def test_buoyancy_and_static_equilibrium(self):
  volume=displaced_volume_m3(100.0, FRESH_WATER_20C)
  self.assertAlmostEqual(buoyant_force_n(volume, FRESH_WATER_20C), 100*9.80665)
  self.assertAlmostEqual(vertical_equilibrium_residual_n(100, volume, FRESH_WATER_20C), 0.0)
 def test_pitching_moment_from_coefficient(self):
  moment=moment_from_coefficient(5, 0.08, 0.12, -0.03, FRESH_WATER_20C)
  self.assertAlmostEqual(moment, 0.5*998.2*25*0.08*0.12*-0.03)
 def test_static_displacement(self):
  self.assertAlmostEqual(displaced_volume_m3(100, FRESH_WATER_20C), 100/998.2)
 def test_rejects_invalid_fluid(self):
  with self.assertRaises(ValueError): Fluid(0, 0.001)
 def test_rejects_invalid_geometry(self):
  with self.assertRaises(ValueError): reynolds_number(3.0, 0.0, FRESH_WATER_20C)
 def test_zero_speed_gives_zero_force_and_reynolds(self):
  self.assertEqual(force_from_coefficient(0, 0.1, 0.5, FRESH_WATER_20C), 0)
  self.assertEqual(reynolds_number(0, 0.1, FRESH_WATER_20C), 0)

if __name__ == "__main__":
 unittest.main()
