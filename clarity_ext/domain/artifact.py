from clarity_ext.domain.udf import DomainObjectWithUdfMixin
from clarity_ext.domain.common import DomainObjectMixin


class Artifact(DomainObjectWithUdfMixin):
    """
    Represents any input or output artifact from the Clarity server, e.g. an Analyte
    or a ResultFile.
    """
    PER_INPUT = 1
    PER_ALL_INPUTS = 2

    OUTPUT_TYPE_RESULT_FILE = 1
    OUTPUT_TYPE_ANALYTE = 2
    OUTPUT_TYPE_SHARED_RESULT_FILE = 3

    def __init__(self, api_resource=None, artifact_id=None, name=None, udf_map=None):
        super(Artifact, self).__init__(api_resource=api_resource, id=artifact_id, udf_map=udf_map)
        self.is_input = None  # Set to true if this is an input artifact
        self.generation_type = None  # Set to PER_INPUT or PER_ALL_INPUTS if applicable
        self.name = name


class ArtifactPair(object):
    """
    Represents an input/output pair of artifacts
    """

    def __init__(self, input_artifact, output_artifact):
        self.input_artifact = input_artifact
        self.output_artifact = output_artifact

    def __repr__(self):
        return "(in={}, out={})".format(self.input_artifact, self.output_artifact)

    def __iter__(self):
        yield self.input_artifact
        yield self.output_artifact
