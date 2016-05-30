from __future__ import print_function
import os
import shutil
import logging
from driverfile import DriverFileIntegrationTests


# Creates an integration test config file based on convention
# i.e. position and contents of the script classes themselves.
class ConfigFromConventionProvider:

    @classmethod
    def _enumerate_modules(cls, root_name):
        import importlib
        import pkgutil
        root = importlib.import_module(root_name)
        for loader, module_name, is_pkg in pkgutil.walk_packages(root.__path__):
            module = loader.find_module(module_name).load_module(module_name)
            yield module

    @classmethod
    def _enumerate_extensions(cls, root_pkg):
        for module in cls._enumerate_modules(root_pkg):
            if hasattr(module, "Extension"):
                yield module

    @classmethod
    def get_extension_config(cls, root_pkg):
        for extension in cls._enumerate_extensions(root_pkg):
            # NOTE: For some reason, the root does not get added to the enumerated modules
            entry = dict()
            entry["module"] = "{}.{}".format(root_pkg, extension.__name__)
            yield entry


class IntegrationTestService:
    CACHE_NAME = "test_run_cache"

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.CACHE_FULL_NAME = "{}.sqlite".format(self.CACHE_NAME)

    @staticmethod
    def _test_run_directory(config_entry, pid):
        return os.path.join(".", "runs", config_entry["name"], pid, "test-run")

    @staticmethod
    def _test_frozen_directory(config_entry, pid):
        return os.path.join(".", "runs", config_entry["name"], pid, "test-frozen")

    def _validate_run(self, entry):
        if entry["cmd"] == "driverfile":
            test_provider = DriverFileIntegrationTests()
            for test in entry["tests"]:
                run_path = self._test_run_directory(entry, test["pid"])
                frozen_path = self._test_frozen_directory(entry, test["pid"])
                test_provider.validate(run_path, frozen_path, test)

    def _freeze_test(self, entry, test):
        source = self._test_run_directory(entry, test["pid"])

        if not os.path.exists(source):
            raise FreezingBeforeRunning()

        target = self._test_frozen_directory(entry, test["pid"])
        print("Freezing test {} => {}".format(source, target))
        if os.path.exists(target):
            print("Target already exists, removing it")
            shutil.rmtree(target)
        shutil.copytree(source, target)

    def validate(self, module, config):
        """
        Runs the tests on the frozen tests. The idea is that this should run (at least) on every official build,
        thus validating every script against a known state

        :param config:
        :return:
        """
        from clarity_ext.extensions import ExtensionService
        extension_svc = ExtensionService()
        config_obj = ConfigFromConventionProvider.get_extension_config(module)
        exception_count = 0

        for entry in config_obj:
            module = entry["module"]
            print("- {}".format(module))
            from clarity_ext.extensions import ResultsDifferFromFrozenData
            try:
                extension_svc.execute(module, "test", None, config, artifacts_to_stdout=False, print_help=False)
            except ResultsDifferFromFrozenData as e:
                print("Error: {}".format(e.message))
                exception_count += 1
        return exception_count


class FreezingBeforeRunning(Exception):
    """Thrown when the user tries to freeze a state before doing an initial run"""
    pass

