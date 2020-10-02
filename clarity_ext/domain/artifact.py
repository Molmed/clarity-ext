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

    def __init__(self, api_resource=None, artifact_id=None, name=None, udf_map=None,
                 is_input=None, mapper=None):
        super(Artifact, self).__init__(api_resource=api_resource, id=artifact_id, udf_map=udf_map)
        self.is_input = is_input
        self.generation_type = None  # Set to PER_INPUT or PER_ALL_INPUTS if applicable
        self._name = name
        self.view_name = name
        self._mapper = mapper

        # NOTE: This is currently only used in tests, so you can't trust that it has been set
        self.pairings = list()
        self.output_type = None
        if not is_input:
            self._set_output_type()

    def _set_output_type(self):
        raise NotImplementedError(
            'Output type {} is not implemented'.format(self.__class__.__name__))

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self.view_name = value

    def pair_as_output(self, input_artifact):
        return self.pair_together(input_artifact, self)

    def pair_as_input(self, output_artifact):
        return self.pair_together(self, output_artifact)

    @staticmethod
    def pair_together(input_artifact, output_artifact):
        """Marks two artifacts as input/output, pairs them together in an ArtifactPair object and sets evidence
        about the pairing on both objects"""
        input_artifact.is_input = True
        output_artifact.is_input = False
        pair = ArtifactPair(input_artifact, output_artifact)
        input_artifact.pairings.append(pair)
        output_artifact.pairings.append(pair)
        return pair


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
