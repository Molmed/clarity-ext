from clarity_ext.domain.artifact import Artifact
from clarity_ext.domain.udf import DomainObjectWithUdf
from clarity_ext.inversion_of_control.ioc import ioc
from clarity_ext.utils import single


class Aliquot(Artifact):
    """
    NOTE: This class currently acts as a base class for both Analyte and ResultFile. It will be
    merged with Analyte, since the name can cause some confusion as Analytes
    and ResultFiles strictly don't need to be Aliquots, i.e. they can be non-divided copies
    of the original for example. Or, in the case of ResultFile, only a measurement of the original.
    """

    QC_FLAG_PASSED = 'PASSED'
    QC_FLAG_FAILED = 'FAILED'
    QC_FLAG_UNKNOWN = 'UNKNOWN'

    def __init__(self, api_resource, is_input, id=None, samples=None, name=None,
                 well=None, qc_flag=None, udf_map=None, mapper=None):
        super(Aliquot, self).__init__(api_resource=api_resource,
                                      artifact_id=id,
                                      name=name,
                                      udf_map=udf_map,
                                      is_input=is_input,
                                      mapper=mapper,)

        self.well = well
        if well:
            self.container = well.container
            well.artifact = self
        else:
            self.container = None
        self.is_from_original = False
        self.qc_flag = qc_flag if qc_flag else self.QC_FLAG_UNKNOWN
        self._samples = None
        self._sample_resources = samples or list()
        self.reagent_label = single(api_resource.reagent_labels)
        self._init_samples()

    def _init_samples(self):
        for sample_resource in self._sample_resources:
            ioc.app.sample_repository.add_candidate(sample_resource)

    @property
    def passed(self):
        return self.qc_flag == self.QC_FLAG_PASSED

    def set_qc_passed(self):
        self.qc_flag = self.QC_FLAG_PASSED

    def set_qc_failed(self):
        self.qc_flag = self.QC_FLAG_FAILED

    @property
    def samples(self):
        if self._samples is None:
            self._samples = ioc.app.sample_repository.get_samples(self._sample_resources)
        return self._samples

    @property
    def is_pool(self):
        return len(self._sample_resources) > 1


class Sample(DomainObjectWithUdf):

    def __init__(self, sample_id, name, project, udf_map=None, mapper=None):
        """
        :param sample_id: The ID of the sample
        :param name: The name of the sample
        :param project: The project domain object
        :param udf_map: An UdfMapping
        :param mapper: The ClarityMapper
        """
        super(Sample, self).__init__(udf_map=udf_map, id=sample_id)
        self.name = name
        self.project = project
        self._mapper = mapper

    def __repr__(self):
        return "<Sample id={}>".format(self.id)


class Project(DomainObjectWithUdf):
    def __init__(self, name, udf_map=None):
        super().__init__(udf_map=udf_map)
        self.name = name
