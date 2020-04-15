from __future__ import print_function
import re
import os
import shutil
import logging
from zipfile import ZipFile
from lxml import objectify
from clarity_ext import utils
import requests


class FileService:
    """
    Handles downloading and uploading files from/to the LIMS and keeping local copies of them as
    well as cleaning up after a script as run
    """
    CONTEXT_FILES_ROOT = "./context_files"
    SERVER_FILE_NAME_PATTERN = r"(\d+-\d+)_(.+)"

    FILE_PREFIX_NONE = 0
    FILE_PREFIX_ARTIFACT_ID = 1
    FILE_PREFIX_RUNNING_NUMBER = 2

    def __init__(self, artifact_service, file_repo, should_cache, os_service, uploaded_to_stdout=False,
                 disable_commits=False, session=None):
        """
        :param artifact_service: An artifact service instance.
        :param should_cache: Set to True if files should be cached in .cache, mainly
        for faster integration tests.
        :param uploaded_to_stdout: Set to True to output uploaded files to stdout
        :param disable_commits: Set to True to not upload files when committing. Used for testing.
        """
        self._local_shared_files = []
        self.artifact_service = artifact_service
        self.logger = logging.getLogger(__name__)
        self.should_cache = should_cache
        self.file_repo = file_repo
        self.os_service = os_service
        self.artifactid_by_filename = dict() # key=filename, value=artifact-id

        self.upload_queue_path = os.path.join(self.CONTEXT_FILES_ROOT, "upload_queue")
        self.uploaded_path = os.path.join(self.CONTEXT_FILES_ROOT, "uploaded")
        self.temp_path = os.path.join(self.CONTEXT_FILES_ROOT, "temp")
        self.downloaded_path = os.path.join(self.CONTEXT_FILES_ROOT, "downloaded")
        self.session = session
        self.disable_commits = disable_commits
        self.uploaded_to_stdout = uploaded_to_stdout

        self.local_shared_file_provider = LocalSharedFileProvider(
            self, self.file_repo, self.artifact_service, self.downloaded_path,
            self.os_service, self.should_cache, self.logger)

        # Remove all files before starting
        if self.os_service.exists(self.CONTEXT_FILES_ROOT):
            self.os_service.rmtree(self.CONTEXT_FILES_ROOT)
        self.os_service.makedirs(self.upload_queue_path)
        self.os_service.makedirs(self.uploaded_path)
        self.os_service.makedirs(self.temp_path)
        self.os_service.makedirs(self.downloaded_path)

    def parse_xml(self, f):
        """
        Parses the file like object as XML and returns an object that provides simple access to
        the leaves, such as `parent.child.grandchild`
        """
        with f:
            tree = objectify.parse(f)
            return tree.getroot()

    def parse_csv(self, f):
        with f:
            return Csv(f)

    def local_shared_file(self, file_handle, mode='r', extension="", modify_attached=False, file_name_contains=None):
        return self.local_shared_file_provider.\
            search_existing(file_handle, mode=mode,
                            extension=extension,
                            modify_attached=modify_attached,
                            file_name_contains=file_name_contains)

    def local_shared_file_search_or_create(self, file_handle, mode='r', extension="",
                                           modify_attached=False, filename=None):
        return self.local_shared_file_provider.\
            search_or_create(file_handle, mode=mode,
                             extension=extension,
                             modify_attached=modify_attached,
                             filename=filename)

    def queue(self, downloaded_path, artifact, file_prefix=FILE_PREFIX_NONE):
        file_name = os.path.basename(downloaded_path)
        self.artifactid_by_filename[file_name] = artifact.id
        if file_prefix == FileService.FILE_PREFIX_ARTIFACT_ID and not file_name.startswith(artifact.id):
            file_name = "{}_{}".format(artifact.id, file_name)
        elif file_prefix == FileService.FILE_PREFIX_NONE:
            if file_name.startswith(artifact.id):
                file_name = file_name.split("_", 1)[1]
        elif file_prefix == FileService.FILE_PREFIX_RUNNING_NUMBER:
            # Prefix with the index of the shared file
            artifact_ids = sorted([tuple(map(int, shared_file.id.split("-")) + [shared_file.id])
                                   for shared_file in self.artifact_service.shared_files()])
            running_numbers = {artifact_id[2]: ix + 1 for ix, artifact_id in enumerate(artifact_ids)}
            file_name = "{}_{}".format(running_numbers[artifact.id], file_name)

        upload_dir = os.path.join(self.upload_queue_path, artifact.id)
        self.os_service.makedirs(upload_dir)
        upload_path = os.path.join(upload_dir, file_name)
        self.os_service.copy_file(downloaded_path, upload_path)
        return upload_path

    def remove_files(self, file_handle, disabled, exclude_list=None):
        """Removes all files for the particular file handle.

        Note: The files are not actually removed from the server, only the link to the step.
        """
        artifacts = sorted([shared_file for shared_file in self.artifact_service.shared_files()
                            if shared_file.name == file_handle], key=lambda f: f.id)
        if exclude_list is not None:
            artifacts = [a for a in artifacts for exclude_name in exclude_list
                         if len(a.files) > 0 and exclude_name not in a.files[0].original_location]
        for artifact in artifacts:
            artifact.remove_files(disabled, self.logger, self.session)

    def upload_files(self, file_handle, files, stdout_max_lines=50, zip_files=False):
        """
        Uploads one or more files to the particular file handle. The file handle must support
        at least the same number of files.

        # TODO: Check what happens if there are already n files uploaded but the user uploads n-1.
                It might lead to inconsistency and there should at least be a warning

        :param file_handle: The name that this should be attached to in Clarity, e.g. "Step Log"
        :param files: A list of tuples, (file_name, str)
        """
        artifacts = sorted([shared_file for shared_file in self.artifact_service.shared_files()
                            if shared_file.name == file_handle], key=lambda f: f.id)

        if zip_files:
            # We are only interested in the first file handle artifact when zipping:
            artifact = artifacts[0]

            # Zipped files should be prefixed with the artifact ID:
            files = [("{}_{}".format(artifact.id, file_name), content) for file_name, content in files]

            zip_file_name = "sample_sheet.zip"
            self.compress_files(zip_file_name, files)
            self.queue(os.path.join(self.temp_path, zip_file_name), artifact,
                       FileService.FILE_PREFIX_ARTIFACT_ID)
        else:
            if len(files) > len(artifacts):
                raise SharedFileNotFound("Trying to upload {} files to '{}', but only {} are supported".format(
                    len(files), file_handle, len(artifacts)))

            for artifact, file_and_name in zip(artifacts, files):
                instance_name, content = file_and_name
                self._upload_single(artifact, file_handle, instance_name, content, FileService.FILE_PREFIX_ARTIFACT_ID)

    def compress_files(self, out_name, files):
        """
        :param out_name: The name of the zipped file
        :param files: A list of (file_name, content) tuples
        :return: None
        """
        files_to_zip = list()
        for instance_name, content in files:
            local_path = self.save_locally(content, instance_name)
            files_to_zip.append(os.path.basename(local_path))

        old_dir = os.getcwd()
        try:
            os.chdir(self.temp_path)
            with ZipFile(out_name, 'w') as zipfile:
                for path in files_to_zip:
                    zipfile.write(path)
        finally:
            os.chdir(old_dir)

    def upload(self, file_handle, instance_name, content, file_prefix):
        """
        :param file_handle: The handle of the file in the Clarity UI
        :param instance_name: The name of this particular file
        :param content: The content of the file. Should be a string.
        :param file_prefix: Any of the FILE_PREFIX_* values
        """
        artifacts = sorted([shared_file for shared_file in self.artifact_service.shared_files()
                     if shared_file.name == file_handle], key=lambda x: x.id)
        self._upload_single(artifacts[0], file_handle, instance_name, content, file_prefix)

    def _upload_single(self, artifact, file_handle, instance_name, content, file_prefix):
        """Queues the file for update. Call commit to send to the server."""

        local_path = self.save_locally(content, instance_name)
        self.logger.info("Queuing file '{}' for upload to the server, file handle '{}'".format(local_path, file_handle))
        self.queue(local_path, artifact, file_prefix)

    def pre_queue(self, filename, file_handle):
        """
        This is a temporary solution to solve the problem when one wants to get the full path
        they need to write to.

        Returns the full path to the file you're going to write and the artifact to which it should
        be uploaded. These can be used as arguments to `queue` to queue a file for upload. 
        """
        artifact = utils.single(
            sorted([shared_file for shared_file in self.artifact_service.shared_files()
                    if shared_file.name == file_handle], key=lambda x: x.id))
        full_path = os.path.join(self.temp_path, filename)
        return full_path, artifact

    def close_local_shared_files(self):
        for f in self._local_shared_files:
            f.close()

    def commit(self, disable_commits):
        """Copies files in the upload queue to the server"""
        self.close_local_shared_files()
        for artifact_id in self.os_service.listdir(self.upload_queue_path):
            for file_name in self.os_service.listdir(os.path.join(self.upload_queue_path, artifact_id)):
                if disable_commits:
                    self.logger.info("Uploading (disabled) file: {}".format(os.path.abspath(file_name)))
                else:
                    artifact = utils.single([shared_file for shared_file in self.artifact_service.shared_files()
                                             if shared_file.id == artifact_id])
                    local_file = os.path.join(self.upload_queue_path, artifact_id, file_name)
                    self.logger.info("Uploading file {}".format(local_file))
                    try:
                        self.session.api.upload_new_file(artifact.api_resource, local_file)
                    except requests.HTTPError as e:
                        if "UNDER_REVIEW" in str(e):
                            self.logger.error("Not able to upload step log as some of the samples are in review")
                        else:
                            raise e

    def _split_file_name(self, name):
        m = re.match(self.SERVER_FILE_NAME_PATTERN, name)
        if not m:
            raise Exception("The file name {} is not of the expected format <artifact id>_<name>".format(name))
        return m.groups()

    def save_locally(self, content, filename):
        """
        Saves a file locally before uploading it to the server. Content should be a string.
        """
        full_path = os.path.join(self.temp_path, filename)
        # The file needs to be opened in binary form to ensure that Windows
        # line endings are used if specified
        with self.os_service.open_file(full_path, 'wb') as f:
            self.logger.debug("Writing output to {}.".format(full_path))
            # Content should be either a string or something else we can
            # iterate over, in which case we need newline
            if isinstance(content, basestring):
                try:
                    f.write(content)
                except UnicodeEncodeError:
                    f.write(content.encode("utf-8"))
            else:
                raise NotImplementedError("Type not supported")
        return full_path


