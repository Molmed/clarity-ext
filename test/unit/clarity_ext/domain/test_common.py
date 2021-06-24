import unittest
from clarity_ext.domain.common import DomainObject
from .shared import DomainObjectTestCase
from clarity_ext.domain.common import AssignLogger
from clarity_ext.domain.common import domain_object_set
from copy import deepcopy


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


class TestDomainObjectSet(unittest.TestCase):
    def test_can_create_set(self):
        do1 = DomainObject(1)
        do2 = DomainObject(2)
        do2b = deepcopy(do2)
        lst = [do1, do2, do2b]
        my_set = domain_object_set(lst)

        self.assertEqual(list(sorted(el.id for el in my_set)), [1, 2])

        self.assertEqual(set(domain_object_set()


