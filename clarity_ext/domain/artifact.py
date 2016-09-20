from clarity_ext.domain.common import DomainObjectMixin
from clarity_ext.utils import lazyprop
from clarity_ext.domain.common import AssignLogger
from clarity_ext.utils import get_and_apply


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

    def __init__(self, api_resource=None, artifact_specific_udf_map=None):
        self.is_input = None  # Set to true if this is an input artifact
        self.generation_type = None  # Set to PER_INPUT or PER_ALL_INPUTS if applicable
        if artifact_specific_udf_map:
            self.udf_map = artifact_specific_udf_map
        else:
            self.udf_map = dict()
        self.assigner = AssignLogger(self)
        self.api_resource = api_resource

    @lazyprop
    def udf_backward_map(self):
        return {self.udf_map[key]: key for key in self.udf_map}

    def reset_assigner(self):
        self.assigner = AssignLogger(self)

    def set_udf(self, name, value, from_unit=None, to_unit=None):
        if from_unit:
            value = self.units.convert(value, from_unit, to_unit)
        if name in self.udf_backward_map:
            # Assign existing instance variable
            # Log for assignment of instance variables are handled in
            # step_repository.commit()
            self.__dict__[self.udf_backward_map[name]] = value
        else:
            # There is no mapped instance variable for this udf.
            # Log the assignment right away
            self.api_resource.udf[name] = self.assigner.register_assign(name, value)

    def get_udf(self, name):
        return self.api_resource.udf[name]

    def updated_rest_resource(self, original_rest_resource, updated_fields):
        """
        :param original_rest_resource: The rest resource in the state as in the api cache
        :return: An updated rest resource according to changes in this instance of Analyte
        """
        # TODO: Update udfs that is not present in the original xml received from db
        # A ticket is sent to Clarity support (160902)
        _updated_rest_resource = original_rest_resource
        # TODO: This implementation is not ready! Implementation is moved to another ticket
        # in Jira

        # Update udf values
        values_by_udf_names = {self.udf_map[key]: self.__dict__[key]
                               for key in self.udf_map if key in updated_fields}
        # Retrieve fields that are updated, only these field should be included in the rest update
        for key in values_by_udf_names:
            value = values_by_udf_names[key]
            _updated_rest_resource.udf[key] = self.assigner.register_assign(key, value)

        return _updated_rest_resource

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