class LocalSharedFileProvider:
    def __init__(self, file_service, file_repo, artifact_service, downloaded_path, os_service, should_cache, logger):
        self.file_service = file_service
        self.file_repo = file_repo
        self.artifact_service = artifact_service
        self.downloaded_path = downloaded_path
        self.os_service = os_service
        self.should_cache = should_cache
        self.logger = logger

    def search_existing(self, file_handle, mode='r', extension="", modify_attached=False, file_name_contains=None):
        artifact = self._artifact_by_name(file_handle, file_name_contains)
        return self._local_shared_file(artifact, file_handle, mode=mode, extension=extension,
                                       modify_attached=modify_attached)

    def search_or_create(self, file_handle, mode='ab', extension="",
                         modify_attached=False, filename=None):
        if filename is None:
            filename = file_handle

        artifact = self._artifact_by_name(file_handle, filename, fallback_on_first_unassigned=True)
        return self._local_shared_file(artifact, filename, mode=mode, extension=extension,
                                       modify_attached=modify_attached)

    def check_file_extension(self, clarity_file_handle, required_extension=None, filename_contains=None):
        """

        :param clarity_file_handle: Type of file as written in the clarity lims ui
        :param required_extension: the dot should be included, e.g. '.csv'
        :param filename_contains: In case there are more than one file under a given clarity file handle
        :return: void
        """
        artifact = self._artifact_by_name(clarity_file_handle, filename=filename_contains)
        file_name = os.path.basename(artifact.file_name)
        _, actual_extension = os.path.splitext(file_name)
        if not required_extension == actual_extension:
            raise SharedFileNotFound('This file has the wrong extension: {}. Expected: {}, found: {}'.format(
                file_name, required_extension, actual_extension
            ))

    def _local_shared_file(self, artifact, filename, mode='r', extension="",
                           modify_attached=False):
        """
        Downloads the local shared file and returns an open file-like object.

        If the file already exists, it will not be downloaded again.

        Details:
        The downloaded files will be removed when the context is cleaned up. This ensures
        that the LIMS will not upload them by accident
        """
        local_file_name = "{}_{}.{}".format(artifact.id, filename.replace(" ", "_"), extension)
        local_file_name_rel_path = os.path.join(self.downloaded_path, local_file_name)
        local_file_name_abs_path = self.os_service.abspath(local_file_name_rel_path)
        cache_directory = self.os_service.abspath(".cache")
        cache_path = os.path.join(cache_directory, local_file_name)

        if self.should_cache and self.os_service.exists(cache_path):
            self._use_cache(cache_path)
        else:
            self._download_or_create_local_file(artifact, local_file_name_abs_path, modify_attached)

        if self.should_cache:
            self._save_cache_for_next_time(local_file_name_abs_path, cache_directory)

        if modify_attached:
            # Move the file to the upload directory and refer to it by that path afterwards. This way the local shared
            # file can be modified by the caller.
            local_path = self.file_service.queue(local_file_name_abs_path, artifact, FileService.FILE_PREFIX_NONE)
        else:
            local_path = local_file_name_abs_path

        f = self.file_repo.open_local_file(local_path, mode)
        self.file_service._local_shared_files.append(f)
        return f

    def _download_or_create_local_file(self, artifact, local_file_name_abs_path, modify_attached):
        if not self.os_service.exists(local_file_name_abs_path) and len(artifact.files) == 0 and modify_attached:
            # No file has been uploaded yet
            self._create_empty_file(local_file_name_abs_path)
        elif not self.os_service.exists(local_file_name_abs_path) and len(artifact.files) > 0:
            self._copy_remote_file(artifact, local_file_name_abs_path)

    def _use_cache(self, cache_path):
        self.logger.info("Fetching cached artifact from '{}'".format(cache_path))
        self.os_service.copy(cache_path, ".")

    def _save_cache_for_next_time(self, local_file_name_abs_path, cache_directory):
        if self.os_service.exists(local_file_name_abs_path):
            if not self.os_service.exists(cache_directory):
                self.os_service.mkdir(cache_directory)
            self.logger.info("Copying artifact to cache directory, {}=>{}".format(
                local_file_name_abs_path, cache_directory))
            self.os_service.copy(local_file_name_abs_path, cache_directory)

    def _create_empty_file(self, file_path):
        with self.os_service.open_file(file_path, "w+"):
            pass

    def _copy_remote_file(self, artifact, local_file_name_abs_path):
        file = artifact.api_resource.files[0]  # TODO: Hide this logic
        self.logger.info("Downloading file {} (artifact={} '{}')"
                         .format(file.id, artifact.id, artifact.name))
        self.file_repo.copy_remote_file(file.id, local_file_name_abs_path)
        self.logger.info("Download completed, path='{}'".format(os.path.relpath(local_file_name_abs_path)))

    def _artifact_by_name(self, file_handle, filename=None, fallback_on_first_unassigned=False):
        shared_files = self.artifact_service.shared_files()
        by_handle = sorted([shared_file for shared_file in shared_files
                            if shared_file.name == file_handle],
                           key=lambda f: int(f.id.replace('92-', '')))

        # Search for a match from already existing files
        filtered_artifacts = list()
        if filename is not None:
            filtered_artifacts = [a for a in by_handle if len(a.files) > 0 and filename in a.files[0].original_location]

        # No match, take the first artifact with no files yet associated
        if fallback_on_first_unassigned and len(filtered_artifacts) == 0:
            for a in by_handle:
                if len(a.files) == 0 and a.id not in self.file_service.artifactid_by_filename.itervalues():
                    filtered_artifacts = [a]
                    break
        elif not fallback_on_first_unassigned and len(filtered_artifacts) == 0:
            filtered_artifacts = by_handle

        if len(filtered_artifacts) != 1:
            files = ", ".join(map(lambda x: x.name, shared_files))
            searched_filename = filename if filename is not None else file_handle
            raise SharedFileNotFound("Expected a shared file called '{}', got {}.\nFile handle: '{}'\nFiles: {}".format(
                searched_filename, len(filtered_artifacts), file_handle, files))
        artifact = filtered_artifacts[0]
        return artifact


