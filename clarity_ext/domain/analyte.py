from clarity_ext.domain.container import PlatePosition, Well


class Analyte:
    """
    Describes an Analyte in the Clarity LIMS system, including custom UDFs.

    Takes an analyte resource as input.
    """

    def __init__(self, resource, plate):
        self.resource = resource
        self.plate = plate

    # Mapped properties from the underlying resource
    @property
    def name(self):
        return self.resource.name

    # Mapped UDFs
    @property
    def concentration(self):
        return self.resource.udf["Concentration"]

    @property
    def target_concentration(self):
        return float(self.resource.udf["Target Concentration"])

    @property
    def target_volume(self):
        return self.resource.udf["Target Volume"]

    # Other properties
    @property
    def well(self):
        pos = PlatePosition.create(self.resource.location[1])
        return Well(pos, self.plate)

    @property
    def container(self):
        return self.resource.location[0]

    @property
    def sample(self):
        return self.resource.samples[0]

    def __repr__(self):
        return "{} ({})".format(self.name, self.sample.id)

