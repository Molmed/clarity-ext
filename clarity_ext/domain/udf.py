import re
from clarity_ext.domain.common import DomainObject
import logging


logger = logging.getLogger(__name__)


# TODO: Ensure that this overrides the equality check too, to take into account the UDF
# map (since we're not adding the udfs to the object, or add them to the object)
class DomainObjectWithUdf(DomainObject):
    def __init__(self, api_resource=None, id=None, udf_map=None):
        super().__init__(id)

        # NOTE: The udf_map must be the first object set,
        # since it's used in __getattr__ and __setattr__
        if udf_map is None:
            udf_map = UdfMapping()
        self.udf_map = udf_map
        self.api_resource = api_resource

    def __getattr__(self, key):
        """Getter that supports access to the extra udf_ attributes"""
        if key != "udf_map" and key.startswith("udf_"):
            if key in self.udf_map:
                return self.udf_map[key].value
            else:
                raise self._create_udf_exception(key)
        else:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        """Setter that supports access to the extra udf_ attributes"""
        if key != "udf_map" and key.startswith("udf_"):
            # If the key is in the udf_map, set it, if not, raise an error that informs of all available UDFs.
            # This disables the default behaviour in Python where users can set any attribute to a domain object
            # in this particular case, since it must be by mistake (the user can still set attributes dynamically
            # if they don't start with udf_)
            if key in self.udf_map:
                self.udf_map[key].value = value
            else:
                raise self._create_udf_exception(key)
        else:
            super(DomainObjectWithUdf, self).__setattr__(key, value)

    def _create_udf_exception(self, key):
        return AttributeError("The udf '{}' does not exist in the udf_map. Available values are: '{}'"
                              .format(key, self.udf_map.usage()))

    def _get_udf_info(self, key):
        """Unwraps the UDF info, but raises an AttributeError on exceptions"""
        try:
            udf_info = self.udf_map.unwrap(key)
            return udf_info
        except UdfMappingNotUniqueException:
            raise AttributeError(key)

    def is_dirty(self):
        """Returns True if the Artifact was updated since it was originally fetched"""
        return sum(1 for _ in self.udf_map.enumerate_updated())

    def get_updated_api_resource(self):
        """
        Creates an updated api resource object based on changed values
        Returns None if the api resource has not updated
        """
        assert self.api_resource is not None

        # TODO: It would be preferable to copy the object, but that didn't work out of the box.
        # The problem now is that if the update doesn't work out,
        # the api resource will not be in sync, which could lead to subtle errors.
        # new_api_resource = copy.deepcopy(self.api_resource)
        new_api_resource = self.api_resource
        updated_fields = list(self.udf_map.enumerate_updated())
        # TODO: This is a patch to allow renaming artifacts. The whole approach to updating needs
        # to be overhauled. Go through the mapper in all cases (as with Sample)
        # and be able to ask the entire domain object if any of its attributes
        # have changed since loading the object from the backend.
        attrib_updates = False

        if self.name != self.api_resource.name:
            attrib_updates = True

        if self.qc_flag != self.api_resource.qc_flag:
            attrib_updates = True
        if len(updated_fields) == 0 and not attrib_updates:
            return None
        else:
            for udf_info in updated_fields:
                new_api_resource.udf[udf_info.key] = udf_info.value
            new_api_resource.name = self.name
            new_api_resource.qc_flag = self.qc_flag
            return new_api_resource


