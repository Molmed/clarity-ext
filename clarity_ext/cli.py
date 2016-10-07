from __future__ import print_function
import sys
import click
import logging
from clarity_ext.integration import IntegrationTestService
from clarity_ext.extensions import ExtensionService
import os
import yaml
import time

config = None
logger = None


@click.group()
@click.option("--level", default="INFO")
def main(level):
    """
    :param level: ["DEBUG", "INFO", "WARN", "ERROR"]
    :param cache: Set to a cache name if running from a cache (or caching)
                This is used to ensure reproducible and fast integration tests
    :return:
    """
    global config
    global logger
    ExtensionService.initialize_logging(level.upper())
    logger = logging.getLogger(__name__)

    if os.path.exists("clarity-ext.config"):
        with open("clarity-ext.config", "r") as f:
            config = yaml.load(f)


@main.command()
@click.argument("module")
def validate(module):
    """
    Validates the extension if there exists frozen data for it.
    Can use regex to match extensions.

    Note that during development, one may have stray *.pyc files
    hanging around (that don't have a corresponding *.py file)
    so they need to be cleaned before calling
    """
    import time
    t1 = time.time()
    integration_svc = IntegrationTestService()
    validation_exceptions = integration_svc.validate(module, config)
    delta = time.time() - t1
    if validation_exceptions == 0:
        print("\nAll integration tests ran successfully ({:.3f}s)".format(delta))
    else:
        sys.exit(validation_exceptions)


@main.command()
@click.argument("module")
@click.argument("mode")
@click.option("--args")
@click.option("--cache", type=bool)
def extension(module, mode, args, cache):
    """Loads the extension and executes the integration tests.

    :param mode: One of
        exec: Execute the code in normal mode
        test: Test the code locally
        freeze: Freeze an already created test (move from test-run to test-frozen)
        validate: Test the code locally, then compare with the frozen directory
    :param args: Dynamic parameters to the extension
    :param cache: Specifies if the cache should be used. If None, the default for `mode` will be used.
    """
    try:
        extension_svc = ExtensionService()
        extension_svc.execute(module, mode, args, config, use_cache=cache)
    except Exception:
        logger.exception("Exception while running extension")
        raise Exception("There was an exception while running the extension. " +
                        "Refer to the file 'Step log' if available or {} on the application server for details."
                        .format(os.path.join(ExtensionService.PRODUCTION_LOGS_DIR,
                                             ExtensionService.PRODUCTION_LOG_NAME)))

if __name__ == "__main__":
    main()

