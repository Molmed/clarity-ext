from clarity_ext.domain.common import DomainObject
from .shared import DomainObjectTestCase
from clarity_ext.domain.common import AssignLogger


class TestDomainObject(DomainObjectTestCase):
    __test__ = True

    def create_instance(self, the_id):
        ret = DomainObject(id=the_id)
        return ret

    def create_first_instance(self):
        return self.create_instance(1)

    def create_second_instance(self):
        return self.create_instance(2)


class TestAssignLogger(DomainObjectTestCase):
    __test__ = True

    def create_instance(self, the_id):
        obj = DomainObject(the_id)
        ret = AssignLogger(obj)
        return ret

    def create_first_instance(self):
        return self.create_instance(1)

    def create_second_instance(self):
        return self.create_instance(2)
