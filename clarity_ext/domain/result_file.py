from clarity_ext.domain.aliquot import Aliquot, Sample
from clarity_ext.domain.artifact import Artifact
from clarity_ext import utils
from clarity_ext.domain.udf import UdfMapping


class ResultFile(Aliquot):
    """Encapsulates a ResultFile in Clarity"""

    def __init__(self, api_resource, is_input, id=None, samples=None, name=None, well=None,
                 udf_map=None, mapper=None):
        """
        :param api_resource: The original API resource
        :param is_input: True if this is an input analyte, false if not
        :param samples:
        :param name: Name of the result file
        :param well: Well (location, TODO rename) of the result file
        :param udf_map: A list of UdfMappingInfo objects
        """
        # TODO: Get rid of the api_resource
        super(self.__class__, self).__init__(api_resource, is_input=is_input, id=id,
                samples=samples, name=name, well=well, udf_map=udf_map, mapper=mapper)
        self.is_control = False

    def _set_output_type(self):
        self.output_type = Artifact.OUTPUT_TYPE_RESULT_FILE

    @property
    def sample(self):
        """Convenience property for fetching a single sample when only one is expected"""
        return utils.single(self.samples)

    def __repr__(self):
        typename = type(self).__name__
        return "{}<{} ({})>".format(typename, self.name, self.id)
