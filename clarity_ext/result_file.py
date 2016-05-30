class ResultFile:
    """Encapsulates a ResultFile in Clarity"""
    def __init__(self, api_resource, units):
        self.api_resource = api_resource
        self.units = units

    def commit(self):
        self.api_resource.put()

    def set_udf(self, name, value, from_unit=None, to_unit=None):
        if from_unit:
            value = self.units.convert(value, from_unit, to_unit)
        self.api_resource.udf[name] = value

