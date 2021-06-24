from copy import copy


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
        self.id == other.id

    # TEMPORARY: Allow all domain objects to be hashable, even if we define eq, because
    # equality check is based only on the id
    def __hash__(self):
        return hash(self.id)

    def __lt__(self, other):
        return self.id < other.id

    def __ne__(self, other):
        return not self.__eq__(other)


class AssignLogger(DomainObject):
    def __init__(self, domain_object):
        self.log = []
        self.domain_object = domain_object

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


class HashableDomainObjectWrapper:
    """
    comment!
    """

    def __init__(self, domain_object: DomainObject):
        self.domain_object = domain_object

    def __hash__(self) -> int:
        return hash(self.domain_object.id)


class PromiseNonMutableDomainObjectsSet:
    def __init__(self, lst):
        # The elements of the lst are mutable, but the developer promises that they will not
        # be mutated while this set is in scope and that the ID makes them unique, i.e. the
        # lst will never have an element which is
        self.set = set(HashableDomainObjectWrapper(element) for element in lst)

    def __iter__(self):
        for element in self.set:
            yield element.domain_object


def domain_object_set(lst):
    return PromiseNonMutableDomainObjectsSet(lst)
