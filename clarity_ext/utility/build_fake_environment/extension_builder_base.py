from types import SimpleNamespace

from clarity_ext.utility.build_fake_environment.internal_builders import FakeStepRepoBuilder
from clarity_ext.utility.build_fake_environment.internal_builders import PairBuilder
from clarity_ext.utility.build_fake_environment.internal_builders import ContextBuilder


class ExtensionBuilderBase:
    """
    1. call with_analyte_udf, with_output_type, with_mocked_local_shared_file
       (udfs that are to be set from result file)
    2. call with_step_udf (with specific values from user)
    3. call create_pair, N number times
    4. call create
    """
    def __init__(self):
        self.shared_file_handle = None
        self.context_builder = None
        self.step_repo_builder = FakeStepRepoBuilder()
        self.pair_builder = PairBuilder()
        self.extension_type = None

    def create_pair(self, target_artifact_id, name=None):
        artifact_pair_builder = self.pair_builder
        artifact_pair_builder.with_target_id(target_artifact_id)
        artifact_pair_builder.with_name(name)
        artifact_pair_builder.create()
        return artifact_pair_builder.pair

    @property
    def extension(self):
        return self.extension_type(self.context_builder.context)

    @property
    def context(self):
        return self.context_builder.context

    def create(self, extension_type, pairs, file_contents=None):
        self.extension_type = extension_type
        user = SimpleNamespace(initials='xx')
        self.context_builder = ContextBuilder(self.step_repo_builder, user)
        self.context_builder.with_mocked_local_shared_file(
            self.shared_file_handle, file_contents or "")
        for pair in pairs:
            self.context_builder.with_analyte_pair(pair.input_artifact, pair.output_artifact)

    def with_configured_analyte_udf(self, lims_udf_name, default_udf_value):
        # This simulates that all analytes in a step has a pre-configured udf
        # In many cases, this udf has not been populated at start of script execution
        self.pair_builder.with_output_udf(lims_udf_name, default_udf_value)

    def with_output_type(self, output_type):
        self.pair_builder.target_type = output_type

    def with_step_udf(self, lims_udf_name, udf_value):
        self.step_repo_builder.with_process_udf(lims_udf_name, udf_value)

    def with_mocked_local_shared_file(self, filehandle):
        self.shared_file_handle = filehandle