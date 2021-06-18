import copy
from abc import ABCMeta, abstractmethod

# SLOWNESS BUG: the problem is eventually in this code. It could be fixed somewhere further down
# the stack, but I think it's better to fix it here.

# Affected:
# class DomainObjectMixin(object)
#   class AssignLogger(DomainObjectMixin): Implemented
#   class DomainObjectWithUdfMixin(DomainObjectMixin)
#     class Process(DomainObjectWithUdfMixin)
#     class Artifact(DomainObjectWithUdfMixin)
#       class SharedResultFile(Artifact)
#       class Aliquot(Artifact)
#     class Container(DomainObjectWithUdfMixin)
#     class Sample(DomainObjectWithUdfMixin)
#     class Project(DomainObjectWithUdfMixin)
#   class Well(DomainObjectMixin)

class DomainObjectMixin(object, metaclass=ABCMeta):
    def __eq__(self, other):
        return (self.id == other.id and self._equals(other))

    @abstractmethod
    def _equals(self, other):
        """
        Domain class specific equality check. All domain objects must implement this method.
        """

        # We raise here so we'll catch classes that don't clearly specify equality
        raise NotImplementedError()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.id)

    def __lt__(self, other):
        return self.id < other.id


class AssignLogger(DomainObjectMixin):
    def __init__(self, domain_object_mixin):
        self.log = []
        self.domain_object_mixin = domain_object_mixin

    def __eq__(self, other):
        return self.domain_object_mixin == other.domain_object_mixin

    def register_assign(self, field_name, value):
        class_name = self.domain_object_mixin.__class__.__name__
        lims_id = self.domain_object_mixin.id
        self.log.append((class_name, lims_id, field_name, str(value)))
        return value

    def consume(self):
        log_output = copy.copy(self.log)
        self.log = []
        return log_output


class ConfigurationException(Exception):
    """An exception occurred that has to do with the configuration of the LIMS system"""
    pass
