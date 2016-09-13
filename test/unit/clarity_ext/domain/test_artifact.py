import unittest
from clarity_ext.domain import Artifact
from test.unit.clarity_ext.helpers import fake_analyte


class TestArtifact(unittest.TestCase):

    def test_two_identical_artifacts_equal(self):
        """A copy of an artifact should be equal to another"""
        artifacts = [Artifact(), Artifact()]
        for artifact in artifacts:
            artifact.generation_type = Artifact.OUTPUT_TYPE_RESULT_FILE
            artifact.is_input = False
            artifact.any_patch = "13370"

        self.assertEqual(artifacts[0], artifacts[1])

    def test_artifact_should_not_equal_non_artifact(self):
        artifact = Artifact()
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
