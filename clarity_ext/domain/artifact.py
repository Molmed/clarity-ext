from clarity_ext.domain.common import DomainObjectMixin
from clarity_ext.domain.common import AssignLogger


class Artifact(DomainObjectMixin):
    """
    Represents any input or output artifact from the Clarity server, e.g. an Analyte
    or a ResultFile.
    """
    PER_INPUT = 1
    PER_ALL_INPUTS = 2

    OUTPUT_TYPE_RESULT_FILE = 1
    OUTPUT_TYPE_ANALYTE = 2
    OUTPUT_TYPE_SHARED_RESULT_FILE = 3

    def __init__(self, api_resource=None):
        self.is_input = None  # Set to true if this is an input artifact
        self.generation_type = None  # Set to PER_INPUT or PER_ALL_INPUTS if applicable
        self.assigner = AssignLogger(self)
        self.api_resource = api_resource

    def set_udf(self, name, value, from_unit=None, to_unit=None):
        if from_unit:
            value = self.units.convert(value, from_unit, to_unit)
        self.api_resource.udf[name] = self.assigner.log_assign(name, value)

    def get_udf(self, name):
        return self.api_resource.udf[name]

    def commit(self):
        self.api_resource.put()


class ArtifactPair(DomainObjectMixin):
    """
    Represents an input/output pair of artifacts
    """

    def __init__(self, input_artifact, output_artifact):
        self.input_artifact = input_artifact
        self.output_artifact = output_artifact

    def __repr__(self):
        return "{}, {}".format(self.input_artifact.id, self.output_artifact.id)

