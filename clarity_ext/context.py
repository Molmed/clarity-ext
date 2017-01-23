from clarity_ext.service.dilution_service import DilutionService
from clarity_ext import UnitConversion
from clarity_ext.repository import ClarityRepository, FileRepository
from clarity_ext.utils import lazyprop
from clarity_ext import ClaritySession
from clarity_ext.service import ArtifactService, FileService, StepLoggerService, ClarityService, UploadFileService
from clarity_ext.repository import StepRepository
from clarity_ext import utils
from clarity_ext.service.file_service import OSService
from clarity_ext.service.validation_service import ERRORS_AND_WARNING_ENTRY_NAME


class ExtensionContext(object):
    """
    Defines context objects for extensions.


    Details: The context provides simplified access to underlying
    services, so the extension writer writes minimal code and is
    limited by default to only a subset of functionality, while being
    able to access the underlying services if needed.
    """

    def __init__(self, session, artifact_service, file_service, current_user,
                 step_logger_service, step_repo, clarity_service, dilution_service,
                 upload_file_service, test_mode=False,
                 disable_commits=False):
        """
        Initializes the context.

        :param session: An object encapsulating the connection to Clarity
        :param artifact_service: Provides access to artifacts in the current step
        :param file_service: Provides access to result files locally on the machine.
        :param step_logger_service: Provides access to logging via the context.
        :param current_user: The user executing the step
        :param step_repo: The repository for the current step
        :param clarity_service: General service for working with domain objects
        :param dilution_service: A service for handling dilutions
        :param upload_file_service: A service for uploading files to the server
        :param test_mode: If set to True, extensions may behave slightly differently when testing, in particular
                          returning a constant time.
        :param disable_commits: True if commits should be ignored, e.g. when uploading files or updating UDFs.
        Useful when testing.
        """
        self.session = session
        self.logger = step_logger_service
        self.units = UnitConversion()
        self._update_queue = []
        self.current_step = session.current_step
        self.artifact_service = artifact_service
        self.file_service = file_service
        self.current_user = current_user
        self.step_repo = step_repo
        self.dilution_scheme = None
        self.disable_commits = False
        self.dilution_service = dilution_service
        self.upload_file_service = upload_file_service
        self.test_mode = test_mode
        self.clarity_service = clarity_service
        self.disable_commits = disable_commits

    @staticmethod
    def create(step_id, test_mode=False, uploaded_to_stdout=False, disable_commits=False, upload_files=True):
        """
        Creates a context with all required services set up. This is the way
        a context is meant to be created in production and integration tests,
        use the constructor for custom use and unit tests.
        """
        session = ClaritySession.create(step_id)
        step_repo = StepRepository(session)
        artifact_service = ArtifactService(step_repo)
        current_user = step_repo.current_user()
        file_repository = FileRepository(session)
        file_service = FileService(artifact_service, file_repository, False, OSService())
        step_logger_service = StepLoggerService("Step log", file_service)
        clarity_service = ClarityService(ClarityRepository(), step_repo)
        dilution_service = DilutionService(artifact_service)
        upload_file_service = UploadFileService(OSService(), artifact_service,
                                                uploaded_to_stdout=uploaded_to_stdout,
                                                disable_commits=not upload_files)
        return ExtensionContext(session, artifact_service, file_service, current_user,
                                step_logger_service, step_repo, clarity_service,
                                dilution_service, upload_file_service, test_mode=test_mode,
                                disable_commits=disable_commits)

    @lazyprop
    def error_log_artifact(self):
        """
        Returns a file on the current step that can be used for marking the step as having an error
        without having a visible UDF on the step.
        """
        file_list = [file for file in self.shared_files if file.name ==
                     ERRORS_AND_WARNING_ENTRY_NAME]
        if not len(file_list) == 1:
            raise ValueError("This step is not configured with the shared file entry for {}".format(
                ERRORS_AND_WARNING_ENTRY_NAME))
        return file_list[0]

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

    def local_shared_file(self, name, mode="r", is_xml=False, is_csv=False):
        """
        Downloads the file from the current step. The returned file is generally a regular
        file-like object, but can be casted to an xml object or csv by passing in is_xml or is_csv.


        NOTE: It would make sense to use constants instead of is_xml and is_csv, but since this
        is designed to be used by non-developers, this might be more readable.
        """
        if is_xml and is_csv:
            raise ValueError("More than one file type specifiers")
        f = self.file_service.local_shared_file(name, mode=mode)
        if is_xml:
            return self.file_service.parse_xml(f)
        elif is_csv:
            return self.file_service.parse_csv(f)
        else:
            return f

    def output_result_file_by_id(self, file_id):
        """Returns the output result file by id"""
        return self.artifact_service.output_file_by_id(file_id)

    @property
    def output_result_files(self):
        return self.artifact_service.all_output_files()

    @property
    def pid(self):
        return self.session.current_step_id

    def update(self, obj):
        """Add an object that has a commit method to the list of objects to update"""
        self._update_queue.append(obj)

    def commit(self):
        """Commits all objects that have been added via the update method, using batch processing if possible"""
        self.clarity_service.update(self._update_queue, self.disable_commits)

