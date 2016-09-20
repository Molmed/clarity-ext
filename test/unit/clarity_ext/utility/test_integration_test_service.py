import unittest
from test.integration.integration_test_service import IntegrationTest
from mock import MagicMock
from mock import Mock
from test.unit.clarity_ext import helpers
from test.unit.clarity_ext.helpers import fake_analyte
from clarity_ext.domain import Analyte, Artifact


class TestIntegrationTestService(unittest.TestCase):

    def test_returning_pid(self):
        test = IntegrationTest(pid="pid1")
        self.assertEqual(test.pid(), "pid1")

        run_args = {"pid": "pid1"}
        test = IntegrationTest(run_argument_dict=run_args)
        self.assertEqual(test.pid(), "pid1")

    def test_run_prepare(self):
        artifact_set = [(fake_analyte("cont1", "art1", "sample1", "art1", "A:1", True, volume=1),
                         fake_analyte("cont1", "art2", "sample1", "art2", "A:1", False)),
                        (fake_analyte("cont1", "art3", "sample2", "art3", "B:1", True, volume=0),
                         fake_analyte("cont1", "art4", "sample2", "art4", "B:1", False))]

        def pre_test_artifact_set():
            return artifact_set

        update_matrix = [("art1", "Current sample volume (ul)", 50),
                         ("art3", "Current sample volume (ul)", 50)]

        artifact_service = helpers.mock_artifact_service(pre_test_artifact_set)
        test = IntegrationTest(pid="pid1", update_matrix=update_matrix)
        self.assertIsNotNone(test.preparer)

        artifact_service.update_artifacts = Mock()
        test.preparer.prepare(artifact_service)

        art1 = pre_test_artifact_set()[0][0]
        art3 = pre_test_artifact_set()[1][0]
        expected_updated_queue = [art1, art3]

        artifact_service.update_artifacts.assert_called_with(expected_updated_queue)
        self.assertEqual(art1.volume, 50)
        self.assertEqual(art3.volume, 50)