class SharedFileNotFound(Exception):
    pass


class Csv:
    """A simple wrapper for csv files"""
    def __init__(self, file_stream=None, delim=",", file_name=None, newline="\n", header=None):
        self.header = list()
        self.data = list()
        if file_stream:
            if isinstance(file_stream, basestring):
                with open(file_stream, "r") as fs:
                    self._init_from_file_stream(fs, delim, None)
            else:
                self._init_from_file_stream(file_stream, delim, header)
        self.file_name = file_name
        self.delim = delim
        self.newline = newline

    def _init_from_file_stream(self, file_stream, delim, header):
        lines = list()
        if header is not None:
            self.set_header(header)

        for ix, line in enumerate(file_stream):
            values = line.strip().split(delim)
            if ix == 0 and header is None:
                self.set_header(values)
            else:
                self.append(values)

    def set_header(self, header):
        self.key_to_index = {key: ix for ix, key in enumerate(header)}
        self.header = header

    def append(self, values, tag=None):
        """Appends a data line to the CSV, values is a list"""
        csv_line = CsvLine(values, self, tag)
        self.data.append(csv_line)

    def __iter__(self):
        return iter(self.data)

    def to_string(self, include_header=True):
        ret = []
        if include_header:
            ret.append(self.delim.join(map(str, self.header)))
        for line in self.data:
            ret.append(self.delim.join(map(str, line)))
        return self.newline.join(ret)

    def __repr__(self):
        return "<Csv {}>".format(self.file_name)


