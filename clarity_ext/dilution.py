import copy
from clarity_ext.utils import get_and_apply
from itertools import groupby
from clarity_ext.dilution_strategies import *

DILUTION_WASTE_VOLUME = 1
PIPETTING_MAX_VOLUME = 50
CONCENTRATION_REF_NGUL = 1
CONCENTRATION_REF_NM = 2
VOLUME_CALC_FIXED = 1
VOLUME_CALC_BY_CONC = 2


class TransferEndpoint(object):
    """
    TransferEndpoint wraps an source or destination analyte involved in a dilution
    """
    # TODO: Handle tube racks

    def __init__(self, aliquot, concentration_ref=None):
        self.aliquot_name = aliquot.name
        self.well = aliquot.well
        self.container = aliquot.container
        self.concentration = self._referenced_concentration(
            aliquot=aliquot, concentration_ref=concentration_ref)
        self.volume = aliquot.volume
        self.is_control = False
        if hasattr(aliquot, "is_control"):
            self.is_control = aliquot.is_control
        self.is_from_original = aliquot.is_from_original
        self.requested_concentration = self._referenced_requested_concentration(
            aliquot, concentration_ref)
        self.requested_volume = get_and_apply(
            aliquot.__dict__, "requested_volume", None, float)
        self.well_index = None
        self.plate_pos = None

    def _referenced_concentration(self, aliquot=None, concentration_ref=None):
        if concentration_ref == CONCENTRATION_REF_NGUL:
            return aliquot.concentration_ngul
        elif concentration_ref == CONCENTRATION_REF_NM:
            return aliquot.concentration_nm
        else:
            raise NotImplementedError(
                "Concentration ref {} not implemented".format(
                    concentration_ref)
            )

    def _referenced_requested_concentration(self, aliquot=None, concentration_ref=None):
        if concentration_ref == CONCENTRATION_REF_NGUL:
            return aliquot.requested_concentration_ngul
        elif concentration_ref == CONCENTRATION_REF_NM:
            return aliquot.requested_concentration_nm
        else:
            raise NotImplementedError(
                "Concentration ref {} not implemented".format(
                    concentration_ref)
            )


class SingleTransfer(object):
    # Enclose sample data, user input and derived variables for a
    # single row in a dilution

    def __init__(self, source_endpoint, destination_endpoint=None, pair_id=None):
        self.pair_id = pair_id
        self.aliquot_name = source_endpoint.aliquot_name
        self.is_control = source_endpoint.is_control
        self.is_source_from_original = source_endpoint.is_from_original

        self.source_endpoint = source_endpoint
        self.destination_endpoint = destination_endpoint

        self.source_well = source_endpoint.well
        self.source_container = source_endpoint.container
        self.source_concentration = source_endpoint.concentration
        self.source_initial_volume = source_endpoint.volume
        self.source_well_index = None
        self.source_plate_pos = None

        self.target_aliquot_name = None
        self.target_well = None
        self.target_container = None
        self.requested_concentration = None
        self.requested_volume = None
        self.target_well_index = None
        self.target_plate_pos = None

        if destination_endpoint:
            self.set_destination_endpoint(destination_endpoint)

        self.sample_volume = None
        self.buffer_volume = None
        self.has_to_evaporate = None
        self.scaled_up = False

    def set_destination_endpoint(self, destination_endpoint):
        self.target_well = destination_endpoint.well
        self.target_container = destination_endpoint.container
        self.requested_concentration = destination_endpoint.requested_concentration
        self.requested_volume = destination_endpoint.requested_volume
        self.target_aliquot_name = destination_endpoint.aliquot_name

    def identifier(self):
        source = "source({}, conc={})".format(
            self.source_well, self.source_concentration)
        target = "target({}, conc={}, vol={})".format(self.target_well,
                                                      self.requested_concentration, self.requested_volume)
        return "{} => {}".format(source, target)

    def __str__(self):
        source = "source({}, conc={})".format(
            self.source_well, self.source_concentration)
        target = "target({}, conc={}, vol={})".format(self.target_well,
                                                      self.requested_concentration, self.requested_volume)
        return "{} => {}".format(source, target)

    def __repr__(self):
        return "<SingleTransfer {}>".format(self.aliquot_name)


class EndpointPositioner(object):
    """
    Handles positions for all plates and wells for either source or
    destination placement on a robot deck
    """

    def __init__(self, robot_name, transfer_endpoints, plate_size, plate_pos_prefix):
        self.robot_name = robot_name
        self._plate_size = plate_size
        index_method_map = {"Hamilton": lambda well: well.index_down_first}
        self.indexer = index_method_map[robot_name]
        self.plate_sorting_map = self._build_plate_sorting_map(
            [transfer_endpoint.container for transfer_endpoint in transfer_endpoints])
        self.plate_position_map = self._build_plate_position_map(
            self.plate_sorting_map, plate_pos_prefix)

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

    def find_sort_number(self, transfer):
        """Sort dilutes according to plate and well positions
        """
        plate_base_number = self._plate_size.width * self._plate_size.height + 1
        plate_sorting = self.plate_sorting_map[
            transfer.source_container.id
        ]
        # Sort order for wells are always based on down first indexing
        # regardless the robot type
        return plate_sorting * plate_base_number + transfer.source_well.index_down_first

    def __str__(self):
        return "<{type} {robot} {height}x{width}>".format(type=self.__class__.__name__,
                                                          robot=self.robot_name,
                                                          height=self._plate_size.size.height,
                                                          width=self._plate_size.size.width)


