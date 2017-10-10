import abc
import copy
import logging
from itertools import groupby
from itertools import izip_longest
import collections
from collections import namedtuple
from clarity_ext.service.file_service import Csv
from clarity_ext.domain.validation import ValidationException, ValidationType, ValidationResults, UsageError
from clarity_ext import utils
from clarity_ext.domain import Container, Well


class DilutionService(object):
    def __init__(self, validation_service, logger=None):
        self.validation_service = validation_service
        self.logger = logger or logging.getLogger(__name__)

    def create_session(self, robots, dilution_settings, context, transfer_handler_types, transfer_batch_handler_types):
        """
        Creates a DilutionSession based on the settings. Call evaluate to validate the entire session
        with a particular batch of objects.

        A DilutionSession contains several TransferBatch objects that need to be evaluated together
        """
        session = DilutionSession(self, robots, dilution_settings, self.validation_service,
                                  context, transfer_handler_types, transfer_batch_handler_types)
        return session


class DilutionSession(object):
    """
    Encapsulates an entire dilution session, including validation of the dilution, generation of robot driver files
    and updating values.
    """

    def __init__(self, dilution_service, robots, dilution_settings,
                 validation_service, context, transfer_handler_types, transfer_batch_handler_types, logger=None):
        """
        Initializes a DilutionSession object for the robots.

        :param dilution_service: A service providing methods for creating batches
        :param robots: A list of RobotSettings objects
        :param dilution_settings: The list of settings to apply for the dilution
        :param validation_service: The service that handles the results of validation exceptions
        :param context: The context the session is being created in
        :param transfer_handler_types: A list of handlers that transform the SingleTransfer objects
        :param transfer_batch_handler_types: A list of handlers that execute on a transfer batch as a whole
        :param logger: An optional logger. If None, the default logger is used.
        """
        self.dilution_service = dilution_service
        self.robot_settings_by_name = {robot.name: robot for robot in robots}
        self.dilution_settings = dilution_settings
        self.robot_settings = robots
        self._driver_files = dict()  # A dictionary of generated driver files
        self.validation_results = None
        self.transfer_batches_by_robot = None
        self.pairs = None  # These are set on evaluation
        self.validation_service = validation_service
        self.context = context
        self.logger = logger or logging.getLogger(__name__)
        self.transfer_handler_types = transfer_handler_types
        self.transfer_batch_handler_types = transfer_batch_handler_types
        self.map_temporary_container_by_original = dict()

    def evaluate(self, pairs):
        """Refreshes all calculations for all registered robots and runs registered handlers and validators."""
        self.pairs = pairs
        self.transfer_batches_by_robot = dict()
        for robot_settings in self.robot_settings_by_name.values():
            self.transfer_batches_by_robot[robot_settings.name] = self.create_batches(self.pairs, robot_settings)

    def init_handlers(self, transfer_handler_types, batch_handler_types,
                      dilution_settings, robot_settings, virtual_batch):
        """
        Initializes the transfer handlers for a particular robot and dilution settings

        Lists of handlers are implicitly understood to be short-circuited ORs.
        """
        transfer_handlers = list()
        for transfer_handler_type in transfer_handler_types:
            if isinstance(transfer_handler_type, collections.Iterable):
                initialized = [t(self, dilution_settings, robot_settings, virtual_batch)
                               for t in transfer_handler_type]
                transfer_handlers.append(OrTransferHandler(self, dilution_settings, robot_settings,
                                                           virtual_batch, *initialized))
            else:
                transfer_handlers.append(transfer_handler_type(self, dilution_settings, robot_settings, virtual_batch))

        batch_handlers = list()
        for batch_handler_type in batch_handler_types:
            batch_handlers.append(batch_handler_type(self, dilution_settings, robot_settings, virtual_batch))
        return transfer_handlers, batch_handlers

    def get_temporary_container(self, target_container, prefix):
        """Returns the temporary container that should be used rather than the original one, when splitting transfers"""
        if target_container.id not in self.map_temporary_container_by_original:
            temp_container = Container.create_from_container(target_container)
            temp_container.id = "{}{}".format(prefix, len(self.map_temporary_container_by_original) + 1)
            temp_container.name = temp_container.id
            self.map_temporary_container_by_original[target_container.id] = temp_container
        return self.map_temporary_container_by_original[target_container.id]

    def _evaluate_transfer_route_rec(self, current, transfer_handlers, handler_ix):
        if handler_ix == len(transfer_handlers):
            return
        handler = transfer_handlers[handler_ix]
        self.logger.debug("Evaluating handler #{}, {} on {}".format(handler_ix, handler,
                                                                    current.transfer.source_location))
        self.logger.debug("- In:   {}".format(current))
        current.children = handler.run(current)  # Run will always return a list of TransferRouteNodes
        if self.logger.isEnabledFor(logging.DEBUG):
            for ix, child in enumerate(current.children):
                self.logger.debug("- Out{}: {}".format(ix, child))

        # Stop processing this transfer if there are any validation errors (warnings are OK)
        if len(current.transfer.validation_results.errors) > 0:
            return
        for child in current.children:
            self._evaluate_transfer_route_rec(child, transfer_handlers, handler_ix + 1)

    def evaluate_transfer_route(self, transfer, transfer_handlers):
        """Runs the calculation handlers on the transfer, returning a list of one or two transfers (if split)"""
        root = TransferRouteNode(transfer)
        self._evaluate_transfer_route_rec(root, transfer_handlers, 0)
        return TransferRoute(root, transfer_handlers)

    def create_batches(self, pairs, robot_settings):
        # Create the original "virtual" transfers. These represent what we would like to happen:
        transfers = self.create_transfers_from_pairs(pairs)
        virtual_batch = TransferBatch(transfers, robot_settings)

        # Now evaluate the actual transfer route we need to take for each transfer in order
        # to create the "virtual batch". These will depend on the actual values, which robot this will run on
        # as well as the handlers and settings.
        transfer_handlers, batch_handlers = self.init_handlers(self.transfer_handler_types,
                                                               self.transfer_batch_handler_types,
                                                               self.dilution_settings,
                                                               robot_settings,
                                                               virtual_batch)
        transfer_routes = dict()

        # Evaluate the transfers, i.e. execute all handlers. This does not group them into transfer batches yet
        for transfer in transfers:
            route = self.evaluate_transfer_route(transfer, transfer_handlers)
            transfer_routes[transfer] = route

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Calculated transfer routes:")
            for route in transfer_routes.values():
                self.logger.debug(str(route))

        # NOTE: the transfer_routes dictionary now contains detailed information about which route each transfer
        # takes so it should be easy to debug. We could add this to the metadata as extra info, but currently
        # it's just disposed of (but can be used for debugging). Note also that it intentionally takes copies of
        # each transfer.

        # Now group all evaluated transfers together into a batch
        transfer_by_batch = dict()

        for transfer_route in transfer_routes.values():
            for transfer in transfer_route.transfers:
                transfer_by_batch.setdefault(transfer.batch, list())
                transfer_by_batch[transfer.batch].append(transfer)

        transfer_batches = TransferBatchCollection(robot_settings.transfer_batch_sort_key)
        for key in transfer_by_batch:
            depth = 0 if key == "default" else 1  # TODO Used?
            is_temporary = key != "default"  # and this?
            transfer_batches.append(TransferBatch(transfer_by_batch[key], depth, is_temporary, key))

        # Run transfer_batch handlers, these might for example validate an entire batch
        for batch_handler in batch_handlers:
            for batch in transfer_batches:
                batch_handler.handle_batch(batch)

        # Push all validation results over to the validation_service
        for batch in transfer_batches:
            self.validation_service.handle_validation(batch.validation_results)

        include_step_prefix = len(transfer_batches) > 1
        for ix, transfer_batch in enumerate(transfer_batches):
            # Evaluate CSVs:
            csv = Csv(delim=robot_settings.delimiter, newline=robot_settings.newline)
            csv.file_name = \
                robot_settings.get_filename(transfer_batch, self.context, ix, include_step_prefix)
            csv.set_header(robot_settings.header)
            sorted_transfers = sorted(transfer_batch.transfers, key=robot_settings.transfer_sort_key)
            for transfer in sorted_transfers:
                if robot_settings.include_transfer_in_output(transfer):
                    csv.append(robot_settings.map_transfer_to_row(transfer), transfer)
            transfer_batch.driver_file = csv

        return transfer_batches

    def create_transfers_from_pairs(self, pairs):
        """
        Creates the original transfer nodes in the route from the pairs

        Runs only the pre-validation (which usually ensures that the user provided conc/vol)

        Does not validate the transfers in another way or run the calculations.
        """
        # NOTE: The original containers are copied, so the containers in the transfer batch can be modified at will
        containers = dict()
        # First ensure that we've taken copies of the original containers, since we want to be able to move
        # the artifacts to different wells, it's cleaner to do that in a copied container:
        original_containers = set()
        original_containers.update([pair.input_artifact.container for pair in pairs])
        original_containers.update([pair.output_artifact.container for pair in pairs])
        for original_container in original_containers:
            containers[original_container.id] = copy.copy(original_container)

        def create_well(artifact):
            return Well(artifact.well.position,
                        containers[artifact.container.id],
                        artifact)

        transfers = list()

        # First, get a list of SingleTransfer objects, pointing to Well objects in copies of the original
        for pair in pairs:
            source_well = create_well(pair.input_artifact)
            target_well = create_well(pair.output_artifact)
            transfers.append(SingleTransfer(None, None, None, None, None, source_well, target_well))

        return transfers

    def transfer_batches(self, robot_name):
        """Returns the driver file for the robot. Might be cached"""
        return self.transfer_batches_by_robot[robot_name]

    def update_infos_by_target_analyte(self, transfer_batches):
        """
        Returns the information that should be updated in the backend

        After the dilution has taken place, values should be updated in the backend:
         - Target conc. should be updated on the target analyte
         - Target vol. should be updated on the target analyte
         - Source vol. should be updated on the source analyte
        """
        for target, transfers in self.group_transfers_by_target_analyte(transfer_batches).items():
            # TODO: The `is_pooled` check is a quick-fix.
            if target.is_pool and self.dilution_settings.is_pooled:
                regular_transfers = [t for t in transfers if not t.source_location.artifact.is_control]
                source_vol_delta = list(set(t.source_vol_delta for t in regular_transfers
                                            if t.should_update_source_vol))
                # We assume the same delta for all samples in the pool:
                source_vol_delta = utils.single(source_vol_delta)
                # We also assume the same conc for all (or all None)
                target_conc = utils.single(list(set(t.target_conc for t in regular_transfers)))
                target_vol = utils.single(list(set(t.target_vol for t in regular_transfers)))
                yield target, [UpdateInfo(target_conc, target_vol, source_vol_delta)]
            else:
                yield target, [t.update_info for t in transfers]

    @staticmethod
    def group_transfers_by_target_analyte(transfer_batches):
        """Returns transfers grouped by target analyte"""
        ret = dict()
        for transfer_batch in transfer_batches:
            for transfer in transfer_batch.transfers:
                artifact = transfer.final_target_location.artifact
                ret.setdefault(artifact, list())
                ret[artifact].append(transfer)
        return ret

    def single_robot_transfer_batches_for_update(self):
        """
        Helper method that returns the first robot transfer batch, but validates first that
        the updated_source_vol is the same on both. This supports the use case where the
        user doesn't have to tell us which robot driver file they used, because the results will be the same.
        """
        all_robots = self.transfer_batches_by_robot.items()
        candidate_name, candidate_batches = all_robots[0]
        candidate_update_infos = {key: value for key, value in self.update_infos_by_target_analyte(candidate_batches)}

        # Validate that selecting this robot will have the same effect as selecting any other robot
        for current_name, current_batches in all_robots[1:]:
            # Both need to have the same number of transfer batches:
            if len(candidate_batches) != len(current_batches):
                raise Exception("Can't select a single robot for update. Different number of batches between {} and {}".
                                format(candidate_name, current_name))
            # For each transfer in the candidate, we must have a corresponding transfer in
            # the current having the same update_source_vol. Other values can be different (e.g.
            # sort order, plate names on robots etc.)
            current_update_infos = {key: value for key, value in self.update_infos_by_target_analyte(current_batches)}
            for analyte, candidate_update_info in candidate_update_infos.items():
                current_update_info = current_update_infos[analyte]
                if candidate_update_info != current_update_info:
                    raise Exception("There is a difference between the update infos between {} and {}. You need "
                                    "to explicitly select a robot".format(candidate_name, current_name))
        return candidate_batches

    def enumerate_transfers_for_update(self):
        """
        Returns the transfers that require an update. Supports both the case of both regular dilution and "looped"
        (i.e. when we have more than one driver file). Relies on there being only one robot or that they are consistent
        in the reported updated_source_vol.
        """
        transfer_batches = self.single_robot_transfer_batches_for_update()
        for transfer_batch in transfer_batches:
            for transfer in transfer_batch.transfers:
                yield transfer

    def report(self):
        report = list()
        report.append("Dilution Session:")
        report.append("")
        for robot, transfer_batches in self.transfer_batches_by_robot.items():
            report.append("Robot: {}".format(robot))
            for transfer_batch in transfer_batches:
                report.append(transfer_batch.report())
        return "\n".join(report)


