import math
import logging


class UnitConversion:
    NANO = -9
    PICO = -12

    MAPPING = {
        NANO: "n",
        PICO: "p"
    }

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def convert(self, value, unit_from, unit_to):
        if unit_from == unit_to:
            return value

        factor = math.pow(10, unit_from - unit_to)
        ret = value * factor
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Original: {} {}, Factor: {}, New: {} {}".format(
                value, self.MAPPING[unit_from], factor, ret, self.MAPPING[unit_to]))
        return ret

    def unit_to_string(self, unit):
        return self.MAPPING[unit]

