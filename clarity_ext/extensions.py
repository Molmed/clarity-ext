from __future__ import print_function
import importlib
import os
import sys
import codecs
import shutil
from context import ExtensionContext
import clarity_ext.utils as utils
from abc import ABCMeta, abstractmethod
import logging
import difflib
from clarity_ext.utils import lazyprop
from clarity_ext import ClaritySession
from clarity_ext.repository import StepRepository
from clarity_ext.service import ArtifactService, FileService
from clarity_ext.utility.integration_test_service import IntegrationTest
from clarity_ext.service.dilution.index_generation import ConfigValidator
from clarity_ext.service.dilution.index_generation import ConfigParser
from jinja2 import Template
import time
import random
import logging.handlers
import lxml.objectify
from clarity_ext.service.validation_service import UsageError
import re


# Defines all classes that are expected to be extended. These are
# also imported to the top-level module
class ExtensionService(object):
    RUN_MODE_TEST = "test"
    RUN_MODE_TEST_FRESH = "test-fresh"
    RUN_MODE_FREEZE = "freeze"
    RUN_MODE_EXEC = "exec"

    # TODO: It would be preferable to have all cached data in a subdirectory, needs a patch in requests-cache
    CACHE_NAME = ".http_cache"
    CACHE_ARTIFACTS_DIR = ".cache"

    def __init__(self, msg_handler):
        """
        :param msg_handler: A callable that receives messages to a user using the application interactively
        """
        self.logger = logging.getLogger(__name__)
        self.msg = msg_handler
        self.rotating_file_path = None

    def set_log_strategy(self, level, log_to_stdout, log_to_file, use_timestamp,
                         rotating_log_dir=None, rotating_log_name=None):

        root_logger = logging.getLogger('')
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
        root_logger.setLevel(level)

        formatter = utils.get_default_log_formatter(use_timestamp)
        if log_to_stdout:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        # Log to the current directory if the rotating directory doesn't exist.
        if log_to_file:
            warn_dir_missing = False
            if not os.path.exists(rotating_log_dir):
                warn_dir_missing = True
                rotating_log_dir = os.path.abspath(".")
            self.rotating_file_path = os.path.join(rotating_log_dir, rotating_log_name)
            rotating_handler = logging.handlers.RotatingFileHandler(
                self.rotating_file_path, maxBytes=10 * (2 ** 20), backupCount=5)
            rotating_handler.setFormatter(formatter)
            root_logger.addHandler(rotating_handler)

            if warn_dir_missing:
                logging.warn(
                    "The rotating log directory {} doesn't exist. Logging to ./ instead".format(rotating_log_dir))

    def _get_run_path(self, pid, module, mode, config):
        """Fetches the run path based on different modes of execution"""
        if mode == self.RUN_MODE_EXEC:
            return config["exec_root_path"]
        elif mode == self.RUN_MODE_TEST or mode == self.RUN_MODE_FREEZE:
            root = config["test_root_path"] if mode == self.RUN_MODE_TEST else config["frozen_root_path"]
            # When testing or freezing, we need subdirectories based on the modules path
            # so they don't get mixed up:
            module_parts = module.split(".")[1:]
            path = os.path.sep.join(module_parts)
            return os.path.join(root, path, pid, "run-" + mode)
        else:
            raise ValueError("Unexpected mode")

    def _artifact_service(self, pid):
        session = ClaritySession.create(pid)
        step_repo = StepRepository(session)
        return ArtifactService(step_repo)

    def run_exec(self, config, run_arguments_list, module):
        """Executes the extension normally, without freezing or caching. This should be the default in production."""
        for run_arguments in run_arguments_list:
            pid = run_arguments["pid"]
            path = self._get_run_path(pid, module, self.RUN_MODE_EXEC, config)
            self._run(path, pid, module, False, False)

    def run_test(self, config, run_arguments_list, module, artifacts_to_stdout, use_cache, validate_against_frozen):
        self.msg("To execute from Clarity:")
        self.msg("  clarity-ext extension --args '{}' {} {}".format(
            "pid={processLuid}", module, self.RUN_MODE_EXEC))
        self.msg("To execute from Clarity in a sandbox:")
        self.msg("  bash -c \"source activate clarity-USER && clarity-ext extension --args '{}' {} {}\"".format(
            "pid={processLuid}", module, self.RUN_MODE_EXEC))
        self.msg("To run a fresh test (ignores the frozen test's cache)")
        self.msg("  clarity-ext extension '{}' test-fresh".format(module))
        self.msg("To freeze the latest test run (set as reference data for future validations):")
        self.msg("  clarity-ext extension {} {}".format(
            module, self.RUN_MODE_FREEZE))

        if use_cache is None:
            use_cache = True
        if use_cache:
            self._set_cache(use_cache)

        if not run_arguments_list:
            run_arguments_list = self._gather_runs(module, True)

        for run_arguments in run_arguments_list:
            pid = run_arguments["pid"]
            commit = run_arguments["commit"]
            path = self._get_run_path(pid, module, self.RUN_MODE_TEST, config)

            if validate_against_frozen:
                frozen_path = self._get_run_path(pid, module, self.RUN_MODE_FREEZE, config)
                self._prepare_frozen_test(path, frozen_path)
            else:
                self._prepare_fresh_test(path)

            with utils.add_log_file_handler(os.path.join(path, "extensions.log"), False, ExtensionTestLogFilter()):
                self._run(path, pid, module, artifacts_to_stdout, disable_context_commit=not commit, test_mode=True)

            if validate_against_frozen:
                try:
                    self._validate_against_frozen(path, frozen_path)
                except NoFrozenDataFoundException:
                    self.msg("No frozen data was found at {}".format(frozen_path))

    def _prepare_fresh_test(self, path):
        """
        Prepares a test where a cache from the frozen directory should not be used, but a
        new cache might be generated
        """
        if os.path.exists(path):
            self.logger.info("Cleaning run directory '{}'".format(path))
            utils.clean_directory(path)
        else:
            self.logger.info("Creating an empty run directory at {}".format(path))
            os.makedirs(path)

    def _prepare_frozen_test(self, path, frozen_path):
        self.logger.info("Preparing frozen test at '{}'".format(frozen_path))
        http_cache_file = '{}.sqlite'.format(self.CACHE_NAME)

        # Remove everything but the cache files
        if os.path.exists(path):
            self.logger.info("Cleaning run directory '{}' of everything but the cache file".format(path))
            utils.clean_directory(path, [http_cache_file, self.CACHE_ARTIFACTS_DIR])
        else:
            self.logger.info("Creating an empty run directory at {}".format(path))
            os.makedirs(path)

        # Copy the cache file from the frozen path if available:
        frozen_http_cache_file = os.path.join(frozen_path, http_cache_file)
        frozen_cache_dir = os.path.join(frozen_path, self.CACHE_ARTIFACTS_DIR)
        if os.path.exists(frozen_http_cache_file):
            self.logger.info("Frozen http cache file exists and will be copied to run location")
            shutil.copy(frozen_http_cache_file, path)

        if os.path.exists(frozen_cache_dir):
            if os.path.exists(os.path.join(path, self.CACHE_ARTIFACTS_DIR)):
                shutil.rmtree(os.path.join(path, self.CACHE_ARTIFACTS_DIR))
            self.logger.info("Frozen cache directory exists and will be used")
            shutil.copytree(frozen_cache_dir, os.path.join(path, self.CACHE_ARTIFACTS_DIR))

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(utils.dir_tree(path))
            self.logger.debug(utils.dir_tree(frozen_path))

    def run_freeze(self, config, run_arguments_list, module):
        """
        Freezes the results of running an extension so it can be validated later

        :params config: A dictionary of paths. Uses the default config if not provided
        """

        if not run_arguments_list:
            self.logger.debug("Run arguments not provided, fetching from extension")
            run_arguments_list = self._gather_runs(module)

        frozen_root_path = config.get("frozen_root_path", ".")
        self.msg("Freezing data (requests, responses and result files/hashes) to {}"
                 .format(frozen_root_path))

        for run_arguments in run_arguments_list:
            pid = run_arguments["pid"]
            test_path = self._get_run_path(pid, module, self.RUN_MODE_TEST, config)
            frozen_path = self._get_run_path(pid, module, self.RUN_MODE_FREEZE, config)

            if os.path.exists(frozen_path):
                self.logger.info("Removing old frozen directory '{}'".format(frozen_path))
                shutil.rmtree(frozen_path)
            shutil.copytree(test_path, frozen_path)

            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(utils.dir_tree(test_path))
                self.logger.debug(utils.dir_tree(frozen_path))

    def _gather_runs(self, module, require_tests=True):
        def parse_run_argument(in_argument):
            # The run argument can be either an IntegrationTest or just a string (pid)
            if isinstance(in_argument, IntegrationTest):
                test = in_argument
            elif isinstance(in_argument, basestring):
                test = IntegrationTest(pid=in_argument)
            else:
                raise ValueError("Unexpected run argument type")
            return test

        instance = self._get_extension(module)(None)
        ret = map(parse_run_argument, instance.integration_tests())
        if require_tests and len(ret) == 0:
            raise NoTestsFoundException()
        return ret

    def _prepare_runs(self, extension_instance):
        """TODO: Document what this does"""
        for integration_test in extension_instance.integration_tests():
            if isinstance(integration_test, IntegrationTest) and integration_test.preparer:
                artifact_service = self._artifact_service(integration_test.pid())
                integration_test.preparer.prepare(artifact_service)

    def _set_cache(self, use_cache):
        if use_cache:
            self.logger.info("Using cache {}".format(self.CACHE_NAME))
            utils.use_requests_cache(self.CACHE_NAME)

    def _get_extension(self, module):
        module_obj = importlib.import_module(module)
        return getattr(module_obj, "Extension")

    def _run(self, path, pid, module, artifacts_to_stdout, disable_context_commit=False, test_mode=False):
        print("RUNNING")
        path = os.path.abspath(path)
        self.logger.info("Running extension {module} for pid={pid}, test_mode={test_mode}".format(
            module=module, pid=pid, test_mode=test_mode))
        self.logger.info(" - Path={}".format(path))
        extension = self._get_extension(module)
        old_dir = os.getcwd()
        os.chdir(path)
        self.logger.info("Executing at {}".format(path))
        context = ExtensionContext.create(pid, test_mode=test_mode,
                                          disable_commits=disable_context_commit,
                                          uploaded_to_stdout=artifacts_to_stdout)
        instance = extension(context)
        try:
            if issubclass(extension, DriverFileExtension):
                context.file_service.upload(instance.shared_file(), instance.filename(), instance.to_string(),
                                            instance.file_prefix())
            elif issubclass(extension, GeneralExtension):
                instance.execute()
            else:
                raise NotImplementedError("Unknown extension type")
            context.commit()
        except UsageError as e:
            # Commit in order to upload step log
            # Ordinary files and objects shouldn't have been moved to upload queue,
            # since the scipt have been interrupted by the usage error.
            context.commit()
            # UsageErrors are deferred and handled by the notify method
            # To support the case (legacy) if someone raises an error without adding it to the defer list,
            # we add it to the instance too:
            if len(instance.errors) == 0:
                instance.errors[e] = list()
        os.chdir(old_dir)

        self.notify(instance.errors, instance.warnings, context.validation_service.error_count,
                    context.validation_service.warning_count, context, module)

    def notify(self, user_errors, user_warnings, other_errors_count, other_warnings_count, context, module):
        """Notifies the user of errors and warnings during execution. user_errors and user_warnings
        should be shown in the UI. The engine itself may have gathered other errors and warnings, which
        are then accessible in the error log.
        """
        total_error_count = len(user_errors) + other_errors_count
        total_warning_count = len(user_warnings) + other_warnings_count

        if total_error_count > 0 or total_warning_count > 0:
            errors = self._generate_notifications(user_errors)
            warnings = self._generate_notifications(user_warnings)
            end_user_notification = ["WARNING: {} ran with {} error(s), {} warning(s)".format(
                module, total_error_count, total_warning_count)]
            # Log the error/warning, but also show it to the user
            if errors:
                for error in errors:
                    context.logger.error(error)
                end_user_notification.append("Errors: " + "; ".join(errors))
            if warnings:
                for warning in warnings:
                    context.logger.warning(warning)
                end_user_notification.append("Warnings: " + "; ".join(warnings))
            print("; ".join(end_user_notification))
        else:
            print("{} ran successfully".format(module))

        if total_error_count > 0:
            # Exit with error code 1. This ensures that Clarity shows an error box instead of just a notifaction box.
            sys.exit(1)

    def _generate_notifications(self, bag):
        if len(bag) == 0:
            return None
        messages = list()
        for key, values in bag.items():
            current = "{}".format(key)
            if values:
                current += ": {}".format(values)
            messages.append(current)
        return messages

    def _validate_against_frozen(self, path, frozen_path):
        if os.path.exists(frozen_path):
            test_info = RunDirectoryInfo(path)
            frozen_info = RunDirectoryInfo(frozen_path)
            diff_report = list(test_info.compare(frozen_info))
            if len(diff_report) > 0:
                msg = []
                for type, key, diff in diff_report:
                    msg.append("{} ({}).".format(key, type))
                    msg.append(diff)
                    msg.append(path + " " + frozen_path)
                raise ResultsDifferFromFrozenData("\n".join(msg))
        else:
            raise NoFrozenDataFoundException(frozen_path)