class SingleTransfer(object):
    """
    Encapsulates a single transfer between two positions:
      * From where: source (TransferEndpoint)
      * To where: target (TransferEndpoint)
      * How much sample volume and buffer volume are needed (in the robot file)
      * Other metadata that will be used for warnings etc, e.g. has_to_evaporate/scaled_up etc.
    """
    SPLIT_NONE = 0
    SPLIT_ROW = 1
    SPLIT_BATCH = 2

    def __init__(self, source_conc, source_vol, target_conc, target_vol, dilute_factor,
                 source_location, target_location):
        self.source_conc = source_conc
        self.source_vol = source_vol
        self.target_conc = target_conc
        self.target_vol = target_vol
        self.dilute_factor = dilute_factor

        self.source_location = source_location
        self.target_location = target_location

        # The calculated values:
        self.pipette_sample_volume = 0
        self.pipette_buffer_volume = 0

        # Meta values for warnings etc.
        self.has_to_evaporate = None
        self.scaled_up = False

        # In the case of temporary transfers, we keep a pointer to the original for easier calculations
        self.original = None
        self.source_vol_delta = None

        # The TransferBatch takes care of marking the transfer as being a part of it
        self.transfer_batch = None

        # Regular transfers are "primary", but if they are split into others, either into rows or other transfer,
        # the resulting transfers are "secondary"
        self.is_primary = True

        # Set to False if source vol should not be updated based on this transfer.
        # NOTE: This solves a use case where transfer objects shouldn't be used to update source volume. It would
        # make sense to just set updated_source_vol to zero in that case, but this is currently simpler as it
        # solves the case with TransferBatches. Look into changing back to the other approach later
        self.should_update_source_vol = True
        self.should_update_target_vol = True
        self.should_update_target_conc = True

        self.split_type = SingleTransfer.SPLIT_NONE

        # A string identifying the batch the transfer should be grouped into
        self.batch = "default"

        self.validation_results = ValidationResults()

        # A site-specific command to send to the robot.
        self.custom_command = None

        # The source and target slot are slots on the robot in which the containers are put:
        self.source_slot = None
        self.target_slot = None

    @property
    def pipette_total_volume(self):
        return self.pipette_buffer_volume + self.pipette_sample_volume

    def identifier(self):
        source = "source({}, conc={})".format(
            self.source_well, self.source_concentration)
        target = "target({}, conc={}, vol={})".format(self.target_well,
                                                      self.requested_concentration, self.requested_volume)
        return "{} => {}".format(source, target)

    @property
    def updated_source_vol(self):
        if self.source_vol_delta is not None and self.source_vol is not None:
            return self.source_vol + self.source_vol_delta
        else:
            return None

    @property
    def update_info(self):
        return UpdateInfo(target_conc=self.target_conc if self.should_update_target_conc else None,
                          target_vol=self.target_vol if self.should_update_target_vol else None,
                          source_vol_delta=self.source_vol_delta if self.should_update_source_vol else None)

    @property
    def final_target_location(self):
        if not self.is_primary and self.split_type == SingleTransfer.SPLIT_BATCH:
            return self.original.target_location
        else:
            return self.target_location

    def split_type_string(self):
        if self.split_type == SingleTransfer.SPLIT_BATCH:
            return "batch"
        elif self.split_type == SingleTransfer.SPLIT_ROW:
            return "row"
        else:
            return "no split"

    def __repr__(self):
        return "<SingleTransfer {}({},{}=>[{}]) =({},{})=> {}({},{}) {} / {}>".format(
            self.source_location,
            self.source_conc,
            self.source_vol,
            self.updated_source_vol if self.should_update_source_vol else "",
            self.pipette_sample_volume,
            self.pipette_buffer_volume,
            self.target_location,
            self.target_conc,
            self.target_vol,
            "primary" if self.is_primary else "secondary ({})".format(self.split_type_string()),
            tuple(self.update_info))


