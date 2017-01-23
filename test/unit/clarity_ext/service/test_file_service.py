import unittest
from mock import MagicMock
from clarity_ext.domain.artifact import Artifact
import os
from clarity_ext.service.file_service import UploadFileService


class TestUploadFileService(unittest.TestCase):

    def test_run_driver_file_service(self):
        artifact_service = MagicMock()
        shared_files = [fake_artifact(
            "art1", "Handle Name 1"), fake_artifact("art2", "Handle Name 2")]
        artifact_service.shared_files = MagicMock(return_value=shared_files)
        os_service = MagicMock()
        upload_file_service = UploadFileService(
            os_service=os_service, artifact_service=artifact_service)
        upload_file_service.upload("Handle Name 2", "file2.txt", "content")
        os_service.attach_file_for_epp.assert_called_with(".{sep}file2.txt".format(sep=os.sep),
                                                          shared_files[1])


def fake_artifact(artifact_id, name):
    artifact = Artifact()
    artifact.name = name
    artifact.id = artifact_id
    return artifact
