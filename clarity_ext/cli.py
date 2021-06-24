
import sys
import click
import logging
from clarity_ext.integration import IntegrationTestService
from clarity_ext.extensions import ExtensionService
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
    config = load_config()


def load_config():
    """
    Searches for a config file named 'clarity-ext.config' in the following order:
    * the current directory
    * ~/.config/clarity-ext/
    * /etc/clarity-ext/

    Returns a default config if none is found
    """
    config = dict()
    search_path = [".", os.path.expanduser("~/.config/clarity-ext/"), "/etc/clarity-ext/"]

    for root in search_path:
        fpath = os.path.join(root, "clarity-ext.config")
        if os.path.exists(fpath):
            with open(fpath, "r") as f:
                config = yaml.safe_load(f)

    # Add default values required for execution:
    if "test_root_path" not in config:
        config["test_root_path"] = "./clarity_ext_scripts/int_tests"
    if "frozen_root_path" not in config:
        config["frozen_root_path"] = "./clarity_ext_scripts/int_tests"
    if "exec_root_path" not in config:
        config["exec_root_path"] = "."

    return config


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


modes = [ExtensionService.RUN_MODE_TEST,
         ExtensionService.RUN_MODE_EXEC, "exec", "test", "tape"]


@main.command()
@click.argument("module")
@click.argument("mode", type=click.Choice(modes))
@click.option("--args")
@click.option("--description", type=str)
@click.option("--cache", type=bool)
def extension(module, mode, args, cache, description):
    """Loads the extension and executes the integration tests.

    :param mode: One of
        exec: Execute the code in normal mode
        test: Test the code locally
        tape: Works the same way as test, but uses a 'tape file', i.e. a recording of all requests
              and responses. If the tape file already exists, runs the test on the tape file
              results. If the user is happy with the results they should save the tape. The CI
              will then run all the tapes.
    :param args: Dynamic parameters to the extension
    """
    global config
    default_logging()
    try:
        # Parse the run arguments list:
        if args and isinstance(args, str):
            separated = args.split(" ")
            key_values = (argument.split("=") for argument in separated)
            args = [{key: value for key, value in key_values}]

        extension_svc = ExtensionService(lambda msg: print(msg))
        if mode == ExtensionService.RUN_MODE_TEST:
            extension_svc.set_log_strategy(log_level, True, False, True)
            extension_svc.run_test(config, args, module, True, cache)
        elif mode == ExtensionService.RUN_MODE_TAPE:
            extension_svc.set_log_strategy(log_level, True, False, True)
            extension_svc.run_test(config, args, module, True, False,
                                   tape=True, description=description)
        elif mode == ExtensionService.RUN_MODE_EXEC:
            extension_svc.set_log_strategy(
                log_level, False, True, True, "/opt/clarity-ext/logs", "extensions.log")
            extension_svc.run_exec(config, args, module)
        else:
            raise NotImplementedError("Mode '{}' is not implemented".format(mode))
    except Exception as ex:
        if mode == "test":
            # Just re-raise when testing - to keep the stacktrace
            raise
        logger.exception("Exception while running extension")
        msg = "There was an exception while running the extension: '{}'. ".format(ex) + \
              "Refer to the file 'Step log' if available."
        if extension_svc.rotating_file_path:
            msg += " The application log is available in {}.".format(
                extension_svc.rotating_file_path)
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


if __name__ == "__main__":
    main()