# Represents source conc/vol, target conc/vol as one unit. TODO: Better name
DilutionMeasurements = namedtuple('DilutionMeasurements', ['source_conc', 'source_vol', 'target_conc', 'target_vol'])
UpdateInfo = namedtuple("UpdateInfo", ['target_conc', 'target_vol', 'source_vol_delta'])


class DilutionSettings:
    """Defines the rules for how a dilution should be performed"""
    CONCENTRATION_REF_NGUL = 1
    CONCENTRATION_REF_NM = 2
    VOLUME_CALC_FIXED = 1
    VOLUME_CALC_BY_CONC = 2

    CONCENTRATION_REF_TO_STR = {
        CONCENTRATION_REF_NGUL: "ng/ul",
        CONCENTRATION_REF_NM: "nM"
    }

    def __init__(self, scale_up_low_volumes=False, concentration_ref=None, include_blanks=False,
                 volume_calc_method=None, make_pools=False, fixed_sample_volume=None):
        """
        :param dilution_waste_volume: Extra volume that should be subtracted from the sample volume
        to account for waste during dilution
        """
        self.scale_up_low_volumes = scale_up_low_volumes
        # TODO: Use py3 enums instead
        if concentration_ref is not None:
            concentration_ref = self._parse_conc_ref(concentration_ref)
            if concentration_ref not in [self.CONCENTRATION_REF_NM, self.CONCENTRATION_REF_NGUL]:
                raise ValueError("Unsupported concentration_ref '{}'".format(concentration_ref))
        self.concentration_ref = concentration_ref
        # TODO: include_blanks, has that to do with output only? If so, it should perhaps be in RobotSettings
        self.include_blanks = include_blanks
        self.volume_calc_method = volume_calc_method
        self.make_pools = make_pools
        self.include_control = True
        self.fixed_sample_volume = fixed_sample_volume

        # NOTE: This is part of a quick-fix (used in one particular corner case)
        self.is_pooled = False

    @staticmethod
    def _parse_conc_ref(concentration_ref):
        if isinstance(concentration_ref, basestring):
            for key, value in DilutionSettings.CONCENTRATION_REF_TO_STR.items():
                if value.lower() == concentration_ref.lower():
                    return key
        else:
            return concentration_ref

    @staticmethod
    def concentration_unit_to_string(conc_ref):
        return DilutionSettings.CONCENTRATION_REF_TO_STR[conc_ref]


