import unittest
from mock import MagicMock
from clarity_ext.driverfile import DriverFileService, ResponseFileService
from clarity_ext.domain.artifact import Artifact
import logging


class TestGeneralFileService(unittest.TestCase):

    def test_run_driver_file_service(self):
        shared_files = [fake_artifact("art1", "file1.txt"), fake_artifact("art2", "file2.txt")]
        context = fake_context(step_id="step1", shared_files=shared_files, response=[])
        extension = fake_extension("file1.txt", context)
        os_service = MagicMock()
        logger = logging.getLogger(__name__)
        file_svc = DriverFileService.create_file_service(extension, extension.shared_file(), logger, os_service)
        file_svc.execute()
        os_service.copy_file.assert_called_with(".\\file1.txt", ".\\uploaded\\art1_file1.txt")

    def test_run_response_file_service(self):
        context = fake_context(step_id="step1", shared_files=None, response=[])
        extension = fake_extension("response.txt", context)
        os_service = MagicMock()
        logger = logging.getLogger(__name__)
        file_svc = ResponseFileService.create_file_service(extension, logger, os_service)
        file_svc.execute()
        os_service.copy_file.assert_called_with(".\\response.txt", ".\\uploaded\\step1_response.txt")


def fake_artifact(id, name):
    artifact = Artifact()
    artifact.name = name
    artifact.id = id
    return artifact


def fake_context(step_id, shared_files, response):
    context = MagicMock()
    session = MagicMock()
    session.current_step_id = step_id
    context.shared_files = shared_files
    context.response = response
    context.session = session
    return context


def fake_extension(file_name=None, context=None):
    extension = MagicMock()
    extension.context = context
    extension.filename.return_value = file_name
    extension.shared_file.return_value = file_name
    extension.newline.return_value = '\n'
    extension.execute.return_value = []
    extension.content.return_value = "content"
    return extension
