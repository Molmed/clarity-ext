from clarity_ext.domain.artifact import Artifact
from clarity_ext.domain.udf import DomainObjectWithUdf


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
                                      mapper=mapper)
        # NOTE: This is a quick fix for extremely slow loading of large pools
        if samples:
            self._samples_require_initializing = not isinstance(samples[0], Sample)
        self._samples = samples

        self.well = well
        if well:
            self.container = well.container
            well.artifact = self
        else:
            self.container = None
        self.is_from_original = False

        self.qc_flag = qc_flag if qc_flag else self.QC_FLAG_UNKNOWN

    @property
    def passed(self):
        return self.qc_flag == self.QC_FLAG_PASSED

    def set_qc_passed(self):
        self.qc_flag = self.QC_FLAG_PASSED

    def set_qc_failed(self):
        self.qc_flag = self.QC_FLAG_FAILED

    @property
    def samples(self):
        if self._samples_require_initializing:
            self._samples = [self._mapper.sample_create_object(sample)
                             for sample in self._samples]
            self._samples_require_initializing = False
        return self._samples

    @samples.setter
    def samples(self, value):
        self._samples = value

    @property
    def is_pool(self):
        if self._samples is None:
            # TODO: Happens only in a test, fix that...
            return False
        return len(self._samples) > 1


class Sample(DomainObjectWithUdf):

    def __init__(self, sample_id, name, project, udf_map=None, mapper=None):
        """
        :param sample_id: The ID of the sample
        :param name: The name of the sample
        :param project: The project domain object
        :param udf_map: An UdfMapping
        :param mapper: The ClarityMapper
        """
        super(Sample, self).__init__(udf_map=udf_map)
        self.id = sample_id
        self.name = name
        self.project = project
        self._mapper = mapper

    def __repr__(self):
        return "<Sample id={}>".format(self.id)


class Project(DomainObjectWithUdf):
    def __init__(self, name):
        self.name = name