class UdfMapping(object):
    """
    Handles mapping between Clarity UDFs and the domain objects.

    The UdfMapping is semi-dictionary-like (TODO: make fully dictionary-like),

    When a value is fetched, an exception will be raised
    if the key does not uniquely map to a Clarity UDF. If that happens, the user
    can instead either rename the UDF in Clarity or refer to the UDF by its original
    name.
    """
    def __init__(self, original_udf_map=None):
        """
        :param original_udf_map: The original key/value mapping in Clarity, may have
        to be extended for some domain objects to contain all available UDFs
        """
        self.raw_map = dict()  # Mapping from names (both Clarity style and Python style) to UdfInfo
        self.values = set()  # List of unique values
        self.py_names = set()  # A list of the python names for the UDFs
        if original_udf_map:
            self.create_from_dict(original_udf_map)

    def __eq__(self, other):
        return self.values == other.values

    def force(self, key, value):
        """
        In general, users should not add UDFs that are not defined in the UDF map already. In some cases however,
        e.g. when updating UDFs on input artifacts in a step, there is no clean way to add the UDFs to the map
        based on step metadata. The user can then force the UDF by using this method.
        """
        if key not in self:
            self.add(key, None)
        self[key].value = value

    def add(self, key, value):
        if key in self.raw_map:
            raise ValueError("Key already in dictionary {}".format(key))

        # We add a mapping directly from the original key to the (wrapped) value:
        # It should be in a list, since those mapped by pyname will potentially be more
        # than one:
        udf_info = UdfInfo(key, value)
        self.values.add(udf_info)
        self.raw_map[key] = [udf_info]

        # Then, we also fetch the py name, and add that to the raw map too
        py_name = self._automap_name(key)
        self.raw_map.setdefault(py_name, list())
        self.raw_map[py_name].append(udf_info)
        self.py_names.add(py_name)

        # Post: The raw_map will contain a new key that corresponds to the original
        # UDF. It will also contain a mapping from a python name to that exact same
        # value, so fetching by either name will lead to the same results.

    def to_dict(self):
        # Returns a dict of the key/values where the key is the original Clarity key (not the
        # python name):
        return {
            udf_info.key: udf_info.value for udf_info in self.values
        }

    def __getitem__(self, key):
        return self.unwrap(key)

    def __setitem__(self, key, value):
        self.unwrap(key).value = value

    def udf_name_in_lims_ui(self, py_udf):
        return self.raw_map[py_udf][0].key

    def unwrap(self, key):
        """
        First tries to fetch by the original key, raises an exception if there
        are more than one possible values for the key.

        Raises a KeyError if the key is not available in the UDF map
        """
        udf_info = self.raw_map[key]
        if len(udf_info) > 1:
            raise UdfMappingNotUniqueException(key)
        return udf_info[0]

    def create_from_dict(self, udf_dict):
        for key, value in list(udf_dict.items()):
            self.add(key, value)

    def usage(self):
        """Returns a string showing which UDFs are available, using Python names"""
        return ", ".join(self.py_names)

    def enumerate_updated(self):
        return (value for value in self.values if value.is_dirty())

    def __contains__(self, item):
        return item in self.raw_map

    @staticmethod
    def _automap_name(original_udf_name):
        """
        Maps a UDF name from Clarity to one that matches Python naming conventions

        The naming scheme may cause clashes, which would need to be resolved by the
        caller (e.g. by ignoring UDFs that clash, or by throwing an exception)

        Examples:
          'Fragment Lower (bp)' => 'udf_fragment_lower_bp'
          '% Total' => 'udf_total'
        """
        new_name = original_udf_name.lower().replace(" ", "_")
        # Get rid of all non-alphanumeric characters
        new_name = re.sub(r"\W+", "", new_name)
        new_name = "udf_{}".format(new_name)
        # Now ensure that we don't have repeated undercores:
        new_name = re.sub("_{2,}", "_", new_name)
        return new_name

    @staticmethod
    def expand_udfs(api_resource, process_output):
        """Expands udfs for a resouces, given the information in the process output. Handles a usability issue
        in the API, where we don't get values for UDFs that are not defined"""

        # The UDF can be defined either in the api_process' udf dictionary or
        # in the process_output, or both:
        all_udfs = set()
        all_udfs.update([key for key, value in list(api_resource.udf.items())])  # keys() is not available
        all_udfs.update(process_output.field_definitions)
        return {key: api_resource.udf.get(key, None) for key in all_udfs}

    def __repr__(self):
        return str({key: self[key].value for key in self.py_names})


class UdfInfo(object):
    """
    Represents a Udf. Contains the original value as well as the current value.
    """
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self._original_value = self.value

    def is_dirty(self):
        """Returns True if the value has changed since the object was created"""
        return self.value != self._original_value

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __hash__(self):
        return hash(self.__repr__())

    def __repr__(self):
        return self.key


class UdfMappingNotUniqueException(Exception):
    pass