class ResultsDifferFromFrozenData(Exception):
    pass


class RunDirectoryInfo(object):
    """
    Provides methods to query a particular result directory for its content

    Used to compare two different runs, e.g. a current test and a frozen test
    """

    def __init__(self, path):
        self.path = path
        self.uploaded_path = os.path.join(self.path, "uploaded")

    @lazyprop
    def uploaded_files(self):
        """Returns a dictionary of uploaded files indexed by key"""
        ret = dict()
        if not os.path.exists(self.uploaded_path):
            return ret
        for file_name in os.listdir(self.uploaded_path):
            assert os.path.isfile(os.path.join(self.uploaded_path, file_name))
            file_key = self.file_key(file_name)
            if file_key:
                if file_key in ret:
                    raise Exception("More than one file with the same prefix")
                ret[file_key] = os.path.abspath(os.path.join(self.uploaded_path, file_name))
            else:
                raise Exception("Unexpected file name {}, should start with Clarity ID".format(file_name))
        return ret

    def file_key(self, file_name):
        import re
        match = re.match(r"(^\d+-\d+).*$", file_name)
        if match:
            return match.group(1)
        else:
            return None

    def compare_files(self, a, b):
        with open(a, 'r') as f:
            fromlines = f.readlines()
        with open(b, 'r') as f:
            tolines = f.readlines()

        diff = list(difflib.unified_diff(fromlines, tolines, a, b))
        return diff

    def compare(self, other):
        """Returns a report for the differences between the two runs"""
        a_keys = set(self.uploaded_files.keys())
        b_keys = set(other.uploaded_files.keys())
        if a_keys != b_keys:
            raise Exception("Keys differ: {} != {}".format(a_keys, b_keys))

        for key in self.uploaded_files:
            path_a = self.uploaded_files[key]
            path_b = other.uploaded_files[key]
            diff = self.compare_files(path_a, path_b)
            if len(diff) > 0:
                yield ("uploaded", key, "".join(diff[0:10]))

        # Compare the log files:
        log_file_a = os.path.join(self.path, "extensions.log")
        log_file_b = os.path.join(other.path, "extensions.log")
        if os.path.exists(log_file_a):
            if not os.path.exists(log_file_b):
                raise Exception("Log file exists at {} but not at {}".format(self.path, other.path))
            diff = self.compare_files(log_file_a, log_file_b)
            if len(diff) > 0:
                yield ("logs", "extensions.log", "".join(diff[0:10]))


