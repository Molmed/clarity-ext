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

    def __init__(self, api_resource, name=None, well=None, sample=None, id=None, **kwargs):
        """
        Creates an analyte
        """
        super(self.__class__, self).__init__(api_resource)
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
        analyte = Analyte(resource, resource.name, well, sample, resource.id, **kwargs)
        analyte.api_resource = resource
        well.artifact = analyte
        return analyte


class Sample(DomainObjectMixin):
    def __init__(self, sample_id):
        self.id = sample_id

    def __repr__(self):
        return "<Sample id={}>".format(self.id)

    @staticmethod
    def create_from_rest_resource(resource):
        sample = Sample(resource.id)
        return sample

