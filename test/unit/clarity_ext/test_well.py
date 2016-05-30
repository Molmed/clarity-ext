import unittest
from clarity_ext.domain import *


class WellTest(unittest.TestCase):
    def test_index_down_correct(self):
        plate = Plate(plate_type=Plate.PLATE_TYPE_96_WELLS)

        def assert_well(location, expected):
            pos = PlatePosition.create(location)
            well = Well(pos, plate)
            self.assertEqual(well.index_down_first, expected)

        assert_well("A:1", 1)
        assert_well("A:5", 33)
        assert_well("E:12", 93)
        assert_well("B:7", 50)

if __name__ == "__main__":
    unittest.main()
