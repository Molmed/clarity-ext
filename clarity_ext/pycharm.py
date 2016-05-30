"""Methods specific for generating pycharm run configurations"""
from integration import ConfigFromConventionProvider


def generate_pycharm_run_config(module):
    # TODO: Implement
    config_obj = ConfigFromConventionProvider.get_config_by_convention(module)
    print config_obj

