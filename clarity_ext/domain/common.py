import copy
# from abc import ABCMeta, abstractmethod

# SLOWNESS BUG: the problem is eventually in this code. It could be fixed somewhere further down
# the stack, but I think it's better to fix it here.

# Affected:
# class DomainObject(object): Implemented
#   class AssignLogger(DomainObject): Implemented
#   class DomainObjectWithUdf(DomainObject)
#     class Process(DomainObjectWithUdf)
#     class Artifact(DomainObjectWithUdf)
#       class SharedResultFile(Artifact)
#       class Aliquot(Artifact)
#         class Analyte(Aliquot):
#         class ResultFile(Aliquot):
#     class Container(DomainObjectWithUdf)
#     class Sample(DomainObjectWithUdf)
#     class Project(DomainObjectWithUdf)
#   class Well(DomainObject)

class DomainObject(object):
    def __init__(self, id):
        self.id = id

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.id < other.id


class AssignLogger(DomainObject):
    """
    Wraps a DomainObject
    """

    def __init__(self, domain_object):
        self.log = []
        self.domain_object = domain_object

    @property
    def id(self):
        return self.domain_object.id

    def __eq__(self, other):
        return self.domain_object == other.domain_object

    def __ne__(self, other):
        return self.domain_object.__ne__(other)

    def __lt__(self, other):
        return self.domain_object.id < other.domain_object_mixin.id

    def register_assign(self, field_name, value):
        class_name = self.domain_object.__class__.__name__
        lims_id = self.domain_object.id
        self.log.append((class_name, lims_id, field_name, str(value)))
        return value

    def consume(self):
        log_output = copy.copy(self.log)
        self.log = []
        return log_output


class ConfigurationException(Exception):
    """An exception occurred that has to do with the configuration of the LIMS system"""
    pass
