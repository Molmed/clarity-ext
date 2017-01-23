from __future__ import print_function
import sys
import click
import logging
from clarity_ext.integration import IntegrationTestService
from clarity_ext.extensions import ExtensionService
from clarity_ext.service import ProcessService
from clarity_ext.tool.template_generator import TemplateNotFoundException, TemplateGenerator
import os
import yaml
import time
from clarity_ext.extensions import ResultsDifferFromFrozenData

config = None
logger = logging.getLogger(__name__)
log_level = None


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
    global log_level
    log_level = level

    if os.path.exists("clarity-ext.config"):
        with open("clarity-ext.config", "r") as f:
            config = yaml.load(f)


def default_logging():
    global log_level
    logging.basicConfig(level=log_level)


@main.command()
@click.argument("module")
def validate(module):
    """
    Validates the extension if there exists frozen data for it.
    Can use regex to match extensions.
    """
    default_logging()
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
    """
    global config
    default_logging()
    try:
        if not config:
            config = {
                "test_root_path": "./clarity_ext_scripts/int_tests",
                "frozen_root_path": "./clarity_ext_scripts/int_tests",
                "exec_root_path": "."
            }
            logger.debug("Configuration not provided, using default: {}".format(config))

        # Parse the run arguments list:
        if args and isinstance(args, basestring):
            separated = args.split(" ")
            key_values = (argument.split("=") for argument in separated)
            args = [{key: value for key, value in key_values}]

        validate_against_frozen = True # Indicates a run that should ignore the frozen directory
        if mode == "test-fresh":
            mode = "test"
            validate_against_frozen = False

        extension_svc = ExtensionService(lambda msg: print(msg))
        if mode == ExtensionService.RUN_MODE_FREEZE:
            extension_svc.run_freeze(config, args, module)
        elif mode == ExtensionService.RUN_MODE_TEST:
            extension_svc.set_log_strategy(log_level, True, False, True)
            try:
                extension_svc.run_test(config, args, module, True, cache, validate_against_frozen)
            except ResultsDifferFromFrozenData as ex:
                print("Results differ from frozen data: " + ex.message)
        elif mode == ExtensionService.RUN_MODE_EXEC:
            extension_svc.set_log_strategy(log_level, True, True, True, "/opt/clarity-ext/logs", "extensions.log")
            extension_svc.run_exec(config, args, module)
        else:
            raise NotImplementedError("Mode '{}' is not implemented".format(mode))
    except Exception as ex:
        if mode == "test":
            # Just re-raise when testing - to keep the stacktrace
            raise
        logger.exception("Exception while running extension")
        msg = "There was an exception while running the extension: '{}'. ".format(ex.message) + \
              "Refer to the file 'Step log' if available."
        if extension_svc.rotating_file_path:
            msg += " The application log is available in {}.".format(extension_svc.rotating_file_path)
        raise Exception(msg)


@main.command()
def templates():
    """
    Lists all available templates
    """
    click.echo("Available templates:")
    template_generator = TemplateGenerator()
    for template in template_generator.list_templates():
        if template.name != "_base":
            click.echo("  {}".format(template))

    click.echo()
    click.echo("Create from template by executing:")
    click.echo("  clarity-ext create <template-name> <package>")


@main.command()
@click.argument("template")
@click.argument("package")
def create(template, package):
    """
    Creates a new extension from a template.
    """
    click.echo("Creating a new '{}' extension in package '{}'...".format(template, package))
    template_generator = TemplateGenerator()
    try:
        template_generator.create(template, package)
    except TemplateNotFoundException:
        click.echo("ERROR: Can't find template called: {}".format(template))


@main.command("fix-pycharm")
@click.argument("package")
def fix_pycharm(package):
    template_generator = TemplateGenerator()
    template_generator.fix_pycharm(package)


@main.command("list-process-types")
@click.option("--contains", help="Filter to process type containing this regex pattern anywhere in the XML")
@click.option("--list-procs", help="Lists procs: all|active")
@click.option("--ui-links", is_flag=True, help="Report ui links rather than api links")
def list_process_types(contains, list_procs, ui_links):
    """Lists all process types in the lims. Uses a cache file (process-type.sqlite)."""
    process_svc = ProcessService(use_cache=True)
    for process_type in process_svc.list_process_types(contains):
        click.echo("{name}: {uri}".format(name=process_type.name, uri=process_type.uri))

        if list_procs is not None:
            if list_procs not in ["all", "active"]:
                raise ValueError("Proc status not supported: {}".format(list_procs))
            for process in process_svc.list_processes_by_process_type(process_type):
                if list_procs == "active" and process.date_run is not None:
                    continue
                uri = process.uri if not ui_links else process_svc.ui_link_process(process)
                click.echo(u" - {}: date_run={}, technician={}".format(uri,
                           process.date_run, process.technician.name))


if __name__ == "__main__":
    main()

