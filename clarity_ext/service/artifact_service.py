import logging
from clarity_ext.domain import *
from clarity_ext.domain.shared_result_file import SharedResultFile
from clarity_ext.repository import StepRepository
from clarity_ext import ClaritySession


class ArtifactService:
    """
    Provides access to "Artifacts" in Clarity, e.g. analytes and result files.

    Artifacts are fetched through the step_repository, provided in the constructor.

    All objects fetched from the step repository are cached.
    """

    def __init__(self, step_repository, logger=None):
        self.step_repository = step_repository
        self.logger = logger or logging.getLogger(__name__)
        self._artifacts = None
        self._parent_input_artifacts_by_sample_id = None

    def all_artifacts(self):
        # NOTE: The underlying REST library does also do some caching, but since this library wraps
        # objects, some benefit may be achieved by caching on this level too.
        if not self._artifacts:
            self._artifacts = self.step_repository.all_artifacts()
        return self._artifacts

    def shared_files(self):
        """
        Returns all shared files for the current step
        """
        outputs = (outp for inp, outp in self.all_artifacts())
        shared_files = (
            outp for outp in outputs if isinstance(outp, SharedResultFile))
        ret = list(utils.unique(shared_files, lambda f: f.id))
        assert len(ret) == 0 or isinstance(ret[0], SharedResultFile)
        return ret

    def all_aliquot_pairs(self):
        """
        Returns all aliquots in a step as an artifact pair (input/output)
        """
        pairs = self.step_repository.all_artifacts()
        aliquots_only = filter(lambda pair: isinstance(pair[0], Aliquot) and
                               isinstance(pair[1], Aliquot), pairs)
        return [ArtifactPair(i, o) for i, o in aliquots_only]

    def all_analyte_pairs(self):
        """
        Returns all analytes in a step as an artifact pair (input/output)
        """
        pairs = self.all_artifacts()
        analytes_only = filter(lambda pair: isinstance(pair[0], Analyte) and
                               isinstance(pair[1], Analyte), pairs)
        return [ArtifactPair(i, o) for i, o in analytes_only]

    def all_input_artifacts(self):
        """Returns a unique list of input artifacts"""
        return utils.unique(self._filter_artifact(True, Artifact), lambda item: item.id)

    def all_output_artifacts(self):
        """Returns a unique list of output artifacts"""
        return utils.unique(self._filter_artifact(False, Artifact), lambda item: item.id)

    def _filter_artifact(self, input, type):
        # Fetches all input analytes in the step, unique
        pair_index = 0 if input else 1
        for pair in self.all_artifacts():
            if isinstance(pair[pair_index], type):
                yield pair[pair_index]

    def all_input_analytes(self):
        """Returns a unique list of input analytes"""
        return filter(lambda x: isinstance(x, Analyte), self.all_input_artifacts())

    def all_output_analytes(self):
        """Returns a unique list of output analytes"""
        return filter(lambda x: isinstance(x, Analyte), self.all_output_artifacts())

    def all_output_containers(self):
        containers_non_unique = (artifact.container
                                 for artifact in self.all_output_artifacts()
                                 if isinstance(artifact, Aliquot) and artifact.container is not None)
        containers = utils.unique(
            containers_non_unique, lambda item: item.id)
        return list(containers)

    def all_input_containers(self):
        artifacts_having_container = (artifact.container
                                      for artifact in self.all_input_artifacts()
                                      if artifact.container is not None)
        containers = utils.unique(
            artifacts_having_container, lambda item: item.id)
        return list(containers)

    def all_output_files(self):
        outputs = (outp for inp, outp in self.all_artifacts())
        files = (outp for outp in outputs
                 if outp.output_type == Artifact.OUTPUT_TYPE_RESULT_FILE)
        ret = list(utils.unique(files, lambda f: f.id))
        return ret

    def output_file_by_id(self, file_id):
        ret = utils.single(
            [outp for outp in self.all_output_files() if outp.id == file_id])
        return ret

    def all_shared_result_files(self):
        outputs = (outp for inp, outp in self.all_artifacts())
        files = (outp for outp in outputs
                 if outp.output_type == Artifact.OUTPUT_TYPE_SHARED_RESULT_FILE)
        ret = list(utils.unique(files, lambda f: f.id))
        assert len(ret) == 0 or isinstance(ret[0], ResultFile)
        return ret

    def parent_input_artifacts(self):
        """
        Returns a dictionary of all parent input artifacts, indexed by process ID.

        Details:
        In your current step (CS), you will have input and output artifacts like this:
            [CS-I1  ->  CS-O1]
            [CS-I2  ->  CS-O2]
            ...

        These artifacts may be coming from a parent step (PS):
            [PS-I1  ->  PS-O1]  -> [CS-I1   -> CS-O2]
            ...

        This method will fetch all of the input artifacts based on all of your output artifacts in one call
        and index them by their respective process id.
        """
        # We will need the input artifacts from the previous step
        parent_processes = set([artifact.input.parent_process for artifact in self.all_output_artifacts()])

        for process in parent_processes:
            # This might seem roundabout, but for simplicity, we create another artifact service for
            # fetching the parent items:
            parent_step_repo = StepRepository(ClaritySession.create(process.id),
                                              self.step_repository.clarity_mapper)
            parent_artifact_service = ArtifactService(parent_step_repo)
            for input in parent_artifact_service.all_input_artifacts():
                yield input

    def get_parent_input_artifact(self, sample):
        """
        Given a sample in some artifact, returns parent artifact for that sample.

        Performance note:
        Starts by fetching all input artifacts of all parent processes (to save time if there are further calls)
        """
        if not self._parent_input_artifacts_by_sample_id:
            parent_input_artifacts = list(self.parent_input_artifacts())
            self._parent_input_artifacts_by_sample_id = dict()
            for parent_input_artifact in parent_input_artifacts:
                for current_sample in parent_input_artifact.samples:
                    if current_sample.id in self._parent_input_artifacts_by_sample_id:
                        previously_mapped = self._parent_input_artifacts_by_sample_id[current_sample.id]
                        if previously_mapped != parent_input_artifact:
                            raise ValueError("Can't find parent input artifact for sample {}. "
                                             "It maps to different parent analytes {}".format(sample.id,
                                                 [parent_input_artifact, previously_mapped]))
                    self._parent_input_artifacts_by_sample_id[current_sample.id] = parent_input_artifact
        if sample.id not in self._parent_input_artifacts_by_sample_id:
            raise ValueError("Can't find a parent artifact for this sample: {}".format(sample.id))
        return self._parent_input_artifacts_by_sample_id[sample.id]

    def all_output_result_files(self):
        """
        Returns all individual output `ResultFile`s. These are generated "per input".
        """
        return [output for _, output in self.all_artifacts()
                if output.generation_type == output.PER_INPUT]
