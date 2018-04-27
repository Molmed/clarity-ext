import logging
from clarity_ext.domain import Container, Artifact, Sample


class ClarityService(object):
    """
    General service for handling objects in Clarity.

    Note that artifacts (e.g. Analytes) are still handled in the ArtifactService
    """

    def __init__(self, clarity_repo, step_repo, clarity_mapper, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.clarity_repository = clarity_repo
        self.step_repository = step_repo
        self.clarity_mapper = clarity_mapper

    def update(self, domain_objects, ignore_commit=False):
        """Updates the domain object"""
        artifacts = list()
        other_domain_objects = list()
        for item in domain_objects:
            if isinstance(item, Artifact):
                artifacts.append(item)
            elif isinstance(item, Container) or isinstance(item, Sample):
                # TODO: This is temporarily limited to Sample and Container. LIMS-1057
                other_domain_objects.append(item)
            else:
                raise NotImplementedError("No update method available for {}".format(type(item)))

        for domain_object in other_domain_objects:
            self.update_single(domain_object, ignore_commit)

        if ignore_commit:
            # TODO: When ignoring commits, the changes that would have been committed are not logged anymore
            # Ignoring commits should only skip writing to the backend, but should log the changes that should have
            # happened. Recommended fix is to update all domain objects through the repository and use a repo that logs
            # only when called.
            self.logger.info("A request for updating artifacts was ignored. "
                             "View log to see which properties have changed.")
            return

        if len(artifacts) > 0:
            self._update_artifacts(artifacts)

    def _update_artifacts(self, artifacts):
        # Filter out artifacts that don't have any updated fields:
        map_artifact_to_resource = {artifact: artifact.get_updated_api_resource()
                                    for artifact in artifacts}
        if sum(1 for value in map_artifact_to_resource.values()
               if value is not None) == 0:
            return 0
        ret = self.step_repository.update_artifacts([res for res in map_artifact_to_resource.values()
                                                     if res is not None])

        # Now update all the artifacts so they have the latest version of the api resource.
        # This is a bit strange, it would be cleaner to create a new API resource from the domain
        # object, but for simplicity we currently keep the original API resource.
        for artifact, resource in map_artifact_to_resource.items():
            if resource:
                artifact.api_resource = resource
        return ret

    def update_single(self, domain_object, ignore_commit):
        # TODO: This is a quick-fix to support changing container names
        if isinstance(domain_object, Container):
            api_resource = domain_object.api_resource
            if api_resource.name != domain_object.name:
                self.logger.info("Updating name of {} from {} to {}".format(domain_object,
                                                                            api_resource.name, domain_object.name))
                api_resource.name = domain_object.name
                # Update UDFs. TODO: Clean this up and do it the same way for all resources
                for udf_name in api_resource.udf:
                    if api_resource.udf[udf_name] != domain_object.udf_map[udf_name].value:
                        api_resource.udf[udf_name] = domain_object.udf_map[udf_name].value

                if not ignore_commit:
                    self.clarity_repository.update(api_resource)
        elif isinstance(domain_object, Sample):
            # TODO: Update in a consistent way. LIMS-1057
            api_resource = self.clarity_mapper.create_resource(domain_object)
            if not ignore_commit:
                self.clarity_repository.update(api_resource)
        else:
            raise NotImplementedError("The type '{}' isn't implemented".format(type(domain_object)))
