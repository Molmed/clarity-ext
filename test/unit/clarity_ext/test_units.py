import unittest
from clarity_ext.units import Units


class TestUnits(unittest.TestCase):
    def test_nano_to_pico_zero_unchanged(self):
        units = Units()
        self.assertEqual(units.convert(0, units.PICO, units.NANO), 0)

    def test_nano_to_pico_expected(self):
        units = Units()
        self.assertEqual(units.convert(40, units.PICO, units.NANO), 0.04)
        self.assertEqual(units.convert(1000, units.PICO, units.NANO), 1)
        self.assertEqual(units.convert(0.1, units.PICO, units.NANO), 0.0001)

    def test_pico_to_nano_expected(self):
        units = Units()
        self.assertEqual(units.convert(40, units.NANO, units.PICO), 40000)
        self.assertEqual(units.convert(1000, units.NANO, units.PICO), 1000000)
        self.assertEqual(units.convert(0.1, units.NANO, units.PICO), 100)

    def test_pico_to_pico_unchanged(self):
        units = Units()
        self.assertEqual(units.convert(40, units.PICO, units.PICO), 40)