class RobotSettings(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        """
        Inherit from this file to supply new settings for a robot
        """
        self.name = None
        self.newline = None
        self.file_ext = None
        self.delimiter = None
        self.dilution_waste_volume = None
        self.pipette_min_volume = None
        self.pipette_max_volume = None
        self.max_pipette_vol_for_row_split = None

    def include_transfer_in_output(self, transfer):
        return True

    @abc.abstractmethod
    def map_transfer_to_row(self, transfer):
        """
        Describes how to transform a SingleTransfer object to a csv row
        :return:
        """
        pass

    @abc.abstractmethod
    def get_index_from_well(self, well):
        """Returns the numerical index of the well"""
        pass

    @abc.abstractmethod
    def get_filename(self, csv, context):
        pass

    @staticmethod
    def source_container_name(transfer_location):
        return "DNA{}".format(transfer_location.container_pos)

    @staticmethod
    def target_container_name(transfer_location):
        return "END{}".format(transfer_location.container_pos)

    @staticmethod
    def transfer_sort_key(transfer):
        """
        Sort the transfers based on:
            - Regular should become before controls
            - source position (container.index)
            - well index (down first)
            - pipette volume (descending)
        """
        assert transfer.transfer_batch is not None
        assert transfer.source_slot is not None
        assert transfer.source_slot.index is not None
        return (transfer.source_slot.index,
                transfer.source_location.index_down_first,
                -transfer.pipette_total_volume)

    def __repr__(self):
        return "<RobotSettings {}>".format(self.name)

    def __str__(self):
        return "<RobotSettings {name} file_ext='{file_ext}'>".format(
            name=self.name,
            file_ext=self.file_ext)


class TransferValidationException(ValidationException):
    """Wraps a validation exception for Dilution transfer objects"""

    def __init__(self, transfer, msg, result_type=ValidationType.ERROR):
        super(TransferValidationException, self).__init__(msg, result_type)
        self.transfer = transfer

    def __repr__(self):
        return "{}: {} transfer ({}@{} => {}@{}) - {}".format(
            self._repr_type(),
            self.transfer.transfer_batch.name if self.transfer.transfer_batch else "",
            self.transfer.source_location.position, self.transfer.source_location.container.id,
            self.transfer.target_location.position, self.transfer.target_location.container.id,
            self.msg)


class TransferBatch(object):
    """
    Encapsulates a list of SingleTransfer objects. Used to generate robot driver files.
    """

    def __init__(self, transfers, depth=0, is_temporary=False, name=None):
        self._container_to_container_slot = dict()
        self.depth = depth
        self.is_temporary = is_temporary  # temp dilution, no plate will actually be saved.
        self.validation_results = list()
        self._set_transfers(transfers)
        self.name = name
        self._transfers_by_output_dict = None
        # Set to True if the transfer batch was split
        self.split = False

    def _set_transfers(self, transfers):
        self._transfers_by_output_dict = None
        self._transfers = transfers
        for transfer in transfers:
            transfer.transfer_batch = self
            for validation_result in transfer.validation_results:
                self.validation_results.append(validation_result)

    @property
    def transfers(self):
        """
        Enumerates the transfers. The underlying transfer list is sorted by self._transfer_sort_key
        and row split is performed if needed
        """
        return self._transfers

    @property
    def transfers_by_output(self):
        """Returns the transfers in the batch grouped by the artifact in the target well"""
        if self._transfers_by_output_dict is None:
            self._transfers_by_output_dict = self._transfers_by_output()
        return self._transfers_by_output_dict

    def _transfers_by_output(self):
        def group_key(transfer):
            # TODO: Use the artifact rather than the id
            return transfer.target_location.artifact.id

        transfers = sorted(self.transfers, key=group_key)
        return {k: list(t) for k, t in groupby(transfers, key=group_key)}

    # TODO: site-specific?
    def _include_in_container_mappings(self, transfer):
        """
        Exclude negative controls which is added in current step.
        Do not exclude negative controls added in previous step.
        """
        a = transfer.source_location.artifact
        return not a.is_control or a.id.startswith("2-")

    @property
    def container_mappings_for_printout(self):
        def slot_repr(slot):
            return "{} ({})".format(slot.name, slot.container.name)
        sources = self.source_container_slots
        targets = self.target_container_slots
        gen = izip_longest(map(slot_repr, sources), map(slot_repr, targets), fillvalue="")
        return [pair for pair in gen]

    @property
    def container_mappings(self):
        ret = set()
        for transfer in self.transfers:
            if self._include_in_container_mappings(transfer):
                ret.add((transfer.source_slot, transfer.target_slot))

        ret = list(sorted(ret, key=lambda t: t[0].index))
        return ret

    @property
    def target_container_slots(self):
        return sorted(set(target for source, target in self.container_mappings),
                      key=lambda cont: cont.index)

    @property
    def source_container_slots(self):
        return sorted(set(source for source, target in self.container_mappings),
                      key=lambda source: source.index)

    def report(self):
        """Creates a detailed report of what's included in the transfer, for debug and learning purposes."""
        report = list()
        report.append("TransferBatch:")
        report.append("-" * len(report[-1]))
        report.append(" - temporary: {}".format(self.is_temporary))
        for source, target in self.container_mappings:
            report.append(" - {} => {}".format(source, target))
        for transfer in self._transfers:
            report.append("{}".format(transfer))
        return "\n".join(report)

    def __iter__(self):
        return iter(self.transfers)


class TransferBatchCollection(object):
    """
    Encapsulates the list of TransferBatch object that go together, i.e. as the result of splitting a
    TransferBatch.
    """

    def __init__(self, sort_key, *args):
        self._batches = list()
        self.sort_key = sort_key
        self._batches.extend(args)

    def append(self, obj):
        self._batches.append(obj)

    def __iter__(self):
        return iter(sorted(self._batches, key=self.sort_key))

    def __len__(self):
        return len(self._batches)

    def __getitem__(self, item):
        return self._batches[item]

    def report(self):
        ret = list()
        for batch in self._batches:
            ret.append(batch.report())
        return "\n\n".join(ret)

    @property
    def driver_files(self):
        """Returns the driver files (csvs) as a dictionary"""
        return {tb.name: tb.driver_file for tb in self}

    def __repr__(self):
        return repr(self._batches)


class ContainerSlot(object):
    """
    During a dilution, containers are positioned on a robot in a sequential order.
    This is encapsulated by wrapping them in a 'ContainerSlot'.

    The name is the name used by the robot to reference the container.
    """

    def __init__(self, container, index, name, is_source):
        self.container = container
        self.index = index
        self.name = name
        self.is_source = is_source

    def __repr__(self):
        return "{} ({}): [{}]".format(self.name, "source" if self.is_source else "target", self.container)


class TransferHandlerBase(object):
    """Base class for all handlers"""
    __metaclass__ = abc.ABCMeta

    def __init__(self, dilution_session, dilution_settings, robot_settings, virtual_batch):
        self.dilution_session = dilution_session
        self.dilution_settings = dilution_settings
        self.robot_settings = robot_settings
        self.virtual_batch = virtual_batch
        self.validation_exceptions = list()
        self.logger = logging.getLogger(__name__)
        self.validation_results = ValidationResults()

    def tag(self):
        return None

    def run(self, transfer_route_node):
        """Called by the engine"""
        transfer_route_node.handler = self
        if not self.should_execute(transfer_route_node.transfer):
            return [TransferRouteNode(copy.copy(transfer_route_node.transfer))]
        ret = self.handle_transfer(transfer_route_node.transfer)
        transfer_route_node.handler_executed = True
        if ret is None:
            # When nothing is returned, we continue with the same values, but a shallow copy for debuggingb
            return [TransferRouteNode(copy.copy(transfer_route_node.transfer))]
        else:
            # Otherwise (when splitting) we return a list of new transfer route nodes:
            return [TransferRouteNode(t) for t in ret]

    def handle_transfer(self, transfer):
        pass

    def should_execute(self, transfer):
        return True

    def error(self, msg, transfer):
        transfer.validation_results.append(TransferValidationException(transfer, msg, ValidationType.ERROR))

    def warning(self, msg, transfer):
        transfer.validation_results.append(TransferValidationException(transfer, msg, ValidationType.WARNING))

    def __repr__(self):
        return self.__class__.__name__


class TransferBatchHandlerBase(TransferHandlerBase):
    def handle_batch(self, batch):
        pass

    def error(self, msg, batch):
        batch.validation_results.append(ValidationException(msg, ValidationType.ERROR))

    def warning(self, msg, batch):
        batch.validation_results.append(ValidationException(msg, ValidationType.WARNING))


class TransferSplitHandlerBase(TransferHandlerBase):
    """Base class for handlers that can split one transfer into more"""
    __metaclass__ = abc.ABCMeta

    # TODO: Better naming so it's clear that this differs from the row-split
    def handle_split(self, transfer, temp_transfer, main_transfer):
        pass

    def temp_tag(self):
        return None

    def main_tag(self):
        return None

    @abc.abstractmethod
    def _update_source_target_locations(self, dilute_session, original_transfer,
                                        temp_transfer, main_transfer):
        pass

    def _split_transfer(self, dilute_session, transfer):
        """Returns two transfers where the first one will go on a temporary container"""
        temp_transfer = SingleTransfer(transfer.source_conc, transfer.source_vol,
                                       transfer.target_conc, transfer.target_vol, 0, None, None)
        main_transfer = copy.copy(temp_transfer)

        temp_transfer.is_primary = False
        temp_transfer.split_type = SingleTransfer.SPLIT_BATCH
        temp_transfer.should_update_target_vol = False
        temp_transfer.should_update_target_conc = False
        temp_transfer.original = transfer

        temp_transfer, main_transfer = self._update_source_target_locations(
            dilute_session, transfer, temp_transfer, main_transfer)

        return temp_transfer, main_transfer

    def run(self, transfer_route_node):
        if not self.should_execute(transfer_route_node.transfer):
            return None
        temp_transfer, main_transfer = self._split_transfer(self.dilution_session, transfer_route_node.transfer)
        temp_transfer.batch = self.temp_tag()
        main_transfer.batch = self.main_tag()
        self.handle_split(transfer_route_node.transfer, temp_transfer, main_transfer)
        return [TransferRouteNode(temp_transfer), TransferRouteNode(main_transfer)]


class OrTransferHandler(TransferHandlerBase):
    """A handler that stops executing the subhandlers when one of them succeeds"""

    def __init__(self, dilution_session, dilution_settings, robot_settings, virtual_batch, *sub_handlers):
        super(OrTransferHandler, self).__init__(dilution_session, dilution_settings, robot_settings, virtual_batch)
        self.sub_handlers = sub_handlers

    def run(self, transfer_node):
        """Given a transfer route node, returns a list of one or more transfers resulting from it"""
        transfer_node.handler = self
        evaluated = None
        for handler in self.sub_handlers:
            evaluated = handler.run(transfer_node)
            if evaluated:
                break
        if evaluated:
            transfer_node.executed = True
            return evaluated
        else:
            return [TransferRouteNode(copy.copy(transfer_node.transfer))]

    def __repr__(self):
        return "OR({})".format(", ".join(map(repr, self.sub_handlers)))


class TransferRoute(object):
    """Describes the route needed to get to a preferred dilution"""

    def __init__(self, root, handlers):
        self.root = root
        self.handlers = handlers

    def __str__(self):
        # Traverse the tree, printing out the leaves
        ret = ["Transfer route:"]
        ret.append(len(ret[0]) * "-")
        ret.append("Handlers: {}".format(self.handlers))

        for node, level in self.walk():
            ret.append("{}{}".format(level * " ", node))
        return "\n".join(ret)

    @property
    def transfers(self):
        """The leaf nodes of the tree form the transfers we'll expose"""
        return [node.transfer for node, level in self.walk() if node.is_leaf]

    def walk(self):
        """Walks the tree in a BFS manner, yielding the current node and the level"""
        s = set()
        q = list()  # Contains (node, level)

        s.add(self.root)
        q.append((self.root, 0))

        while len(q) > 0:
            current, level = q.pop()
            yield (current, level)
            for child in current.children:
                q.append((child, level + 1))

    def __repr__(self):
        return repr(self.root)


class TransferRouteNode(object):
    """Describes one 'node' in the transfer route
    
    Transfers are described by the SingleTransfer class. But while evaluating handlers, since there may be errors
    during validation and because transfers may be split, we encapsulate each evaluated transfer in the node by a
    TransferRouteNode
    """

    def __init__(self, transfer):
        self.transfer = transfer
        self.children = list()
        # self.validation_results = list()  # Validation exceptions that occurred during handling
        self.handler = None
        self.handler_executed = False  # True if the handler has actually executed

    @property
    def is_leaf(self):
        return len(self.children) == 0

    def __repr__(self):
        return "{}({}) is_leaf={}, handler_executed={}".format(self.handler, self.transfer, self.is_leaf,
                                                               self.handler_executed)
