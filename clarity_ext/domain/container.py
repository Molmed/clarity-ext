from collections import namedtuple
from clarity_ext.utils import lazyprop
from clarity_ext.domain.common import DomainObjectMixin


class Well(DomainObjectMixin):
    """
    Encapsulates a location in a container.

    This could for example be a well in a plate, but could also be the single "location" in a tube.

    NOTE: Sometimes, instances of this class are called "location" as it's more generic than well.
    Consider renaming this class to Location. The exact coordinates (e.g. A:1) are called "position".
    A better name for that might have been "coordinates" or "index" to avoid a potential confusion, as
    location and position can have the same meaning.
    """

    def __init__(self, position, container, artifact=None):
        self.position = position
        self.container = container
        self.artifact = artifact

    @property
    def is_empty(self):
        return self.artifact is None

    def get_key(self):
        return "{}:{}".format(self.position.row, self.position.col)

    def __repr__(self):
        if self.container:
            container_name = self.container.name
        else:
            container_name = '<no container>'
        return "{}({}{}: {})".format(container_name,
                                     self.position.row_letter,
                                     self.position.col,
                                     self.artifact.id if self.artifact is not None else "")

    @property
    def index_down_first(self):
        # The position is 1-indexed
        return (self.position.col - 1) * self.container.size.height + self.position.row

    @property
    def index_right_first(self):
        # The position is 1-indexed
        return (self.position.row - 1) * self.container.size.width + self.position.col


class ContainerPosition(namedtuple("ContainerPosition", ["row", "col"])):
    """
    Defines the position of an item in a container, (zero based)

    Default representation is `<row as letter>:<column as number>`, e.g. `A:1`
    """
    def __repr__(self):
        return "{}:{}".format(self.row_letter, self.col)

    @staticmethod
    def create(repr):
        """
        Creates a ContainerPosition from different representations. Supported formats:
            "<row as A-Z>:<col as int>"
            "<row as int>:<col as int>"
            (<row>, <col>) where both are integers
            (<row>, <col>) where column is a string (e.g. A)
        """
        if isinstance(repr, basestring):
            row, col = repr.split(":")
            if row.isalpha():
                row = ord(row.upper()) - 64
            else:
                row = int(row)
            col = int(col)
        else:
            row, col = repr
            if isinstance(row, basestring):
                row = ContainerPosition.letter_to_index(row)
        return ContainerPosition(row=row, col=col)

    @property
    def row_letter(self):
        """Returns the letter representation for the row index, e.g. 3 => C"""
        return self.index_to_letter(self.row)

    @staticmethod
    def index_to_letter(index):
        return chr(65 + index - 1)

    @staticmethod
    def letter_to_index(letter):
        return ord(letter.upper()) - 64


class PlateSize(namedtuple("PlateSize", ["height", "width"])):
    """Defines the size of a plate"""
    pass


class Container(DomainObjectMixin):
    """Encapsulates a Container"""

    DOWN_FIRST = 1
    RIGHT_FIRST = 2

    CONTAINER_TYPE_96_WELLS_PLATE = "96 well plate"

    def __init__(self, mapping=None, size=None, container_type=None,
                 container_id=None, name=None, is_source=None):
        """
        :param mapping: A dictionary-like object containing mapping from well
        position to content. It can be non-complete.
        :param size: The size of the container. Object should support height and width
        :param container_type: The type of the container (string)
        :return:
        """
        self.mapping = mapping
        # TODO: using both container_type and container_type_name is temporary
        self.container_type = container_type
        self.id = container_id
        self.name = name

        # Set to True if the plate represents no actual plate in Clarity
        self.is_temporary = False

        # Set to True if this is a source container in the current context, False if it's the target
        self.is_source = is_source

        # The container may need to be referenced by a different name, in particular when diluting the container
        # will need a shorter name.
        self.source_ref = None
        self.target_ref = None

        # The index of the container in some context, e.g. the 1st plate being diluted from. Context-specific
        self.index = None

        if size is None:
            size = self.size_from_container_type(container_type)
        assert size is not None
        self.size = size

    def size_from_container_type(self, container_type):
        if container_type == self.CONTAINER_TYPE_96_WELLS_PLATE:
            return PlateSize(height=8, width=12)
        else:
            raise ValueError("Can't initialize container size from plate name {}".format(container_type))

    @property
    def rows(self):
        # Enumerates the row indexes, returning e.g. (A,B,...,H) for a 96 well plate
        for index in xrange(1, self.size.height + 1):
            yield ContainerPosition.index_to_letter(index)

    @property
    def columns(self):
        # Enumerates the column indexes, returning e.g. (1,2,...12) for a 96 well plate
        for index in xrange(1, self.size.width + 1):
            yield index

    @staticmethod
    def create_from_container(container):
        """Creates a container with the same dimensions as the other container"""
        return Container(container_type=container.container_type,
                         size=container.size,
                         is_source=container.is_source)

    @classmethod
    def create_from_rest_resource(cls, resource, api_artifacts=[], is_source=None):
        """
        Creates a container based on a resource from the REST API.
        """
        size = PlateSize(width=resource.type.x_dimension[
                         "size"], height=resource.type.y_dimension["size"])

        ret = Container(size=size, container_type=resource.type.name, is_source=is_source)
        ret.id = resource.id
        ret.name = resource.name
        ret.size = size
        for artifact in api_artifacts:
            ret.set_well(artifact.location[1], artifact)
        ret.api_resource = resource
        return ret

    @lazyprop
    def wells(self):
        ret = dict()
        for row, col in self._traverse():
            key = "{}:{}".format(row, col)
            content = self.mapping[key] if self.mapping and key in self.mapping else None
            pos = ContainerPosition(row=row, col=col)
            ret[(row, col)] = Well(pos, content)
            ret[(row, col)].container = self
        return ret

    def _traverse(self, order=DOWN_FIRST):
        """Traverses the container, visiting wells in a certain order, yielding keys as (row,col) tuples, 1-indexed"""
        if not self.size:
            raise ValueError("Not able to traverse the container without a plate size")

        rows = range(1, self.size.height + 1)
        cols = range(1, self.size.width + 1)
        if order == self.RIGHT_FIRST:
            return ((row, col) for row in rows for col in cols)
        else:
            return ((row, col) for col in cols for row in rows)

    # Lists the wells in a certain order:
    def enumerate_wells(self, order=DOWN_FIRST):
        for key in self._traverse(order):
            yield self.wells[key]

    def list_wells(self, order=DOWN_FIRST):
        return list(self.enumerate_wells(order))

    def set_well(self, well_pos, artifact=None):
        # We should support any position that ContainerPosition can handle:
        if not isinstance(well_pos, ContainerPosition):
            well_pos = ContainerPosition.create(well_pos)

        if well_pos not in self.wells:
            raise KeyError(
                "Well id {} is not available in this container (type={})".format(well_pos, self))

        self.wells[well_pos].artifact = artifact
        if artifact and not artifact.container:
            artifact.container = self

        if not artifact.well:
            artifact.well = self.wells[well_pos]
        return self.wells[well_pos]

    def __iter__(self):
        return self.enumerate_wells(order=self.DOWN_FIRST)

    def __setitem__(self, key, value):
        self.set_well(key, artifact=value)

    def __contains__(self, item):
        return item in self.wells

    def __getitem__(self, well_pos):
        if not isinstance(well_pos, ContainerPosition):
            well_pos = ContainerPosition.create(well_pos)
        return self.wells[well_pos]

    def __repr__(self):
        return "Container(id={})".format(self.id)

