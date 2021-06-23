from clarity_ext.domain.udf import DomainObjectWithUdf
from .shared import DomainObjectTestCase


class TestDomainObjectWithUdf(DomainObjectTestCase):
    __test__ = True

    def create_instance(self, the_id, udf_map_as_dict):
        ret = DomainObjectWithUdf(id=the_id)
        for key, value in udf_map_as_dict.items():
            ret.udf_map.add(key, value)
        return ret

    def create_first_instance(self):
        return self.create_instance(1, dict(key=1))

    def create_second_instance(self):
        return self.create_instance(2, dict(key=2))
