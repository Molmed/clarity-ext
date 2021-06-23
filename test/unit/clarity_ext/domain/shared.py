import unittest
from abc import ABCMeta, abstractmethod
from copy import deepcopy


class DomainObjectTestCase(unittest.TestCase, metaclass=ABCMeta):
    __test__ = False  # Must be set to True when implementing

    @abstractmethod
    def create_first_instance(self):
        raise NotImplementedError()

    @abstractmethod
    def create_second_instance(self):
        """
        Creates an instance that must be different from the one created by create_instance
        """
        raise NotImplementedError()

    def test_two_identical_instances__are_equal(self):
        instance1 = self.create_first_instance()
        instance2 = deepcopy(instance1)
        self.assertEqual(instance1, instance2)

    def test_two_non_identical_instances__are_not_equal(self):
        instance1 = self.create_first_instance()
        instance2 = self.create_second_instance()
        self.assertNotEqual(instance1, instance2)

    def test_instance__is_not_hashable(self):
        instance = self.create_first_instance()
        self.assertIsNone(instance.__hash__)

    # TODO: Sorting?
