class ArtifactRepository(object):
    def __init__(self, session, clarity_mapper):
        self.session = session
        self.clarity_mapper = clarity_mapper

    def get(self, name=None, process_type=None):
        """Returns a list of resolved artifacts that match the search criteria"""
        artifacts = self.session.api.get_artifacts(name=name, process_type=process_type)
        for artifact in artifacts:
            yield self.clarity_mapper.artifact_create_object(artifact)