class RobotDeckPositioner(object):
    """
    Handle plate positions on the robot deck (target and source)
    as well as well indexing
    """

    def __init__(self, robot_name, dilutes, plate_size):

        source_endpoints = [dilute.source_endpoint for dilute in dilutes]
        source_positioner = EndpointPositioner(robot_name, source_endpoints,
                                               plate_size, "DNA")
        destination_endpoints = [
            dilute.destination_endpoint for dilute in dilutes]
        destination_positioner = EndpointPositioner(
            robot_name, destination_endpoints, plate_size, "END")

        self._robot_name = robot_name
        self._plate_size = plate_size
        self._source_positioner = source_positioner
        self.indexer = source_positioner.indexer
        self.source_plate_position_map = source_positioner.plate_position_map
        self.target_plate_position_map = destination_positioner.plate_position_map

    def find_sort_number(self, dilute):
        """Sort dilutes according to plate and well positions in source
        """
        return self._source_positioner.find_sort_number(dilute)

    def __str__(self):
        return "<{type} {robot} {height}x{width}>".format(type=self.__class__.__name__,
                                                          robot=self._robot_name,
                                                          height=self._plate_size.height,
                                                          width=self._plate_size.width)


class DilutionScheme(object):
    """Creates a dilution scheme, given input and output analytes."""

    def __init__(self, artifact_service, robot_name, scale_up_low_volumes=True,
                 concentration_ref=None, include_blanks=False, error_log_artifact=None,
                 volume_calc_strategy=None):
        """
        Calculates all derived values needed in dilute driver file.
        """
        self.scale_up_low_volumes = scale_up_low_volumes
        self.error_log_artifact = error_log_artifact
        self.volume_calc_strategy = volume_calc_strategy
        pairs = artifact_service.all_aliquot_pairs()

        # TODO: Is it safe to just check for the container for the first output
        # analyte?
        container = pairs[0].output_artifact.container
        all_transfers = self._create_transfers(
            pairs, concentration_ref=concentration_ref)
        self._transfers = self._filtered_transfers(
            all_transfers=all_transfers, include_blanks=include_blanks)

        self.aliquot_pair_by_transfer = self._map_pair_and_transfers(
            pairs=pairs)
        self.robot_deck_positioner = RobotDeckPositioner(
            robot_name, self._transfers, container.size)

        self.calculate_transfer_volumes()
        self.do_positioning()
        self.split_row_transfers = self.split_up_high_volume_rows(
            self.sort_transfers(self._transfers))
        self.unsplit_transfers = self.sort_transfers(self._transfers)
        self.grouped_transfers = list(self._grouped_transfers())

    def _grouped_transfers(self):
        """
        Sometimes a sample transfer from source A to destination B is
        split up on several rows, due to the max pipetting volume of 50 ul.
        :return: An iterable group of transfers for a common destination well.
        """
        for key, transfer_group in groupby(
                self._transfers, key=lambda t: "{}{}".format(
                    t.target_container, t.target_well.position)):
            yield list(transfer_group)

    def _filtered_transfers(self, all_transfers, include_blanks):
        if include_blanks:
            return all_transfers
        else:
            return list(t for t in all_transfers if t.is_control is False)

    def _create_transfers(self, aliquot_pairs, concentration_ref=None):
        # TODO: handle tube racks
        transfers = []
        for pair in aliquot_pairs:
            source_endpoint = TransferEndpoint(
                pair.input_artifact, concentration_ref=concentration_ref)
            destination_endpoint = TransferEndpoint(
                pair.output_artifact, concentration_ref=concentration_ref)
            transfers.append(SingleTransfer(
                source_endpoint, destination_endpoint, pair_id=id(pair)))
        return transfers

    def _map_pair_and_transfers(self, pairs):
        """
        :param pairs: input artifact --- output artifact pair
        :return: A function returning an artifact pair, given a transfer object
        """
        pair_dict = {id(pair): pair for pair in pairs}

        def pair_by_transfer(transfer):
            by_transfer_dict = {transfer.identifier: pair_dict[
                transfer.pair_id] for transfer in self._transfers}
            return by_transfer_dict[transfer.identifier]
        return pair_by_transfer

    def calculate_transfer_volumes(self):
        # Handle volumes etc.
        self.volume_calc_strategy.calculate_transfer_volumes(
            transfers=self._transfers, scale_up_low_volumes=self.scale_up_low_volumes)

    def split_up_high_volume_rows(self, transfers):
        """
        Split up a transfer between source well x and target well y into
        several rows, if sample volume or buffer volume exceeds 50 ul
        :return:
        """
        split_row_transfers = []
        for transfer in transfers:
            calculation_volume = max(
                self._get_volume(transfer.sample_volume), self._get_volume(transfer.buffer_volume))
            (n, residual) = divmod(calculation_volume, PIPETTING_MAX_VOLUME)
            if residual > 0:
                total_rows = int(n + 1)
            else:
                total_rows = int(n)

            copies = self._create_copies(transfer, total_rows)
            split_row_transfers += copies
            self._split_up_volumes(
                copies, transfer.sample_volume, transfer.buffer_volume)

        return split_row_transfers

    @staticmethod
    def _create_copies(transfer, total_rows):
        """
        Create copies of transfer
        that will cause extra rows in the driver file if
        pipetting volume exceeds 50 ul.
        Initiate both buffer volume and sample volume to zero
        :param transfer: The transfer to be copied
        :param total_rows: The total number of rows needed for a
        transfer between source well x and target well y
        :return:
        """
        copies = [copy.copy(transfer)]
        for i in xrange(0, total_rows - 1):
            t = copy.copy(transfer)
            t.buffer_volume = 0
            t.sample_volume = 0
            copies.append(t)

        return copies

    @staticmethod
    def _split_up_volumes(transfers, original_sample_volume, original_buffer_volume):
        """
        Split up any transferring volume exceeding 50 ul to multiple rows represented by the
         list 'transfers'
        :param transfers: Represents rows in driver file,
        needed for a transfer between source well x and target well y
        :param original_sample_volume: Sample volume first calculated for a single row transfer,
        that might exceed 50 ul
        :param original_buffer_volume: Buffer volume first calculated for a single row transfer,
        that might exceed 50 ul
        :return:
        """
        number_rows = len(transfers)
        for t in transfers:
            # Only split up pipetting volume if the actual volume exceeds
            # max of 50 ul. Otherwise, the min volume of 2 ul might be
            # violated.
            if original_buffer_volume > PIPETTING_MAX_VOLUME:
                t.buffer_volume = float(
                    original_buffer_volume / number_rows)

            if original_sample_volume > PIPETTING_MAX_VOLUME:
                t.sample_volume = float(
                    original_sample_volume / number_rows)

    def sort_transfers(self, transfers):
        def pipetting_volume(transfer):
            return self._get_volume(transfer.buffer_volume) + self._get_volume(transfer.sample_volume)

        def max_added_pip_volume():
            volumes = map(lambda t: (self._get_volume(t.buffer_volume),
                                     self._get_volume(t.sample_volume)), self._transfers)
            return max(map(lambda (buffer_vol, sample_vol): buffer_vol + sample_vol, volumes))

        # Sort on source position, and in case of splitted rows, pipetting
        # volumes. Let max pipetting volumes be shown first
        max_vol = max_added_pip_volume()
        return sorted(
            transfers, key=lambda t: self.robot_deck_positioner.find_sort_number(t) +
            (max_vol - pipetting_volume(t)) / (max_vol + 1.0))

    @staticmethod
    def _get_volume(volume):
        # In cases when some parameter is not set (Source conc, Target concentration
        # or volume), let the error and warnings check in script
        # catch these exceptions
        if not volume:
            return 0
        else:
            return volume

    def do_positioning(self):
        # Handle positioning
        for transfer in self._transfers:
            transfer.source_well_index = self.robot_deck_positioner.indexer(
                transfer.source_well)
            transfer.source_plate_pos = self.robot_deck_positioner. \
                source_plate_position_map[transfer.source_container.id]
            transfer.target_well_index = self.robot_deck_positioner.indexer(
                transfer.target_well)
            transfer.target_plate_pos = self.robot_deck_positioner \
                .target_plate_position_map[transfer.target_container.id]

    def __str__(self):
        return "<DilutionScheme positioner={}>".format(self.robot_deck_positioner)

    @staticmethod
    def create(artifact_service, robot_name, scale_up_low_volumes=True,
               concentration_ref=None, include_blanks=False, error_log_artifact=None,
               volume_calc_method=None, make_pools=False):
        volume_calc_strategy = None

        if volume_calc_method == VOLUME_CALC_FIXED:
            volume_calc_strategy = FixedVolumeCalc()
        elif volume_calc_method == VOLUME_CALC_BY_CONC and make_pools is False:
            volume_calc_strategy = OneToOneConcentrationCalc()
        elif volume_calc_method == VOLUME_CALC_BY_CONC and make_pools is True:
            volume_calc_strategy = PoolConcentrationCalc()
        else:
            raise ValueError(
                "Choice for volume calculation method is not implemented. \n"
                "volume calc method:  {}\n"
                "make pools: {}".format(volume_calc_method, make_pools))

        return DilutionScheme(
            artifact_service=artifact_service, robot_name=robot_name,
            scale_up_low_volumes=scale_up_low_volumes,
            concentration_ref=concentration_ref, include_blanks=include_blanks,
            error_log_artifact=error_log_artifact, volume_calc_strategy=volume_calc_strategy)
