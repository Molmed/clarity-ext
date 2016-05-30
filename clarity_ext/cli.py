from __future__ import print_function
import sys
import click
import logging
from clarity_ext.integration import IntegrationTestService
from clarity_ext.extensions import ExtensionService
import os
import yaml

config = None


@click.group()
@click.option("--level", default="WARN")
def main(level):
    """
    :param level: ["DEBUG", "INFO", "WARN", "ERROR"]
    :param cache: Set to a cache name if running from a cache (or caching)
                This is used to ensure reproducible and fast integration tests
    :return:
    """
    global config
    if os.path.exists("clarity-ext.config"):
        with open("clarity-ext.config", "r") as f:
            config = yaml.load(f)

    logging.basicConfig(level=level.upper())


@main.command()
@click.argument("module")
def validate(module):
    """
    Validates the extension if there exists frozen data for it.
    Can use regex to match extensions.
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
def extension(module, mode, args):
    """Loads the extension and executes the integration tests.

    :param mode: One of
        exec: Execute the code in normal mode
        test: Test the code locally
        freeze: Freeze an already created test (move from test-run to test-frozen)
        validate: Test the code locally, then compare with the frozen directory
    """
    extension_svc = ExtensionService()
    extension_svc.execute(module, mode, args, config)

if __name__ == "__main__":
    main()

