from collections import namedtuple
from clarity_ext.utils import lazyprop


class Well:
    """Encapsulates a well in a plate"""
    def __init__(self, position, plate, artifact_name=None, artifact_id=None):
        self.position = position
        self.plate = plate
        self.artifact_name = artifact_name
        self.artifact_id = artifact_id

    @property
    def is_empty(self):
        return self.artifact_name is None

    def get_key(self):
        return "{}:{}".format(self.position.row, self.position.col)

    def __repr__(self):
        return "{}:{}".format(self.position.row, self.position.col)

    def __str__(self):
        return "{} name={}, id={}".format(self.get_key().ljust(5, ' '), self.artifact_name,
                                          self.artifact_id)

    @property
    def index_down_first(self):
        # The position is 1-indexed
        return (self.position.col - 1) * self.plate.size.height + self.position.row


class PlatePosition(namedtuple("PlatePosition", ["row", "col"])):
    """Defines the position of the plate, (zero based)"""
    def __repr__(self):
        return "{}:{}".format(self.row_letter, self.col)

    @staticmethod
    def create(repr):
        """
        Creates a PlatePosition from different representations. Supported formats:
            "<row as A-Z>:<col as int>"
            "<row as int>:<col as int>"
            (<row>, <col>)
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
        return PlatePosition(row=row, col=col)

    @property
    def row_letter(self):
        """Returns the letter representation for the row index, e.g. 3 => C"""
        return chr(65 + self.row - 1)


class PlateSize(namedtuple("PlateSize", ["height", "width"])):
    """Defines the size of a plate"""
    pass


class Container:
    """Encapsulates a Container"""

    DOWN_FIRST = 1
    RIGHT_FIRST = 2

    CONTAINER_TYPE_96_WELLS_PLATE = 100
    CONTAINER_TYPE_STRIP_TUBE = 200

    def __init__(self, mapping=None, container_type=None):
        """
        :param mapping: A dictionary-like object containing mapping from well
        position to content. It can be non-complete.
        :return:
        """
        self.mapping = mapping
        self.container_type = container_type
        self.size = None

        if self.container_type == self.CONTAINER_TYPE_96_WELLS_PLATE:
            self.size = PlateSize(height=8, width=12)
        elif self.container_type == self.CONTAINER_TYPE_STRIP_TUBE:
            self.size = PlateSize(height=8, width=1)
        else:
            self.size = None

    @classmethod
    def create_from_rest_resource(cls, resource, artifacts):
        """
        Creates a container based on a resource from the REST API
        """
        # TODO: This needs to be cleaned up, i.e. how exactly the rest resource and domain objects should interact
        ret = Container()
        ret.rest_resource = resource
        ret.size = PlateSize(width=resource.type.x_dimension["size"], height=resource.type.y_dimension["size"])
        for artifact in artifacts:
            ret.set_well(artifact.location[1], artifact.name, artifact.id)
        return ret

    @lazyprop
    def wells(self):
        ret = dict()
        for row, col in self._traverse():
            key = "{}:{}".format(row, col)
            content = self.mapping[key] if self.mapping and key in self.mapping else None
            pos = PlatePosition(row=row, col=col)
            ret[(row, col)] = Well(pos, content)
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

    def set_well(self, well_pos, artifact_name, artifact_id=None):
        """
        well_pos should be a string in the format 'B:1'
        """
        if type(well_pos) is str:
            row, col = well_pos.split(":")
            try:
                well_pos = int(row), int(col)
            except ValueError:
                # Try to parse as "A:1" etc
                row = ord(row.upper()) - 64
                well_pos = row, int(col)

        if well_pos not in self.wells:
            raise KeyError("Well id {} is not available in this container (type={})".format(well_pos, self))

        self.wells[well_pos].artifact_name = artifact_name
        self.wells[well_pos].artifact_id = artifact_id


class Plate:
    """Encapsulates a Plate"""

    DOWN_FIRST = 1
    RIGHT_FIRST = 2

    PLATE_TYPE_96_WELLS = 1

    def __init__(self, mapping=None, plate_type=None):
        """
        :param mapping: A dictionary-like object containing mapping from well
        position to content. It can be non-complete.
        :return:
        """
        self.mapping = mapping
        self.plate_type = plate_type
        self.size = None

        if self.plate_type == self.PLATE_TYPE_96_WELLS:
            self.size = PlateSize(height=8, width=12)
        else:
            self.size = None

    @lazyprop
    def wells(self):
        ret = dict()
        for row, col in self._traverse():
            key = "{}:{}".format(row, col)
            content = self.mapping[key] if self.mapping and key in self.mapping else None
            pos = PlatePosition(row=row, col=col)
            ret[(row, col)] = Well(pos, content)
        return ret

    def _traverse(self, order=DOWN_FIRST):
        """Traverses the well in a certain order, yielding keys as (row,col) tuples"""

        # TODO: Provide support for other formats (plate_type is ignored)
        # TODO: Make use of functional prog. - and remove dup.
        # TODO: NOTE! RIGHT_FIRST/DOWN_FIRST where switched. Fix all scripts before checking in.
        if order == self.RIGHT_FIRST:
            for row in "ABCDEFGH":
                for col in range(1, 13):
                    yield (row, col)
        else:
            for col in range(1, 13):
                for row in "ABCDEFGH":
                    yield (row, col)

    # Lists the wells in a certain order:
    def enumerate_wells(self, order=DOWN_FIRST):
        for key in self._traverse(order):
            yield self.wells[key]

    def list_wells(self, order=DOWN_FIRST):
        return list(self.enumerate_wells(order))

    def set_well(self, well_id, artifact_name, artifact_id=None):
        """
        well_id should be a string in the format 'B:1'
        """
        if type(well_id) is str:
            split = well_id.split(":")
            well_id = split[0], int(split[1])

        if well_id not in self.wells:
            raise KeyError("Well id {} is not available in this plate".format(well_id))

        # TODO: Change the parameter to accepting a Well class instead
        self.wells[well_id].artifact_name = artifact_name
        self.wells[well_id].artifact_id = artifact_id