class GeneralExtension(object):
    """
    An extension that must implement the `execute` method
    """
    __metaclass__ = ABCMeta

    def __init__(self, context):
        """
        @type context: clarity_ext.driverfile.DriverFileContext

        :param context: The context the extension is running in. Can be used to access
                        the plate etc.
        :return: None
        """
        self.context = context
        self.logger = logging.getLogger(self.__class__.__module__)
        self.response = None
        # Expose the IntegrationTest type like this so it doesn't need to be imported
        self.test = IntegrationTest
        self.errors = dict()
        self.warnings = dict()

    def usage_warning(self, category, value=None):
        """
        Notify the user of an error or warning
        """
        self._defer_warning_or_error(False, category, value)

    def usage_error(self, msg):
        """
        Raise an error which the user can possibly fix by changing input parameters.
        """
        self.usage_error_defer(msg, None)
        self.raise_deferred()

    def usage_error_defer(self, category, value=None):
        """Defers raising the error until at the end of the extension run.

        Category can be any string, e.g. 'UDF target vol missing for artifact', in which case the value would
        be the id or name of the sample."""
        self._defer_warning_or_error(True, category, value)

    def _defer_warning_or_error(self, is_error, category, value=None):
        bag = self.errors if is_error else self.warnings
        bag.setdefault(category, list())
        if value:
            bag[category].append(value)

    def raise_deferred(self):
        """Raises the errors that have been deferred"""
        raise UsageError("Usage error")

    def notify(self, msg):
        """
        Adds text to the notification box in the UI, that's shown when
        the extension has finished running.
        """
        self.notifications.append(msg)

    @lazyprop
    def random(self):
        """Provides a random object. Seeds from a constant if context.test_mode is on"""
        if self.context.test_mode:
            return random.Random(0)  # Seed from a constant
        else:
            return random.Random()

    def handle_validation(self, validation_results):
        return self.validation_service.handle_validation(validation_results)

    @abstractmethod
    def integration_tests(self):
        """Returns `DriverFileTest`s that should be run to validate the code"""
        pass

    def localtime(self):
        # Returns the current time, but returns a constant time when running in test mode
        # Used to make sure that the basic built-in integration tests always use the same time.
        if self.context.test_mode:
            return 2016, 12, 12, 12, 43, 36, 0, 347, 0
        else:
            return time.localtime()

    def time(self, fmt, time_tuple=None):
        from time import strftime
        if time_tuple is None:
            time_tuple = self.localtime()
        return strftime(fmt, time_tuple)

    @staticmethod
    def parse(func, val):
        """Parses the value using func, but adding extra information for the end user.

        If this is an XML file, it will also add information on which line the error occurred."""
        try:
            return func(val)
        except ValueError:
            msg = "Not able to parse {} to a {}".format(repr(val), func.__name__)
            if isinstance(val, lxml.objectify.StringElement):
                msg = "{}: Error occurred at line {} in the xml file".format(msg, val.sourceline)
            raise UsageError(msg)

    def int(self, val):
        self.parse(int, val)

    def float(self, val):
        self.parse(float, val)

    def copy_udf(self, key, source, target):
        """Moves a udf value from the output_artifact to the input_artifact"""
        value = source.udf_map[key].value
        setattr(target, key, value)
        self.context.update(target)

    def copy_from_output_to_input(self, exceptions=[]):
        self.copy_all_udfs(lambda pair: (pair.output_artifact, [pair.input_artifact]), exceptions)

    def copy_from_input_to_output(self, exceptions=[]):
        self.copy_all_udfs(lambda pair: (pair.input_artifact, [pair.output_artifact]), exceptions)

    def copy_from_output_to_submitted_sample(self, exceptions=[]):
        """Copies all UDFs from the output analyte to each submitted sample."""
        self.copy_all_udfs(lambda pair: (pair.output_artifact, pair.output_artifact.samples), exceptions)

    def copy_all_udfs(self, source_target_fn, exceptions):
        for pair in self.context.artifact_service.all_aliquot_pairs():
            source, targets = source_target_fn(pair)
            self.logger.info("Updating UDF values. source: {}".format(source))
            for target in targets:
                self.logger.info(" - target: {}".format(target))
                common_udfs = target.udf_map.py_names.intersection(source.udf_map.py_names)
                for udf in common_udfs:
                    if any(re.match(pattern, udf) for pattern in exceptions):
                        continue
                    value = source.udf_map[udf].value
                    self.logger.info("  - {}: {}".format(udf, value))
                    if value is None:
                        continue
                    target.udf_map[udf] = value
                    self.context.update(target)


