import unittest
from clarity_ext import utils
from clarity_ext.service import ArtifactService
from clarity_ext.repository import StepRepository
from clarity_ext import ClaritySession
from test.integration import config
from clarity_ext.context import ExtensionContext


class TestArtifactService(unittest.TestCase):
    """
    Tests various aspects of the artifact service, requiring a running Clarity system and steps in
    certain conditions.
    """

    def test_can_access_patterned_flow_cell_output(self):
        """
        Can access an eight lane patterned flow cell as the output container and access all of its artifacts.

        Condition: The step must have only one output container, which is a Patterned Flow Cell
        """
        item = config.get_by_name("has_one_output_of_type_patterned_flow_cell")
        context = ExtensionContext.create(item.pid)
        containers = context.artifact_service.all_output_containers()
        self.assertEqual(1, len(containers))
        container = containers[0]
        count = 0
        for item in container.enumerate_wells():
            count += 1
            self.assertIsNotNone(item.artifact.input)
            self.assertIsNotNone(item.artifact.input.parent_process)
        self.assertEqual(8, count)

    def test_can_get_parent_input_artifacts(self):
        """
        The step describing a Patterned Flow Cell should have 8 lanes with pooled samples in them.

        The test ensures that if we enumerate those, we can get to the parent input artifacts and
        look at information hanging on them.
        """
        item = config.get_by_name("has_one_output_of_type_patterned_flow_cell")
        context = ExtensionContext.create(item.pid)
        all_samples = list()
        for output_container in context.artifact_service.all_output_containers():
            for lane in output_container.enumerate_wells():
                for sample in lane.artifact.samples:
                    all_samples.append(sample)
        unique_samples = list(utils.unique(
            all_samples, lambda sample: sample.id))
        self.assertTrue(len(unique_samples) >= 2)
        for sample in unique_samples:
            parent = utils.single(context.artifact_service.get_parent_input_artifact(sample))
            self.assertEqual(sample.name, parent.name)
