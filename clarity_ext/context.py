from genologics.config import BASEURI, USERNAME, PASSWORD
from genologics.entities import *
import requests
import os
from clarity_ext.dilution import *
import re
import shutil
import clarity_ext.utils as utils
from lxml import objectify
from clarity_ext.units import Units
from clarity_ext.result_file import ResultFile


class ExtensionContext:
    """
    Defines context objects for extensions.
    """
    def __init__(self, logger=None, cache=False, clarity_svc=None):
        """
        Initializes the context.

        :param logger: A logger instance
        :param cache: Set to True to use the cache folder (.cache) for downloaded files
        :param clarity_svc: A LimsService object, encapsulates connections to the Clarity application server
        """

        self.advanced = Advanced(clarity_svc.api)
        self.logger = logger or logging.getLogger(__name__)
        self._local_shared_files = []
        self.cache = cache

        self.units = Units(self.logger)
        self._update_queue = []
        self.current_step = clarity_svc.current_step

    def local_shared_file(self, file_name, mode='r'):
        """
        Downloads the local shared file and returns an open file-like object.

        If the file already exists, it will not be downloaded again.

        Details:
        The downloaded files will be removed when the context is cleaned up. This ensures
        that the LIMS will not upload them by accident
        """

        # Ensure that the user is only sending in a "name" (alphanumerical or spaces)
        # File paths are not allowed
        if not re.match(r"[\w ]+", file_name):
            raise ValueError("File name can only contain alphanumeric characters, underscores and spaces")
        local_file_name = file_name.replace(" ", "_")
        local_path = os.path.abspath(local_file_name)
        local_path = os.path.abspath(local_path)
        cache_directory = os.path.abspath(".cache")
        cache_path = os.path.join(cache_directory, local_file_name)

        if self.cache and os.path.exists(cache_path):
            self.logger.info("Fetching cached artifact from '{}'".format(cache_path))
            shutil.copy(cache_path, ".")
        else:
            if not os.path.exists(local_path):
                by_name = [shared_file for shared_file in self.shared_files
                           if shared_file.name == file_name]
                if len(by_name) != 1:
                    files = ", ".join(map(lambda x: x.name, self.shared_files))
                    raise ValueError("Expected 1 shared file, got {}.\nFile: '{}'\nFiles: {}".format(
                        len(by_name), file_name, files))
                artifact = by_name[0]
                assert len(artifact.files) == 1
                file = artifact.files[0]
                self.logger.info("Downloading file {} (artifact={} '{}')"
                                 .format(file.id, artifact.id, artifact.name))

                # TODO: implemented in the genologics package?
                response = self.advanced.get("files/{}/download".format(file.id))
                with open(local_path, 'wb') as fd:
                    for chunk in response.iter_content():
                        fd.write(chunk)

                self.logger.info("Download completed, path='{}'".format(local_path))

                if self.cache:
                    if not os.path.exists(cache_directory):
                        os.mkdir(cache_directory)
                    self.logger.info("Copying artifact to cache directory, {}=>{}".format(local_path, cache_directory))
                    shutil.copy(local_path, cache_directory)

        # Add to this list for cleanup:
        if local_path not in self._local_shared_files:
            self._local_shared_files.append(local_path)

        return open(local_path, mode)

    def _get_input_analytes(self, plate):
        # Get an unique set of input analytes
        # Trust the fact that all inputs are analytes, always true?
        resources = self.current_step.all_inputs(unique=True, resolve=True)
        return [Analyte(resource, plate) for resource in resources]

    @lazyprop
    def dilution_scheme(self):
        plate = Plate(plate_type=PLATE_TYPE_96_WELL)

        input_analytes = self._get_input_analytes(plate)
        # TODO: Seems like overkill to have a type for matching analytes, why not a gen. function?
        matched_analytes = MatchedAnalytes(input_analytes,
                                           self.current_step, self.advanced, plate)
        # TODO: The caller needs to provide these arguments
        return DilutionScheme(matched_analytes, "Hamilton", plate)

    @lazyprop
    def shared_files(self):
        """
        Fetches all share files for the current step
        """
        unique = dict()
        # The API input/output map is rather convoluted, but according to
        # the Clarity developers, this is a valid way to fetch all shared result files:
        for input, output in self.current_step.input_output_maps:
            if output['output-generation-type'] == "PerAllInputs":
                unique.setdefault(output["uri"].id, output["uri"])

        artifacts = self.advanced.lims.get_batch(unique.values())
        return artifacts

    @lazyprop
    def _extended_input_artifacts(self):
        artifacts = []
        for input, output in self.current_step.input_output_maps:
            if output['output-generation-type'] == "PerInput":
                artifacts.append(output['uri'])

        # Batch fetch the details about these:
        artifacts_ex = self.advanced.lims.get_batch(artifacts)
        return artifacts_ex

    @lazyprop
    def _extended_input_containers(self):
        """
        Returns a list with all input containers, where each container has been extended with the attribute
        `artifacts`, containing all artifacts in the container
        """
        containers = {artifact.container.id: artifact.container
                      for artifact in self._extended_input_artifacts}
        ret = []
        for container_res in containers.values():
            artifacts_res = [artifact for artifact in self._extended_input_artifacts
                             if artifact.container.id == container_res.id]
            ret.append(Container.create_from_rest_resource(container_res, artifacts_res))
        return ret

    @lazyprop
    def input_container(self):
        """Returns the input container. If there are more than one, an error is raised"""
        return utils.single(self._extended_input_containers)

    def cleanup(self):
        """Cleans up any downloaded resources. This method will be automatically
        called by the framework and does not need to be called by extensions"""
        # Clean up:
        for path in self._local_shared_files:
            if os.path.exists(path):
                self.logger.info("Local shared file '{}' will be removed to ensure "
                                 "that it won't be uploaded again".format(path))
                # TODO: Handle exception
                os.remove(path)

    def local_shared_xml(self, name):
        """
        Returns a local copy of the xml file as a Python object
        """
        with self.local_shared_file(name, "r") as fs:
            tree = objectify.parse(fs)
            return tree.getroot()


