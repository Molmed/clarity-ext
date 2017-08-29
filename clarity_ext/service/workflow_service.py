import re
from clarity_ext.domain.workflow import *


class VersionedEntity(object):
    VERSIONED_PATTERN = r"(.+) v(\d+)"

    def __init__(self, uri, name, entity):
        self.uri = uri
        self.name = name
        self.entity = entity
        m = re.match(self.VERSIONED_PATTERN, self.name)
        self.name_without_version, self.version = m.groups() if m else (self.name, 0)
        self.version = int(self.version)

    @property
    def key(self):
        return self.name_without_version, self.version

    def __repr__(self):
        return repr((self.name_without_version, self.version))


class ArtifactTempHelper(object):
    # Helper for getting extra information about an artifact related to the stages it's in.
    # TODO: Move this to the artifact object itself when this gets ported into clarity-ext
    @staticmethod
    def get_current_stage(artifact):
        stages = artifact.api_resource.root.find("workflow-stages").findall("workflow-stage")
        in_progress_stage = [stage for stage in stages if stage.attrib["status"] == "IN_PROGRESS"]
        if len(in_progress_stage) != 1:
            raise ValueError("Unexpected number of stages in progress: {}".format(len(in_progress_stage)))
        return in_progress_stage[0].attrib["uri"]

    @classmethod
    def get_current_workflow(cls, artifact):
        stage_uri = cls.get_current_stage(artifact)
        return re.sub(r"/stages/\d+", "", stage_uri)


class WorkflowService(object):
    def __init__(self, session):
        self.session = session
        self.workflow_list = None  # TODO: lazy property

    def get_workflows(self):
        # NOTE: The genologics pip package fetches the whole artifact without needing to
        # when you access either the name or the status. So we're parsing the XML directly:
        # TODO: Use the mapper
        from genologics.entities import Workflow as ApiWorkflow
        def get_workflows_raw():
            # Returns a tuple of (status, uri, name)
            uri = self.session.api.get_uri("configuration", "workflows")
            for workflow in self.session.api.get(uri):
                yield tuple(workflow.attrib.get(attrib) for attrib in ["status", "uri", "name"])

        for status, uri, name in get_workflows_raw():
            workflow_id = int(uri.split("/")[-1])
            api_resource = ApiWorkflow(self.session.api, uri=uri)
            yield Workflow(id=workflow_id, status=status, uri=uri, name=name, api_resource=api_resource)

    def get_stages(self, workflow_uri):
        workflow = self.session.api.get(workflow_uri)
        return workflow.find("stages").findall("stage")

    # TODO: Move these to a helper class
    def find_latest_version_of_stage(self, workflow_uri, search_string):
        stages = self.get_stages(workflow_uri)
        versioned_stages = [VersionedEntity(stage.attrib["uri"], stage.attrib["name"], None)
                            for stage in stages]
        matching_stages = [stage for stage in versioned_stages
                           if stage.name_without_version.lower() == search_string.lower()]
        latest_stage = sorted(matching_stages, key=lambda entity: entity.key, reverse=True)[0]
        return latest_stage.uri

    @staticmethod
    def find_latest_version_of_workflow(search_string, workflows):
        """
        Finds the workflow that matches this workflow, but using the latest version if there are several. Assumes
        that new versions are marked with a postfix on the format 'v<number>'
        """
        versioned_workflows = [VersionedEntity(uri, name, None) for name, uri in workflows.items()]
        matching_workflows = [workflow for workflow in versioned_workflows
                              if workflow.name_without_version.lower() == search_string.lower()]
        if len(matching_workflows) == 0:
            raise NoWorkflowFoundException("No workflow found using search string {}".format(search_string))
        latest_workflow = sorted(matching_workflows, key=lambda workflow: workflow.key, reverse=True)[0]
        return latest_workflow.uri


class NoWorkflowFoundException(Exception):
    pass

