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
        if isinstance(other, self.__class__):
            return self._eq_rec(self, other)
        else:
            return False

    def __hash__(self):
        return hash(self.id)

    def __lt__(self, other):
        return self.compare(other) < 0

    def __gt__(self, other):
        return self.compare(other) > 0

    def __le__(self, other):
        return self.compare(other) <= 0

    def __ge__(self, other):
        return self.compare(other) >= 0

    def compare(self, other):
        # Override if needed
        if self._eq_rec(self, other) == 0:
            return 0
        elif str(self) < str(other):
            return -1
        return 1

    #MUTABLE?! (set used in this method)
    def _eq_rec(self, a, b, cache=[]):
        """
        Replaces the == operator because of circulating references (e.g. analyte <-> well)
        Adapted solution taken from
        http://stackoverflow.com/questions/31415844/using-the-operator-on-circularly-defined-dictionaries
        """
        cache = cache + [a, b]
        if isinstance(a, DomainObject):
            a = a.__dict__
        if isinstance(b, DomainObject):
            b = b.__dict__
        if not isinstance(a, dict) or not isinstance(b, dict):
            return a == b

        set_keys = set(a.keys())
        if set_keys != set(b.keys()):
            return False

        for key in set_keys:
            if any(a[key] is i for i in cache):
                continue
            elif any(b[key] is i for i in cache):
                continue
            elif a[key].__class__.__name__ == "MagicMock" and a[key].__class__.__name__ == "MagicMock":
                # TODO: Move this to the tests. The domain objects shouldn't have to directly know about this
                # filter out mocked fields
                continue
            elif not self._eq_rec(a[key], b[key], cache):
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def differing_fields(self, other):
        if isinstance(other, self.__class__):
            ret = []
            for key in self.__dict__:
                if self.__dict__.get(key, None) != other.__dict__.get(key, None):
                    ret.append(key)
            return ret
        else:
            return None


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