class MatchedAnalytes:
    """ Provides a set of  matched input - output analytes for a process.
    When fetching these by the batch_get(), they come in random order
    """
    def __init__(self, input_analytes, current_step, advanced, plate):
        self._input_analytes = input_analytes
        self.advanced = advanced
        self.current_step = current_step
        self.input_analytes, self.output_analytes = self._match_analytes(plate)
        self._iteritems = iter(zip(self.input_analytes, self.output_analytes))

    def __iter__(self):
        return self

    def next(self):
        input_analyte, output_analyte = self._iteritems.next()
        if input_analyte and output_analyte:
            return input_analyte, output_analyte
        else:
            raise StopIteration

    def _get_output_analytes(self, plate):
        analytes, info = self.current_step.analytes()
        if not info == 'Output':
            raise ValueError("No output analytes for this step!")
        resources = self.advanced.lims.get_batch(analytes)
        return [Analyte(resource, plate) for resource in resources]

    def _match_analytes(self, plate):
        """ Match input and output analytes with sample ids"""
        input_dict = {_input.sample.id: _input
                      for _input in self._input_analytes}
        matched_analytes = [(input_dict[_output.sample.id], _output)
                            for _output in self._get_output_analytes(plate)]
        input_analytes, output_analytes = zip(*matched_analytes)
        return list(input_analytes), list(output_analytes)


class Advanced:
    """Provides advanced features, should be avoided in extension scripts"""
    def __init__(self, lims):
        self.lims = lims

    def get(self, endpoint):
        """Executes a GET via the REST interface. One should rather use the lims attribute if possible.
        The endpoint is the part after /api/<version>/ in the API URI.
        """
        url = "{}/api/v2/{}".format(BASEURI, endpoint)
        return requests.get(url, auth=(USERNAME, PASSWORD))


class ClarityService:
    """A wrapper around connections to the lims. Provided for testability"""
    def __init__(self, api, current_step):
        self.api = api
        api.check_version()
        self.current_step = Process(self.api, id=current_step)

