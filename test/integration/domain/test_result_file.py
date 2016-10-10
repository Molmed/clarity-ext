import unittest
from clarity_ext.domain import Container, ResultFile, SharedResultFile
from clarity_ext.context import ExtensionContext
import os


class TestIntegrationAnalyteRepository(unittest.TestCase):
    """
    This is a temporary integration test, which requires the Clarity LIMS to
    be set up in a certain way.
    """

    def test_can_fetch_containers_from_result_files(self):
        """
        A temporary test that validates that one can fetch containers

        Required setup:
          - The step has been set up so that there are output result files (not analytes)
            which containers need to be accessed. Fetching all analytes will not
            return output analytes in this case.
        """
        context = ExtensionContext.create("24-3144")

        wells = [x for x in context.output_container.list_wells(
            Container.RIGHT_FIRST)]
        self.assertIsNotNone(wells[0].artifact)

    def test_can_fetch_shared_files(self):
        """Can fetch a set of shared files from a step"""
        context = ExtensionContext.create("24-3144")
        expected = set(["92-5245", "92-5246", "92-5243", "92-5244"])
        actual = set(f.id for f in context.shared_files)
        self.assertEqual(expected, actual)

    def test_can_download_shared_file(self):
        """Can download a single shared file, view it locally and then clean it up"""
        context = ExtensionContext.create("24-3144")
        f = context.local_shared_file("Sample List")
        self.assertNotEqual(0, len(f.name))
        self.assertTrue(os.path.exists(f.name))
        context.cleanup()
        self.assertFalse(os.path.exists(f.name))

    def test_can_fetch_all_output_files(self):
        """Can fetch all output files in a step"""
        context = ExtensionContext.create("24-3144")
        actual = set(f.id for f in context.output_result_files)
        expected = set(['92-5244', '92-5245', '92-5246',
                        '92-5241', '92-5242', '92-5243'])
        self.assertEqual(expected, actual)

    def test_can_fetch_single_output_file(self):
        context = ExtensionContext.create("24-3144")
        result = context.output_result_file_by_id("92-5244")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SharedResultFile)

    @unittest.skip("Step removed")
    def test_can_read_xml(self):
        """Can parse an xml file directly form the context"""
        context = ExtensionContext.create("24-7880")
        xml = context.local_shared_file(
            "Result XML File (required)", is_xml=True)
        self.assertFalse(0, len(xml.FileInformation.Assay))
        context.cleanup()

