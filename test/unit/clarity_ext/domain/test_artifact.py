import unittest
from clarity_ext.domain.artifact import Artifact
from test.unit.clarity_ext.helpers import fake_analyte, fake_result_file
from test.unit.clarity_ext.helpers import fake_shared_result_file
from test.unit.clarity_ext.helpers import fake_container
from mock import MagicMock
from clarity_ext.unit_conversion import UnitConversion
from clarity_ext.domain.result_file import ResultFile
from clarity_ext.domain.shared_result_file import SharedResultFile
from test.unit.clarity_ext.helpers import mock_artifact_resource
from test.unit.clarity_ext.helpers import mock_container_repo
from clarity_ext.mappers.clarity_mapper import ClarityMapper
from .shared import DomainObjectTestCase

# class TestArtifactDomainObjectProperties(DomainObjectTestCase):
#         self.basic_domain_properties_check(logger1, logger2)


class TestArtifact(DomainObjectTestCase):
    def create_instance(self):
        return Artifact()

    def test_two_identical_artifacts_equal(self):
        """A copy of an artifact should be equal to another"""
        artifacts = [ResultFile(api_resource=None, is_input=False),
                     ResultFile(api_resource=None, is_input=False)]
        for artifact in artifacts:
            artifact.any_patch = "13370"

        self.assertEqual(artifacts[0], artifacts[1])

    def test_artifact_should_not_equal_non_artifact(self):
        artifact = ResultFile(api_resource=None, is_input=False)
        self.assertNotEqual(artifact, "string")

    def test_equality_including_mutual_references(self):
        """
        Analyte referring to a well, that is referring back to the analyte
        """

        def two_identical_analytes():
            return [
                fake_analyte("cont-id1", "art-id1", "sample1", "art-name1", "D:5", True,
                             concentration=100, volume=20),
                fake_analyte("cont-id1", "art-id1", "sample1", "art-name1", "D:5", True,
                             concentration=100, volume=20)
            ]

        analytes = two_identical_analytes()
        self.assertEqual(analytes[0], analytes[1])

    def test_inequality_including_mutual_references(self):
        """
        Analyte referring to a well, that is referring back to the analyte
        """

        def two_identical_analytes():
            return [
                fake_analyte("cont-id1", "art-id1", "sample1", "art-name1", "D:5", True,
                             concentration=100, volume=20),
                fake_analyte("cont-id1", "art-id2", "sample1", "art-name2", "D:6", True,
                             concentration=100, volume=20)
            ]

        analytes = two_identical_analytes()
        self.assertNotEqual(analytes[0], analytes[1])

    def test_unit_conversion(self):
        artifact = fake_result_file("id", "name", "container-id", "A:1", True, {"Test": 10})
        units = UnitConversion()
        artifact.udf_test = units.convert(1234, units.PICO, units.NANO)
        self.assertEqual(artifact.udf_test, 1.234)

    def test_create_from_rest_analyte(self):
        udfs = {"Some udf": 10}
        api_resource = MagicMock()
        api_resource.udf = udfs
        api_resource.location = [None, "B:2"]
        sample = MagicMock()
        sample.id = "sample1"
        api_resource.samples = [sample]
        api_resource.id = "art1"
        api_resource.name = "sample1"
        container_repo = MagicMock()
        container = fake_container("cont1")
        container_repo.get_container.return_value = container

        clarity_mapper = ClarityMapper()
        analyte = clarity_mapper.analyte_create_object(
            api_resource, is_input=True, container_repo=container_repo, process_type=MagicMock())

        expected_analyte = fake_analyte(container_id="cont1", artifact_id="art1", sample_ids=["sample1"],
                                        analyte_name="sample1", well_key="B:2", is_input=True,
                                        requested_volume=10, udfs=udfs)
        self.assertEqual(expected_analyte.udf_some_udf,
                         analyte.udf_some_udf)
        self.assertEqual(expected_analyte.id, analyte.id)
        self.assertEqual(expected_analyte.name, analyte.name)
        self.assertEqual(expected_analyte.well.__repr__(),
                         analyte.well.__repr__())
        self.assertEqual(expected_analyte.well.artifact.name,
                         analyte.well.artifact.name)

    def _create_process_type_mock(self, per_input_artifact_type="ResultFile",
                                  output_generation_type="PerInput",
                                  field_definitions=None):
        """The process type is required in some cases for expanding upon UDFs"""
        process_type = MagicMock()
        per_input_process_output = MagicMock()
        per_input_process_output.output_generation_type = output_generation_type
        per_input_process_output.artifact_type = per_input_artifact_type
        per_input_process_output.field_definitions = field_definitions
        process_type.process_outputs = [per_input_process_output]
        return process_type

    def test_create_from_rest_result_file(self):
        api_resource = mock_artifact_resource(
            resouce_id="art1", sample_name="sample1", well_position="B:2")
        api_resource.udf = {}
        container_repo = mock_container_repo(container_id="cont1")

        clarity_mapper = ClarityMapper()
        result_file = clarity_mapper.result_file_create_object(
            api_resource, is_input=False, container_repo=container_repo,
            process_type=self._create_process_type_mock(field_definitions=[]))

        expected_result_file = fake_result_file(
            artifact_id="art1", container_id="cont1", name="sample1", well_key="B:2",
            is_input=False, concentration_ngul=10)

        self.assertEqual(expected_result_file.id, result_file.id)
        self.assertEqual(expected_result_file.name, result_file.name)
        self.assertEqual(result_file.well.artifact.name,
                         "sample1")

    def test_create_result_file_with_no_container(self):
        udfs = dict()
        api_resource = mock_artifact_resource(
            resouce_id="art1", sample_name="sample1")
        api_resource.udf = udfs
        container_repo = mock_container_repo(container_id=None)

        clarity_mapper = ClarityMapper()
        result_file = clarity_mapper.result_file_create_object(
            api_resource, is_input=False,
            container_repo=container_repo, process_type=self._create_process_type_mock(field_definitions=["UDF1"]))

        expected_result_file = fake_result_file(
            artifact_id="art1", container_id=None, name="sample1", well_key="B:2",
            is_input=False, udfs=udfs)

        self.assertEqual(expected_result_file.id, result_file.id)
        self.assertEqual(expected_result_file.name, result_file.name)
        self.assertEqual(result_file.well.__repr__(), "None")

    def test_create_from_rest_shared_result_file(self):
        api_resource = MagicMock()
        api_resource.id = "id1"
        api_resource.name = "name1"
        api_resource.udf = {"Has errors": 1}
        process_type = self._create_process_type_mock(output_generation_type="PerAllInputs",
                                                      field_definitions=["Has errors"])
        shared_result_file = SharedResultFile.create_from_rest_resource(
            resource=api_resource,
            process_type=process_type)
        expected_shared_result_file = fake_shared_result_file("id1", "name1")
        self.assertEqual(expected_shared_result_file.id, shared_result_file.id)
        self.assertEqual(expected_shared_result_file.name,
                         shared_result_file.name)
        self.assertEqual(True, shared_result_file.udf_has_errors)
