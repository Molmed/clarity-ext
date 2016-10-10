from clarity_ext import utils
from clarity_ext.domain import *
import logging
from clarity_ext.domain.shared_result_file import SharedResultFile


class ArtifactService:
    """
    Provides access to "Artifacts" in Clarity, e.g. analytes and result files.
    """

    def __init__(self, step_repository):
        self.step_repository = step_repository
        self.logger = logging.getLogger(__name__)

    def shared_files(self):
        """
        Returns all shared files for the current step
        """
        outputs = (outp for inp, outp in self.step_repository.all_artifacts())
        shared_files = (
            outp for outp in outputs if outp.generation_type == Artifact.PER_ALL_INPUTS)
        ret = list(utils.unique(shared_files, lambda f: f.id))
        assert len(ret) == 0 or isinstance(ret[0], SharedResultFile)
        return ret

    def all_aliquot_pairs(self):
        """
        Returns all aliquots in a step as an artifact pair (input/output)
        """
        pairs = self.step_repository.all_artifacts()
        aliquots_only = filter(lambda pair: isinstance(pair[0], Aliquot)
                               and isinstance(pair[1], Aliquot), pairs)
        return [ArtifactPair(i, o) for i, o in aliquots_only]

    def all_analyte_pairs(self):
        """
        Returns all analytes in a step as an artifact pair (input/output)
        """
        pairs = self.step_repository.all_artifacts()
        analytes_only = filter(lambda pair: isinstance(pair[0], Analyte)
                               and isinstance(pair[1], Analyte), pairs)
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
        # TODO: Ensure cache for this call, perhaps keeping the state in the
        # ArtifactService
        for pair in self.step_repository.all_artifacts():
            if isinstance(pair[pair_index], type):
                yield pair[pair_index]

    def all_input_analytes(self):
        """Returns a unique list of input analytes"""
        return filter(lambda x: isinstance(x, Analyte), self.all_input_artifacts())

    def all_output_analytes(self):
        """Returns a unique list of output analytes"""
        return filter(lambda x: isinstance(x, Analyte), self.all_output_artifacts())

    def all_output_containers(self):
        artifacts_having_container = (artifact.container
                                      for artifact in self.all_output_artifacts()
                                      if isinstance(artifact, Aliquot) and artifact.container is not None)
        containers = utils.unique(
            artifacts_having_container, lambda item: item.id)
        return list(containers)

    def all_input_containers(self):
        artifacts_having_container = (artifact.container
                                      for artifact in self.all_input_artifacts()
                                      if artifact.container is not None)
        containers = utils.unique(
            artifacts_having_container, lambda item: item.id)
        return list(containers)

    def all_output_files(self):
        outputs = (outp for inp, outp in self.step_repository.all_artifacts())
        files = (outp for outp in outputs
                 if outp.output_type == Artifact.OUTPUT_TYPE_RESULT_FILE)
        ret = list(utils.unique(files, lambda f: f.id))
        return ret

    def output_file_by_id(self, file_id):
        ret = utils.single(
            [outp for outp in self.all_output_files() if outp.id == file_id])
        return ret

    def all_shared_result_files(self):
        outputs = (outp for inp, outp in self.step_repository.all_artifacts())
        files = (outp for outp in outputs
                 if outp.output_type == Artifact.OUTPUT_TYPE_SHARED_RESULT_FILE)
        ret = list(utils.unique(files, lambda f: f.id))
        assert len(ret) == 0 or isinstance(ret[0], ResultFile)
        return ret

    def update_artifacts(self, update_queue):
        response = self.step_repository.update_artifacts(update_queue)
        return response
