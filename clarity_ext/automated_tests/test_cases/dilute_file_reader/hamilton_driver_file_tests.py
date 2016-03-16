# Tests for reading from a Hamilton driver file,
# using the utility dilute_filer_reader

import unittest
import os
import inspect
from ...utility.dilute_filer_reader.hamilton_driver_file_reader import HamiltonReader as FileReader
from ...utility.dilute_filer_reader.hamilton_driver_file_reader import HamiltonColumnReference as ColumnRef

DRIVER_FILE_RELATIVE_PATH = "..\..\mock\dilute_files\SX614_SX686_160308_4_J_Ham.txt"


# noinspection SpellCheckingInspection
class HamiltonDriverFileTests(unittest.TestCase):

    def setUp(self):
        abspath = os.path.abspath(inspect.stack()[0][1])
        currentdir = os.path.dirname(abspath)
        driverfilepath = os.path.join(currentdir, DRIVER_FILE_RELATIVE_PATH)
        with open(driverfilepath, 'r') as driverfile:
            filecontents = driverfile.read()
        self.file_reader = FileReader(filecontents)
        self.column_ref = ColumnRef()

    def test_number_columns(self):
        self.assertEqual(self.file_reader.number_columns(), 7,
                         "Number columns in file is not right")

    def test_number_rows(self):
        numberrows = self.file_reader.number_rows()
        self.assertEqual(numberrows, 29,
                         "Number rows in file is not right, expected: {}, result {}"
                         .format(29, numberrows))

    def test_reference_by_indexing_1st_corner(self):
        self.assertEqual(self.file_reader.matrix[0][0], "SX614_T7.v1",
                         "Contents in first corner not correct")

    def test_reference_by_indexing_2nd_corner(self):
        self.assertEqual(self.file_reader.matrix[0][-1], "END1",
                         "Contents in second corner not correct")

    def test_reference_by_indexing_3rd_corner(self):
        self.assertEqual(self.file_reader.matrix[-1][-1], "END1",
                         "Contents in third corner not correct")

    def test_reference_by_indexing_4th_corner(self):
        contents = self.file_reader.matrix[-1][0]
        self.assertEqual(contents, "SX686_12-130.v2",
                         "Contents in forth corner not correct, outcome {}, expected {}"
                         .format(contents, "SX686_12-130.v2"))

    def test_reference_by_indexing_middle(self):
        contents = self.file_reader.matrix[5][1]
        self.assertEqual(int(contents), 55,
                         "Contents at row 5, column 2 is not correct, outcome {}, expected {}"
                         .format(contents, 55))

    def test_reference_by_name_1st_corner(self):
        contents = self.file_reader.dict_matrix["SX614_T7.v1"][self.column_ref.source_well_pos]
        self.assertEqual(int(contents), 50,
                         "Source plate pos not right for 1st sample, outcome {}, expected {}"
                         .format(contents, 50))

    def test_reference_by_name_2nd_corner(self):
        contents = self.file_reader.dict_matrix["SX614_T7.v1"][self.column_ref.target_plate_pos]
        self.assertEqual(contents, "END1",
                         "Target plate pos not right for 1st sample")

    def test_reference_by_name_3rd_corner(self):
        contents = self.file_reader.dict_matrix["SX686_12-130.v2"][self.column_ref.target_plate_pos]
        self.assertEqual(contents, "END1",
                         "Target plate pos not right for last sample")

    def test_reference_by_name_4th_corner(self):
        contents = self.file_reader.dict_matrix["SX686_12-130.v2"][self.column_ref.source_well_pos]
        self.assertEqual(int(contents), 8,
                         "Target plate pos not right for last sample")

    def test_reference_sample(self):
        contents = self.file_reader.dict_matrix["SX614_T11.v1"][self.column_ref.sample]
        self.assertEqual(contents, "SX614_T11.v1",
                         "Sample column reference not working")

    def test_reference_source_well_pos(self):
        contents = self.file_reader.dict_matrix["SX614_T11.v1"][self.column_ref.source_well_pos]
        self.assertEqual(int(contents), 67,
                         "Source well pos reference not right")

    def test_reference_source_plate_pos(self):
        contents = self.file_reader.dict_matrix["SX614_T11.v1"][self.column_ref.source_plate_pos]
        self.assertEqual(contents, "DNA1",
                         "Source plate pos reference not right")

    def test_reference_volume_sample(self):
        contents = self.file_reader.dict_matrix["SX614_T11.v1"][self.column_ref.volume_sample]
        self.assertEqual(float(contents), 4.3,
                         "Sample volume reference not right")

    def test_reference_volume_buffer(self):
        contents = self.file_reader.dict_matrix["SX614_T11.v1"][self.column_ref.volume_buffer]
        self.assertEqual(float(contents), 4.5,
                         "Buffer volume reference not right")

    def test_reference_target_well_pos(self):
        contents = self.file_reader.dict_matrix["SX614_T11.v1"][self.column_ref.target_well_pos]
        self.assertEqual(int(contents), 16,
                         "Target well pos reference not right")

    def test_reference_target_plate_pos(self):
        contents = self.file_reader.dict_matrix["SX614_T11.v1"][self.column_ref.target_plate_pos]
        self.assertEqual(contents, "END1",
                         "Target plate pos reference not right")

if __name__ == "__main__":
    unittest.main()
