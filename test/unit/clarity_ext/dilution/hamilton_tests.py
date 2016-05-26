import unittest
from clarity_ext.utility.hamilton_driver_file_reader import HamiltonColumnReference
from clarity_ext.utility.hamilton_driver_file_reader import HamiltonReader
from clarity_ext_scripts.dilution.create_hamilton_dilution import Extension
from test.unit.clarity_ext.mock.dilution_mock import DilutionMock1
import textwrap

TEST_PROCESS_ID = "24-3643"
SAMPLE1 = "username1"
SAMPLE2 = "username2"
SAMPLE3 = "username3"
SAMPLE4 = "username4"


class HamiltonTests(unittest.TestCase):
    """
    Unit test the output of the dilution script, generating a driver file for Hamilton.
    Uses the utility in dilute_filer_reader.
    Utilizes a process that has a target plate.
    """

    def setUp(self):
        self.mock = DilutionMock1()
        extension = Extension(self.mock.context)
        driver_file_contents = "\n".join([row_ for row_ in extension.content()])
        self.column_ref = HamiltonColumnReference()
        driver_file_contents = """\
                                  EdvardProv60	36	DNA1	14.9	5.1	34	END1
                                  EdvardProv61	33	DNA2	14.9	5.1	17	END2
                                  EdvardProv62	50	DNA2	14.9	5.1	44	END1
                                  EdvardProv63	93	DNA2	14.9	5.1	69	END2"""
        driver_file_contents = textwrap.dedent(driver_file_contents)
        self.hamilton_reader = HamiltonReader(driver_file_contents)

    def tearDown(self):
        self.mock.clean_up()

    def test_import_hamilton_reader(self):
        self.assertIsNotNone(self.hamilton_reader,
                             "Hamilton reader is not initialized")

    def test_number_columns(self):
        number_cols = len(self.hamilton_reader.matrix[0])
        self.assertEqual(number_cols, 7,
                         "Number columns not correct")

    def test_number_rows(self):
        number_rows = len(self.hamilton_reader.matrix)
        self.assertEqual(number_rows, 4,
                         "Number rows not correct\n{}"
                         .format(self.hamilton_reader.matrix))

    def test_volume_sample(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE1][self.column_ref.volume_sample]
        self.assertEqual(float(contents), 14.9,
                         "Volume from sample value is not right\n{}"
                         .format(self.hamilton_reader.dict_matrix))

    def test_volume_buffer(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE1][self.column_ref.volume_buffer]
        self.assertEqual(float(contents), 5.1,
                         "Volume from buffer value is not right\n{}"
                         .format(self.hamilton_reader.dict_matrix))

    def test_target_well_position(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE4][self.column_ref.target_well_pos]
        self.assertEqual(int(contents), 69,
                         "Target well position is not right")

    def test_target_plate_position(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE1][self.column_ref.target_plate_pos]
        self.assertEqual(contents, "END1",
                         "Target plate position is not right")

    def test_target_plate_position2(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE4][self.column_ref.target_plate_pos]
        self.assertEqual(contents, "END2",
                         "Target plate position is not right")

    def test_source_well_position(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE3][self.column_ref.source_well_pos]
        self.assertEqual(int(contents), 50,
                         "Source well position is not right, sample = {}, contents = {}\n{}"
                         .format(SAMPLE3, contents, self.hamilton_reader.dict_matrix))

    def test_source_well_position2(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE1][self.column_ref.source_well_pos]
        self.assertEqual(int(contents), 36,
                         "Source well position is not right, sample = {}, contents = {}\n{}"
                         .format(SAMPLE1, contents, self.hamilton_reader.dict_matrix))

    def test_source_plate_position(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE1][self.column_ref.source_plate_pos]
        self.assertEqual(contents, "DNA1",
                         "Source plate position is not right, sample = {}, contents = {}\n{}"
                         .format(SAMPLE1, contents, self.hamilton_reader.dict_matrix))

    def test_source_plate_position2(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE2][self.column_ref.source_plate_pos]
        self.assertEqual(contents, "DNA2",
                         "Source plate position is not right, sample = {}, contents = {}\n{}"
                         .format(SAMPLE2, contents, self.hamilton_reader.dict_matrix))

    def test_ordering1(self):
        contents = self.hamilton_reader.matrix[0][self.column_ref.sample]
        self.assertEqual(contents, SAMPLE1)

    def test_ordering2(self):
        contents = self.hamilton_reader.matrix[1][self.column_ref.sample]
        self.assertEqual(contents, SAMPLE2)

    def test_ordering3(self):
        contents = self.hamilton_reader.matrix[2][self.column_ref.sample]
        self.assertEqual(contents, SAMPLE3)

    def test_ordering4(self):
        contents = self.hamilton_reader.matrix[3][self.column_ref.sample]
        self.assertEqual(contents, SAMPLE4)


if __name__ == "__main__":
    unittest.main()
