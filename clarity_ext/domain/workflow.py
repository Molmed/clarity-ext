#from clarity_ext.domain import DomainObjectMixin


class Workflow(object):
    STATUS_ACTIVE = "ACTIVE"
    STATUS_ARCHIVED = "ARCHIVED"

    def __init__(self, id, status=None, name=None, uri=None, api_resource=None):
        self.id = id
        self.status = status
        self.name = name
        self.uri = uri
        self.api_resource = api_resource

    def __repr__(self):
        return repr(self.__dict__)


class Stage(object):
    STATUS_COMPLETE = "COMPLETE"
    STATUS_QUEUED = "QUEUED"

    EXPAND_STATE_NONE = 0
    EXPAND_STATE_MIN = 1
    EXPAND_STATE_FULL = 2

    """A stage which an artifact is in. This is a particular instance of a workflow, protocol and step"""
    def __init__(self, stage_id, status, uri, name, workflow):
        self.id = stage_id
        self.uri = uri
        self.status = status
        self.name = name
        self.workflow = workflow
        self.expand_state = self.EXPAND_STATE_NONE

    def __repr__(self):
        return "Stage<id={}, status={}, workflow={}>".format(self.id, self.status, self.workflow.id)
