from clarity_ext.domain.udf import UdfMapping
from clarity_ext.domain.aliquot import Project, Sample
from clarity_ext.domain import ResultFile
from clarity_ext.domain import Analyte, Project
from clarity_ext import utils
from clarity_ext.domain.container import ContainerPosition


class ClarityMapper(object):
    """
    Maps Clarity API resources to/from internal domain objects.

    Using a mapper to map between the two domains ensures that the code can stay independent from
    Clarity. This helps in tests as well as by moving logic to other backends if required.

    NOTE:
    Limitation: The API resources should be built from domain objects, but currently, the mapper relies on
    an internal cache, where the API resources are built based on the original values fetched from the API.
    This may severely limit the usability in some cases, e.g. making it impossible to get a resource from a copy
    of a domain object.

    Temporary: Doesn't support all domain objects. Port the factory methods on the domain objects here.
    """

    def __init__(self):
        self.map = dict()

        # Cache of all domain objects, indexed by the ID in the LIMS
        # TODO: Currently just caching analytes 
        self.domain_map = dict()

        # TODO: The container_repo used here could be reused per the lifetime of the mapper instead, and not
        # passed around.
        self.create_resource_by_type = {
            Sample: self.sample_create_resource
        }

    def _after_object_created(self, domain_object, resource):
        # See NOTE above. This mapping is only required while we're still not building the rest resources
        # directly from the domain objects.
        self.map[domain_object] = resource

    def _get_from_cache(self, domain_object):
        if domain_object not in self.map:
            raise Exception("The domain object was not created via the mapper. In this implementation "
                            "resources can only be fetched from the mapper if the object was created via the mapper.")
        return self.map[domain_object]

    def sample_create_object(self, resource):
        project = Project(resource.project.name) if resource.project else None
        udf_map = UdfMapping(resource.udf)
        sample = Sample(resource.id, resource.name, project, udf_map)
        sample.api_resource = resource
        self._after_object_created(sample, resource)
        return sample

    def create_resource(self, domain_object):
        return self.create_resource_by_type[type(domain_object)](domain_object)

    def sample_create_resource(self, sample):
        # TODO: Every domain object should be able to report on changed fields. Use those to reconstruct
        # the object
        resource = self._get_from_cache(sample)

        # TODO: Currently only fetching changed UDFs. Change the domain objects so they can report
        # any changed field.
        self._update_udfs(sample, resource)
        return resource

    def _update_udfs(self, domain_object, resource):
        updated_fields = list(domain_object.udf_map.enumerate_updated())
        if len(updated_fields) == 0:
            return None
        else:
            for udf_info in updated_fields:
                resource.udf[udf_info.key] = udf_info.value
            return resource

    def analyte_create_object(self, resource, is_input, container_repo, process_type):
        """
        Creates an Analyte from the rest resource. By default, the container
        is created from the related container resource, except if one
        already exists in the container map. This way, there will be created
        only one container object for each id
        """
        # Map UDFs (which may be using different names in different Clarity setups)
        # to a key-value list with well-defined key names:
        if resource.id in self.domain_map:
            return self.domain_map[resource.id]

        udfs = None
        if not is_input:
            # Get the process-output section, output_generation_type is either PerInput for regular analytes or
            # PerAllInputs for pools
            per_input_analytes = [process_output for process_output
                                  in process_type.process_outputs
                                  if process_output.artifact_type == "Analyte"]
            process_output = utils.single_or_default(per_input_analytes)
            if process_output:
                udfs = UdfMapping.expand_udfs(resource, process_output)

        if udfs is None:
            udfs = resource.udf

        udf_map = UdfMapping(udfs)

        well = self.well_create_object(resource, container_repo, is_input)

        # TODO: sample should be put in a lazy property, and all samples in a step should be
        # loaded in one batch
        samples = [self.sample_create_object(
            sample) for sample in resource.samples]

        is_control = self._is_control(resource)
        # TODO: A better way to decide if analyte is output of a previous step?
        is_from_original = (resource.id.find("2-") != 0)
        analyte = Analyte(api_resource=resource, is_input=is_input, id=resource.id,
                          samples=samples, name=resource.name,
                          well=well, is_control=is_control,
                          udf_map=udf_map,
                          is_from_original=is_from_original)
        analyte.api_resource = resource
        self._after_object_created(analyte, resource)
        self.domain_map[resource.id] = analyte
        return analyte

    def _is_control(self, api_resource):
        # Pools are here never counted as controls (... samples == 1)
        return api_resource.root.find("control-type") is not None and len(api_resource.samples) == 1

    def analyte_create_resource(self, analyte):
        pass

    def well_create_object(self, resource, container_repo, is_source):
        # TODO: Batch call
        try:
            container = container_repo.get_container(resource.location[0], is_source)
        except AttributeError:
            container = None
        try:
            pos = ContainerPosition.create(resource.location[1])
        except (AttributeError, ValueError):
            pos = None

        well = None
        if container and pos:
            well = container.wells[pos]

        return well

    def well_create_resource(self, well):
        pass

    def result_file_create_object(self, resource, is_input, container_repo, process_type):
        """
        Creates a `ResultFile` from the REST resource object.
        The container is fetched from the container_repo.
        """
        if not is_input:
            # We expect the process_type to define one PerInput ResultFile
            process_output = utils.single([process_output for process_output in process_type.process_outputs
                                           if process_output.output_generation_type == "PerInput" and
                                           process_output.artifact_type == "ResultFile"])
        udfs = UdfMapping.expand_udfs(resource, process_output)
        udf_map = UdfMapping(udfs)

        well = self.well_create_object(resource, container_repo, is_input)

        # TODO: sample should be put in a lazy property, and all samples in a step should be
        # loaded in one batch
        samples = [self.sample_create_object(
            sample) for sample in resource.samples]
        ret = ResultFile(api_resource=resource, is_input=is_input,
                         id=resource.id, samples=samples, name=resource.name, well=well,
                         udf_map=udf_map)
        return ret


class ProjectClarityMapper(object):
    @staticmethod
    def create_resource(obj):
        raise NotImplementedError()

    @staticmethod
    def create_object(resource):
        ret = Project(resource.name)
        ret.api_resource = resource
        ret.id = resource.id
        return ret
