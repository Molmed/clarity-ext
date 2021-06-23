from .shared import DomainObjectTestCase
from clarity_ext.domain.process import Process
from unittest.mock import MagicMock


class TestProcess(DomainObjectTestCase):
    __test__ = True

    def create_instance(self, the_id, udf_map_as_dict):
        ret = Process(MagicMock(), the_id, MagicMock())
        for key, val in udf_map_as_dict.items():
            ret.udf_map.add(key, val)
        return ret

    def create_first_instance(self):
        return self.create_instance(1, dict(udf=1))

    def create_second_instance(self):
        return self.create_instance(2, dict(udf=2))

    def test_custom(self):
        a = self.create_instance(1, dict(udf=1))
        b = self.create_instance(1, dict(udf=1))
        assert a == b