class DriverFileExtension(GeneralExtension):
    __metaclass__ = ABCMeta

    @abstractmethod
    def shared_file(self):
        """Returns the name of the shared file that should include the newly generated file"""
        return "Sample List"

    @abstractmethod
    def content(self):
        """Yields the output lines of the file, or the response at updates"""
        pass

    def newline(self):
        return "\n"

    def to_string(self):
        content = self.content()
        # Support that the content can be a list of strings. This supports an older version of the DriverFileExtension
        # which was not template based. Consider removing this usage of the DriverFileExtension.
        if isinstance(content, basestring):
            return content
        else:
            return self.newline().join(content)

    def file_prefix(self):
        return FileService.FILE_PREFIX_ARTIFACT_ID


class IndexFileExtension(GeneralExtension):
    def execute(self):
        input_analytes = self.context.artifact_service.all_input_analytes()
        self.context.initialize_logger()
        expected_sample_name, sample_candidates, validator = \
            self._prepare_validation(input_analytes)
        validator.validate(expected_sample_name, sample_candidates, input_analytes)
        from utils import single
        sample = single(sample_candidates)
        files = list()
        config_parser = ConfigParser(sample)
        file_generator = self.get_file_generator(
            self.context.current_user.initials, self.context.pid,
            sample.udf_indexconfig_short_name)
        for robot_settings in self.get_robot_settings():
            index_pos_dict = config_parser.index_mapping_dict(robot_settings)
            sorted_analytes = sorted(input_analytes, key=self._target_pos_sort_key)
            source_dimensions = config_parser.source_dimensions(robot_settings)
            csv = file_generator.generate_csv(robot_settings, sorted_analytes,
                                              index_pos_dict=index_pos_dict,
                                              source_dim=source_dimensions)
            files.append((csv.file_name, csv.to_string(include_header=False)))

        self.upload_files(files=files)

    @abstractmethod
    def upload_files(self, files):
        pass

    @abstractmethod
    def get_file_generator(self, user_initials, pid, short_category):
        pass

    def _prepare_validation(self, input_analytes):
        from clarity_ext.mappers.clarity_mapper import ClarityMapper
        from clarity_ext.repository.reagent_type_repository import ReagentTypeRepository
        """ factory method"""
        label = input_analytes[0].get_reagent_label()
        reagent_repo = ReagentTypeRepository(session=self.context.session)
        reagent_type = reagent_repo.get_reagent_type(label=label)
        expected_sample_name = self._get_sample_name(reagent_type.category)
        sample_resources = self.context.session.api.get_samples(name=expected_sample_name)
        mapper = ClarityMapper()
        sample_candidates = [mapper.sample_create_object(sample_resource)
                             for sample_resource in sample_resources]
        robot_list = list(self.get_robot_settings())
        validator = ConfigValidator(self.context.validation_service,
                                    robot_list,
                                    reagent_type.category)
        return expected_sample_name, sample_candidates, validator

    def _get_sample_name(self, category):
        adjusted_name = category.replace(' ', '_')
        adjusted_name = re.sub('\W+', '', adjusted_name)
        return 'IndexConfig_{}'.format(adjusted_name)

    def _target_pos_sort_key(self, analyte):
        return analyte.well.index_down_first

    @abstractmethod
    def get_robot_settings(self):
        pass


