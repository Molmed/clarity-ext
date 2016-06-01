from genologics.entities import EntityListDescriptor, StringDescriptor, Process, Entity
from genologics.lims import Lims


class PrepareMocking:
    """
    Prepare genologics.entities for an entity based mock by
    monkey patching methods. Classes derived from Entity in genologics.entities
    can then be faked without getting data from remote db.
    NOTE! This monkey is not complete, right now it's just adapted for the
    dilution script. It has to be updated for future extended testing.
    Process.input_output_maps is not yet overwritten.
    """

    def __init__(self):

        self._overwrite_entity()
        self._overwrite_string_descriptor()
        self._overwrite_process()
        self._overwrite_lims()
        self._overwrite_entity_list_descriptor()

    def reset(self):
        EntityListDescriptor.__get__ = self.entity_list_descriptor_get
        StringDescriptor.__get__ = self.string_descriptor_get
        StringDescriptor.__set__ = self .string_descriptor_set
        Process.all_inputs = self.process_all_inputs
        Process.all_outputs = self.process_all_outputs
        Lims.check_version = self.lims_check_version
        Lims.get_batch = self.lims_get_batch

    def _overwrite_entity_list_descriptor(self):
        def __get__(self, instance, cls):
            if self.tag not in instance.get_entity_list_dict():
                instance.get_entity_list_dict()[self.tag] = []
            return instance.get_entity_list_dict()[self.tag]

        self.entity_list_descriptor_get = EntityListDescriptor.__get__
        EntityListDescriptor.__get__ = __get__

    def _overwrite_entity(self):
        def get_descriptor_dict(self):
            if not hasattr(self, 'descriptor_dict'):
                self.descriptor_dict = {}
            return self.descriptor_dict

        def get_entity_list_dict(self):
            if not hasattr(self, 'entity_list_dict'):
                self.entity_list_dict = {}
            return self.entity_list_dict

        Entity.get_descriptor_dict = get_descriptor_dict
        Entity.get_entity_list_dict = get_entity_list_dict

    def _overwrite_string_descriptor(self):
        def __get__(self, instance, cls):
            return instance.get_descriptor_dict()[self.tag]

        def __set__(self, instance, value):
            instance.get_descriptor_dict()[self.tag] = value

        self.string_descriptor_get = StringDescriptor.__get__
        self.string_descriptor_set = StringDescriptor.__set__
        StringDescriptor.__get__ = __get__
        StringDescriptor.__set__ = __set__

    def _overwrite_process(self):
        def get_input_artifact_list(self):
            if not hasattr(self, 'input_artifact_list'):
                self.input_artifact_list = []
            return self.input_artifact_list

        def get_output_artifact_list(self):
            if not hasattr(self, 'output_artifact_list'):
                self.output_artifact_list = []
            return self.output_artifact_list

        def all_inputs(self,unique=True, resolve=False):
            return self.get_input_artifact_list()

        def all_outputs(self,unique=True, resolve=False):
            return self.get_output_artifact_list()

        self.process_all_inputs = Process.all_inputs
        self.process_all_outputs = Process.all_outputs
        Process.get_input_artifact_list = get_input_artifact_list
        Process.get_output_artifact_list = get_output_artifact_list
        Process.all_inputs = all_inputs
        Process.all_outputs = all_outputs

    def _overwrite_lims(self):
        def check_version(self):
            pass

        def get_batch(self, instances, force=False):
            return instances

        self.lims_check_version = Lims.check_version
        self.lims_get_batch = Lims.get_batch
        Lims.check_version = check_version
        Lims.get_batch = get_batch