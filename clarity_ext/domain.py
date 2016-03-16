class Well:
    """Encapsulates a well in a plate"""
    def __init__(self, row, col, content=None):
        self.row = row
        self.col = col
        self.content = content
        self.row_index_dict = dict(
            [(row_str, row_ind)
             for row_str, row_ind
             in zip("ABCDEFGH", range(0, 7))])

    def get_key(self):
        return "{}:{}".format(self.row, self.col)

    def __repr__(self):
        return "{}:{}".format(self.row, self.col)

    def __str__(self):
        return "{} => {}".format(self.get_key(), self.content)

    def get_coordinates(self):
        # Zero based
        return self.row_index_dict[self.row], int(self.col) - 1


class Plate:
    """Encapsulates a Plate"""

    DOWN_FIRST = 1
    LEFT_FIRST = 2

    def __init__(self):
        self.wells = {}
        # For simplicity, set all wells:
        for well in self._traverse():
            self.wells[well] = Well(well[0], well[1])

    def _traverse(self, order=DOWN_FIRST):
        """Traverses the well in a certain order, yielding keys as (row,col) tuples"""

        # TODO: Provide support for other formats
        # TODO: Make use of functional prog. - and remove dup.
        if order == self.DOWN_FIRST:
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

    def set_well(self, well_id, content):
        """
        well_id should be a string in the format 'B:1'
        """
        if type(well_id) is str:
            split = well_id.split(":")
            well_id = split[0], int(split[1])

        if well_id not in self.wells:
            raise KeyError("Well id {} is not available in this plate".format(well_id))

        self.wells[well_id].content = content