class SampleSheetExtension(GeneralExtension):
    """
    Provides helper methods for creating a CSV
    """
    __metaclass__ = ABCMeta

    NONE = "<none>"

    def __init__(self, context):
        super(SampleSheetExtension, self).__init__(context)
        self.column_count = 9

    def header(self, name):
        return self.line("[{}]".format(name))

    def udf(self, name):
        """Returns the UDF if available, otherwise self.NONE. Provided for readability"""
        try:
            return self.context.current_step.udf_map[name].value
        except KeyError:
            return self.NONE

    def line(self, *args):
        """
        Generates one line of the sample sheet, CSV formatted

        Example: Calling with self.line("a", "b") will produce 'a,b,,,,,,,'
        """
        # TODO: The example shows commas in each line. Is that actually required?
        arg_list = list(args) + [""] * (self.column_count - len(args))
        return ",".join(map(str, arg_list))


class TemplateExtension(DriverFileExtension):
    """
    Creates driver files from templates
    """
    __metaclass__ = ABCMeta

    NONE = "<none>"

    def __init__(self, context):
        super(TemplateExtension, self).__init__(context)
        file_name = sys.modules[self.__module__].__file__
        self.template_dir = os.path.dirname(file_name)
        self.module_name = self.__module__.split(".")[-1]

        # Search for a template with the same name as the module:
        # If the module is called `example_tapestation_file.py`, this will
        # search for any file that starts with `example_tapestation_file` and
        # ends with j2 (the default jinja template extension)
        candidates = list()
        for candidate_file in os.listdir(self.template_dir):
            candidate_file_parts = candidate_file.split(".")
            if candidate_file_parts[0] == self.module_name and candidate_file_parts[-1] == "j2":
                candidates.append(candidate_file)
        if len(candidates) > 1:
            raise ValueError("More than one template file found: ", ",".join(candidates))
        self.default_template_name = candidates[0] if len(candidates) == 1 else None
        self.output_by_input_id = None

    def build_artifact_dict(self):
        output_by_input_id = dict()
        pairs = self.context.artifact_service.all_aliquot_pairs()
        for pair in pairs:
            output_by_input_id[pair.input_artifact.id] = pair.output_artifact
        self.output_by_input_id = output_by_input_id

    def get_output(self, input_id):
        if self.output_by_input_id is None:
            self.build_artifact_dict()
        return self.output_by_input_id[input_id]

    @property
    def template_path(self):
        """Returns the name of the template. By default, it will use the convention of returning the template
        named `<current module>.templ.*` if one is found."""
        return os.path.join(self.template_dir, self.default_template_name)

    def content(self):
        with open(self.template_path, 'r') as fs:
            text = fs.read()
            text = codecs.decode(text, "utf-8")
            windows_eol = '\r\n'
            newline_sequence = windows_eol if windows_eol in text else '\n'
            template = Template(text, newline_sequence=newline_sequence)
            rendered = template.render(ext=self)
            return rendered


class ExtensionTest(object):
    def __init__(self, pid):
        self.pid = pid


class NoTestsFoundException(Exception):
    pass


class NoFrozenDataFoundException(Exception):
    pass


class ExtensionTestLogFilter(logging.Filter):
    """A filter applied to log handlers used during testing. Filters to only the namespaces required."""

    def filter(self, record):
        if not record.name.startswith("clarity_"):
            return False
        else:
            if record.name.startswith("clarity_ext.extensions"):
                return False
            return True
