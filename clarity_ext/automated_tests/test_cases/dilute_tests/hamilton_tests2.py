# Unit test the output of the dilution script, generating driver file for Hamilton
# Using the utility in dilute_filer_reader
# Hamilton tests 2 utilize a process which have a target plate

import unittest
import os
import inspect
from ...utility.dilute_filer_reader.hamilton_driver_file_reader import HamiltonReader as FileReader
from ...utility.dilute_filer_reader.hamilton_driver_file_reader import HamiltonColumnReference as ColumnRef
from ....dilute_epp import perform_dilution

TEST_PROCESS_URI = "https://lims-staging.snpseq.medsci.uu.se/api/v2/processes/24-3624"
SAMPLE1 = "EdvardProv50"
SAMPLE2 = "EdvardProv51"
SAMPLE3 = "EdvardProv52"
SAMPLE4 = "EdvardProv53"


class HamiltonTests(unittest.TestCase):

    def setUp(self):
        driver_file_contents = perform_dilution.create_driver_file(TEST_PROCESS_URI, None)
        self.hamilton_reader = FileReader(driver_file_contents)
        self.column_ref = ColumnRef()

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
                         "Number rows not correct")

    def test_volume_sample(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE1][self.column_ref.volume_sample]
        self.assertEqual(float(contents), 14.93,
                         "Volume from sample value is not right\n{}"
                         .format(self.hamilton_reader.dict_matrix))

    def test_volume_buffer(self):
        contents = self.hamilton_reader.dict_matrix[SAMPLE1][self.column_ref.volume_buffer]
        self.assertEqual(float(contents), 5.07,
                         "Volume from buffer value is not right\n{}"
                         .format(self.hamilton_reader.dict_matrix))

if __name__ == "__main__":
    unittest.main()