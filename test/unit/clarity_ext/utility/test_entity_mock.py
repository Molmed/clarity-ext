import unittest

from test.unit.clarity_ext.mock.dilution_mock import DilutionMock1


class EntityMockTests(unittest.TestCase):

    def setUp(self):
        self.mock = DilutionMock1()
        self.input = self.mock.process.all_inputs()[0]
        self.output = self.mock.process.all_outputs()[0]

    def tearDown(self):
        self.mock.clean_up()

    def test_process_id(self):
        self.assertEqual(self.mock.process.id, "123")

    def test_udf_concentration(self):
        concentration = self.input.udf["Concentration"]
        self.assertEqual(concentration, 123)

    def test_artifact_name(self):
        name = self.input.name
        self.assertEqual(name, "username3")

    def test_container_position(self):
        position = self.input.location[1]
        self.assertEqual(position, "B:7")

    def test_container_id(self):
        container = self.input.location[0]
        self.assertEqual(container.id, "container2")

    def test_input_type(self):
        type = self.input.type
        self.assertEqual(type, "Analyte")

    def test_target_concentration(self):
        concentration = self.output.udf["Target Concentration"]
        self.assertEqual(concentration, 100)

    def test_target_volume(self):
        volume = self.output.udf["Target Volume"]
        self.assertEqual(volume, 20)


if __name__ == "__main__":
    unittest.main()
