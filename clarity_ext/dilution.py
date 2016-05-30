from domain import *


class Dilute:
    # Enclose sample data, user input and derived variables for a
    # single row in a dilution
    def __init__(self, input_analyte, output_analyte):
        self.target_concentration = output_analyte.target_concentration
        self.target_volume = output_analyte.target_volume
        self.source_well = input_analyte.well
        self.source_container = input_analyte.container
        self.target_well = output_analyte.well
        self.target_container = output_analyte.container
        self.sample_name = output_analyte.name
        self.source_concentration = input_analyte.concentration
        self.sample_volume = None
        self.buffer_volume = None
        self.source_well_index = None
        self.source_plate_pos = None
        self.target_well_index = None
        self.target_plate_pos = None
        self.has_to_evaporate = None


class RobotDeckPositioner:
    """
    Handle plate positions on the robot deck (target and source)
    as well as well indexing
     """
    def __init__(self, robot_name, dilutes, plate):
        self.robot_name = robot_name
        self.plate = plate
        index_method_map = {"Hamilton": lambda well: well.index_down_first}
        self.indexer = index_method_map[robot_name]
        self.target_plate_sorting_map = self._build_plate_sorting_map(
            [dilute.target_container for dilute in dilutes])
        self.target_plate_position_map = self._build_plate_position_map(
            self.target_plate_sorting_map, "END"
        )
        self.source_plate_sorting_map = self._build_plate_sorting_map(
            [dilute.source_container for dilute in dilutes])
        self.source_plate_position_map = self._build_plate_position_map(
            self.source_plate_sorting_map, "DNA"
        )

    def find_sort_number(self, dilute):
        """Sort dilutes according to plate and well positions in source
        :param dilute:
        """
        plate_base_number = self.plate.size.width * self.plate.size.height + 1
        plate_sorting = self.source_plate_sorting_map[
            dilute.source_container.id]
        # Sort order for wells are always based on down first indexing
        # regardless the robot type
        return plate_sorting * plate_base_number + dilute.source_well.index_down_first


    @staticmethod
    def _build_plate_position_map(plate_sorting_map, plate_pos_prefix):
        # Fetch an unique list of container names from input
        # Make a dictionary with container names and plate positions
        # eg. END1, DNA2
        plate_positions = []
        for key, value in plate_sorting_map.iteritems():
            plate_position = "{}{}".format(plate_pos_prefix, value)
            plate_positions.append((key, plate_position))

        plate_positions = dict(plate_positions)
        return plate_positions

    @staticmethod
    def _build_plate_sorting_map(containers):
        # Fetch an unique list of container names from input
        # Make a dictionary with container names and plate position sort numbers
        unique_containers = sorted(list(
            {container.id for container in containers}))
        positions = range(1, len(unique_containers) + 1)
        plate_position_numbers = dict(zip(unique_containers, positions))
        return plate_position_numbers

    def __str__(self):
        return "<{type} {robot} {rows}x{cols}>".format(type=self.__class__.__name__,
                                                       robot=self.robot_name,
                                                       rows=self.plate_size_y,
                                                       cols=self.plate_size_x)

PLATE_TYPE_96_WELL = 1


class DilutionScheme:
    """Creates a dilution scheme, given input and output analytes."""

    def __init__(self, matched_analytes, robot_name, plate):
        """Calculates all derived values needed in dilute driver file """

        self.dilutes = self._init_dilutes(matched_analytes)
        self.robot_deck_positioner = RobotDeckPositioner(
            robot_name, self.dilutes, plate)

        for dilute in self.dilutes:
            dilute.source_well_index = self.robot_deck_positioner.indexer(
                dilute.source_well)
            dilute.source_plate_pos = self.robot_deck_positioner.\
                source_plate_position_map[dilute.source_container.id]
            dilute.sample_volume = \
                dilute.target_concentration * dilute.target_volume / \
                dilute.source_concentration
            dilute.buffer_volume = \
                max(dilute.target_volume - dilute.sample_volume, 0)
            dilute.target_well_index = self.robot_deck_positioner.indexer(
                dilute.target_well)
            dilute.target_plate_pos = self.robot_deck_positioner\
                .target_plate_position_map[
                    dilute.target_container.id]
            dilute.has_to_evaporate = \
                (dilute.target_volume - dilute.sample_volume) < 0

        self._sort_dilutes(self.robot_deck_positioner)

    def _sort_dilutes(self, robot_deck_positioner):
        new_sorting = []
        for dilute in self.dilutes:
            sort_number = robot_deck_positioner.find_sort_number(dilute)
            new_sorting.append((sort_number, dilute))

        new_sorting = sorted(new_sorting)
        (_, dilutes) = zip(*new_sorting)
        self.dilutes = list(dilutes)

    def validate(self):
        """Yields validation errors or warnings"""
        if any(dilute.sample_volume < 2 for dilute in self.dilutes):
            yield ValidationException("Too low sample volume")

        if any(dilute.sample_volume > 50 for dilute in self.dilutes):
            yield ValidationException("Too high sample volume")

        if any(dilute.buffer_volume > 50 for dilute in self.dilutes):
            yield ValidationException("Too high buffer volume")

        if any(dilute.has_to_evaporate for dilute in self.dilutes):
            yield ValidationException("Sample has to be evaporated", ValidationType.WARNING)

    @staticmethod
    def _init_dilutes(matched_analytes):
        dilutes = []
        for in_analyte, out_analyte in matched_analytes:
            dilutes.append(Dilute(in_analyte, out_analyte))
        return dilutes

    def __str__(self):
        return "<DilutionScheme positioner={}>".format(self.robot_deck_positioner)
