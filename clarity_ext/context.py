import logging
from clarity_ext.dilution import *
from clarity_ext import UnitConversion
from clarity_ext.repository.file_repository import FileRepository
from clarity_ext.utils import lazyprop
from clarity_ext import ClaritySession
from clarity_ext.service import ArtifactService, FileService
from clarity_ext.repository import StepRepository
from clarity_ext import utils


class ExtensionContext(object):
    """
    Defines context objects for extensions.


    Details: The context provides simplified access to underlying
    services, so the extension writer writes minimal code and is
    limited by default to only a subset of functionality, while being
    able to access the underlying services if needed.
    """

    def __init__(self, session, artifact_service, file_service, cache=False, logger=None):
        """
        Initializes the context.

        :param session: An object encapsulating the connection to Clarity
        :param artifact_service: Provides access to artifacts in the current step
        :param file_service: Provides access to result files locally on the machine.
        :param cache: Set to True to use the cache folder (.cache) for downloaded files
        :param logger: A logger instance
        """
        self.session = session
        self.logger = logger or logging.getLogger(__name__)
        self.cache = cache

        self.units = UnitConversion(self.logger)
        self._update_queue = []
        self.current_step = session.current_step
        self.artifact_service = artifact_service
        self.file_service = file_service
        self.response = None

    @staticmethod
    def create(step_id, cache=False):
        """
        Creates a context with all required services set up. This is the way
        a context is meant to be created in production and integration tests,
        use the constructor for custom use and unit tests.
        """
        session = ClaritySession.create(step_id)
        step_repo = StepRepository(session)
        artifact_service = ArtifactService(step_repo)
        file_repository = FileRepository(session)
        file_service = FileService(artifact_service, file_repository, False)
        return ExtensionContext(session, artifact_service, file_service, cache=cache)

    @lazyprop
    def dilution_scheme(self):
        # TODO: The caller needs to provide the robot
        return DilutionScheme(self.artifact_service, "Hamilton")

    @lazyprop
    def shared_files(self):
        """
        Fetches all share files for the current step
        """
        return self.artifact_service.shared_files()

    @lazyprop
    def all_analytes(self):
        return self.artifact_service.all_analyte_pairs()

    @lazyprop
    def output_containers(self):
        """
        Returns all output containers, with respective items
        """
        # TODO: Ensure that the artifacts are not fetched again
        return self.artifact_service.all_output_containers()

    @lazyprop
    def output_container(self):
        """
        A convenience method for fetching a single output container and raising
        an exception if there is more than one.
        """
        return utils.single(self.artifact_service.all_output_containers())

    @lazyprop
    def input_containers(self):
        """
        Returns a list with all input containers, where each container has been extended with the attribute
        `artifacts`, containing all artifacts in the container
        """
        return self.artifact_service.all_input_containers()

    @lazyprop
    def input_container(self):
        """
        A convenience method for fetching a single input container and raising
        an exception if there is more than one.
        """
        return utils.single(self.artifact_service.all_input_containers())

    def cleanup(self):
        """Cleans up any downloaded resources. This method will be automatically
        called by the framework and does not need to be called by extensions"""
        # Clean up:
        self.file_service.cleanup()

    def local_shared_file(self, name, mode="r", is_xml=False):
        f = self.file_service.local_shared_file(name, mode=mode)
        if is_xml:
            return self.file_service.parse_xml(f)
        else:
            return f

    def output_result_file_by_id(self, file_id):
        """Returns the output result file by id"""
        return self.artifact_service.output_file_by_id(file_id)

    @property
    def output_result_files(self):
        return self.artifact_service.all_output_files()

    def update(self, obj):
        """Add an object that has a commit method to the list of objects to update"""
        self._update_queue.append(obj)

    def commit(self):
        """Commits all objects that have been added via the update method, using batch processing if possible"""
        self.response = self.artifact_service.update_artifacts(self._update_queue)


