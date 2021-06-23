from clarity_ext.domain.udf import DomainObjectWithUdf, UdfMapping


class Process(DomainObjectWithUdf):
    """Represents a Process (step)"""

    def __init__(self, api_resource, process_id, technician,
            udf_map=None, ui_link=None, instrument=None):
        super(Process, self).__init__(api_resource, process_id, udf_map)
        self.technician = technician
        self.ui_link = ui_link
        self.instrument = instrument

    # def __eq__(self, other):
    #     def lab_eq(a, b):
    #         return (

    #     def technician_eq(a, b):
    #         return (a.first_name == b.first_name and
    #                 a.last_name == b.last_name and
    #                 a.phone == b.phone and
    #                 a.fax == b.fax and
    #                 a.email == b.email and
    #                 a.initials == b.initials and




    # first_name  = StringDescriptor('first-name')
    # last_name   = StringDescriptor('last-name')
    # phone       = StringDescriptor('phone')
    # fax         = StringDescriptor('fax')
    # email       = StringDescriptor('email')
    # initials    = StringDescriptor('initials')
    # lab         = EntityDescriptor('lab', Lab)
    # udf         = UdfDictionaryDescriptor()
    # udt         = UdtDictionaryDescriptor()
    # externalids = ExternalidListDescriptor()

    # # credentials XXX
    # username = NestedStringDescriptor('username', 'credentials')
    # account_locked = NestedBooleanDescriptor('account-locked', 'credentials')


# class Lab(Entity):
    # "Lab; container of researchers."

    # _URI = 'labs'
    # _PREFIX = 'lab'

    # name             = StringDescriptor('name')
    # billing_address  = StringDictionaryDescriptor('billing-address')
    # shipping_address = StringDictionaryDescriptor('shipping-address')
    # udf              = UdfDictionaryDescriptor()
    # udt              = UdtDictionaryDescriptor()
    # externalids      = ExternalidListDescriptor()
    # website          = StringDescriptor('website')





        return (super().__eq__(other) and
                compare_technician(self.technician, other.technician) and
                self.ui_link == other.ui_link and
                self.instrument == other.instrument)

    @staticmethod
    def create_from_rest_resource(resource):
        udf_map = UdfMapping(resource.udf)

        # TODO: Move to mapper!
        from clarity_ext.service.process_service import ProcessService
        process_service = ProcessService()
        ui_link = process_service.ui_link_process(resource)
        instrument = None
        if resource.instrument:
            instrument = resource.instrument.name
        ret = Process(resource,
                      resource.id,
                      Technician.create_from_resource(resource.technician),
                      udf_map,
                      ui_link, instrument)
        return ret


class ProcessType(object):
    # TODO: The process type defined in pip/genologics doesn't have all the entries defined
    # We currently need only a few of these, but it would make sense to update
    # it there instead.

    def __init__(self, process_outputs, process_type_id, name):
        self.id = process_type_id
        self.process_outputs = process_outputs
        self.name = name

    @staticmethod
    def create_from_resource(resource):
        outputs = resource.root.findall("process-output")
        process_outputs = [ProcessOutput.create_from_element(
            output) for output in outputs]
        return ProcessType(process_outputs, resource.id, resource.name)


class ProcessOutput(object):
    """Defines the artifact output generated in a process"""

    def __init__(self, artifact_type, output_generation_type, field_definitions):
        self.artifact_type = artifact_type
        self.output_generation_type = output_generation_type
        self.field_definitions = field_definitions

    @staticmethod
    def create_from_element(element):
        fields = [f.attrib["name"]
                  for f in element.findall("field-definition")]
        return ProcessOutput(element.find("artifact-type").text,
                             element.find("output-generation-type").text,
                             fields)

    def __repr__(self):
        return "{}/{}".format(self.artifact_type, self.output_generation_type)
