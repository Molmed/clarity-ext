import re
import os
import shutil
import logging
from lxml import objectify


class FileService:
    """
    Handles downloading files from the LIMS and keeping local copies of them as
    well as cleaning up after a script as run
    """

    def __init__(self, artifact_service, file_repo, should_cache):
        """
        :param artifact_service: An artifact service instance.
        :param should_cache: Set to True if files should be cached in .cache, mainly
        for faster integration tests.
        """
        self._local_shared_files = []
        self.artifact_service = artifact_service
        self.logger = logging.getLogger(__name__)
        self.should_cache = should_cache
        self.file_repo = file_repo

    def parse_xml(self, f):
        """
        Parses the file like object as XML and returns an object that provides simple access to
        the leaves, such as `parent.child.grandchild`
        """
        with f:
            tree = objectify.parse(f)
            return tree.getroot()

    def local_shared_file(self, file_name, mode='r'):
        """
        Downloads the local shared file and returns an open file-like object.

        If the file already exists, it will not be downloaded again.

        Details:
        The downloaded files will be removed when the context is cleaned up. This ensures
        that the LIMS will not upload them by accident
        """

        # TODO: Mockable, file system repo

        # Ensure that the user is only sending in a "name" (alphanumerical or spaces)
        # File paths are not allowed
        if not re.match(r"[\w ]+", file_name):
            raise ValueError(
                "File name can only contain alphanumeric characters, underscores and spaces")
        local_file_name = file_name.replace(" ", "_")
        local_path = os.path.abspath(local_file_name)
        local_path = os.path.abspath(local_path)
        cache_directory = os.path.abspath(".cache")
        cache_path = os.path.join(cache_directory, local_file_name)

        if self.should_cache and os.path.exists(cache_path):
            self.logger.info(
                "Fetching cached artifact from '{}'".format(cache_path))
            shutil.copy(cache_path, ".")
        else:
            if not os.path.exists(local_path):
                shared_files = self.artifact_service.shared_files()
                by_name = [shared_file for shared_file in shared_files
                           if shared_file.name == file_name]
                if len(by_name) != 1:
                    files = ", ".join(map(lambda x: x.name, shared_files))
                    raise ValueError("Expected 1 shared file, got {}.\nFile: '{}'\nFiles: {}".format(
                        len(by_name), file_name, files))
                artifact = by_name[0]
                file = artifact.api_resource.files[0]  # TODO: Hide this logic
                self.logger.info("Downloading file {} (artifact={} '{}')"
                                 .format(file.id, artifact.id, artifact.name))
                self.file_repo.copy_remote_file(file.id, local_path)
                self.logger.info(
                    "Download completed, path='{}'".format(local_path))

                if self.should_cache:
                    if not os.path.exists(cache_directory):
                        os.mkdir(cache_directory)
                    self.logger.info("Copying artifact to cache directory, {}=>{}".format(
                        local_path, cache_directory))
                    shutil.copy(local_path, cache_directory)

        # Add to this list for cleanup:
        if local_path not in self._local_shared_files:
            self._local_shared_files.append(local_path)

        return self.file_repo.open_local_file(local_path, mode)

    def cleanup(self):
        for path in self._local_shared_files:
            if os.path.exists(path):
                self.logger.info("Local shared file '{}' will be removed to ensure "
                                 "that it won't be uploaded again".format(path))
                # TODO: Handle exception
                os.remove(path)