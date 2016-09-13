from clarity_ext.domain.container import ContainerPosition, Well
from clarity_ext.utils import get_and_apply
from clarity_ext.domain.common import DomainObjectMixin
from clarity_ext.domain.artifact import Artifact


class Analyte(Artifact):
    """
    Describes an Analyte in the Clarity LIMS system.

    Expects certain mappings to UDFs in clarity. These are provided
    in udf_map, so they can be overridden in different installations.
    """

    def __init__(self, api_resource, name=None, well=None, sample=None,
                 artifact_specific_udf_map=None, id=None, **kwargs):
        """
        Creates an analyte
        """
        super(self.__class__, self).__init__(api_resource, artifact_specific_udf_map)
        self.name = name
        self.well = well
        self.container = well.container
        self.sample = sample
        self.id = id
        self.concentration = get_and_apply(kwargs, "concentration", None, float)
        self.target_concentration = get_and_apply(kwargs, "target_concentration", None, float)
        self.volume = get_and_apply(kwargs, "volume", None, float)
        self.target_volume = get_and_apply(kwargs, "target_volume", None, float)

    def __repr__(self):
        return "{} ({})".format(self.name, self.id)

    @staticmethod
    def create_from_rest_resource(resource, udf_map, container_repo):
        """
        Creates an Analyte from the rest resource. By default, the container
        is created from the related container resource, except if one
        already exists in the container map. This way, there will be created
        only one container object for each id
        """
        container = container_repo.get_container(resource.location[0])

        # Map UDFs (which may be using different names in different Clarity setups)
        # to a key-value list with well-defined key names:
        analyte_udf_map = udf_map["Analyte"]
        kwargs = {key: resource.udf.get(analyte_udf_map[key], None) for key in analyte_udf_map}
        pos = ContainerPosition.create(resource.location[1])
        well = Well(pos, container)
        sample = Sample.create_from_rest_resource(resource.samples[0])
        analyte = Analyte(resource, resource.name, well, sample, analyte_udf_map, resource.id, **kwargs)
        analyte.api_resource = resource
        well.artifact = analyte
        return analyte

    def updated_rest_resource(self, original_rest_resource, udf_map, updated_fields):
        """
        :param original_rest_resource: The rest resource in the state as in the api cache
        :param udf_map: global udf map for all entities
        :return: An updated rest resource according to changes in this instance of Analyte
        """
        # TODO: Update udfs that is not present in the original xml received from db
        # A ticket is sent to Clarity support (160902)
        _updated_rest_resource = original_rest_resource
        # TODO: This implementation is not ready! Implementation is moved to another ticket
        # in Jira

        # Update udf values
        analyte_udf_map = udf_map['Analyte']
        values_by_udf_names = {analyte_udf_map[key]: self.__dict__[key]
                               for key in analyte_udf_map if key in updated_fields}
        # Retrieve fields that are updated, only these field should be included in the rest update
        for key in values_by_udf_names:
            if _updated_rest_resource.udf.get(key, None):
                original_type = type(_updated_rest_resource.udf[key])
                value = get_and_apply(values_by_udf_names, key, None, original_type)
                _updated_rest_resource.udf[key] = self.assigner.log_assign(key, value)

        # Update other fields
        if 'name' in updated_fields:
            _updated_rest_resource.name = self.assigner.log_assign('name', self.name)
        return _updated_rest_resource, self.assigner.consume()


class Sample(DomainObjectMixin):
    def __init__(self, sample_id):
        self.id = sample_id

    def __repr__(self):
        return "<Sample id={}>".format(self.id)

    @staticmethod
    def create_from_rest_resource(resource):
        sample = Sample(resource.id)
        return sample