class CsvLine:
    """Represents one line in a CSV file, items can be added or removed like this were a dictionary"""
    def __init__(self, line, csv, tag=None):
        self.line = line
        self.csv = csv
        self.tag = tag

    def __getitem__(self, key):
        index = self.csv.key_to_index[key]
        return self.line[index]

    def __setitem__(self, key, value):
        index = self.csv.key_to_index[key]
        self.line[index] = value

    def __iter__(self):
        return iter(self.values)

    @property
    def values(self):
        return self.line

    def __repr__(self):
        return repr(self.values)


class OSService(object):
    """Provides access to OS file methods for testability"""

    def __init__(self):
        pass

    def exists(self, path):
        return os.path.exists(path)

    def makedirs(self, path):
        os.makedirs(path)

    def open_file(self, path, mode):
        return open(path, mode)

    def rmdir(self, path):
        os.rmdir(path)

    def rmtree(self, path):
        shutil.rmtree(path)

    def mkdir(self, path):
        os.mkdir(path)

    def copy_file(self, source, dest):
        shutil.copyfile(source, dest)

    def copy(self, src, dst):
        shutil.copy(src, dst)

    def listdir(self, path):
        return os.listdir(path)

    def attach_file_for_epp(self, local_file, artifact):
        # TODO: Remove epp from the name
        original_name = os.path.basename(local_file)
        new_name = artifact.id + '_' + original_name
        location = os.path.join(os.getcwd(), new_name)
        shutil.copy(local_file, location)
        return location

    def abspath(self, path):
        return os.path.abspath(path)


class RemoveFileException(Exception):
    pass
