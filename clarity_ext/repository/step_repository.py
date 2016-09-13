from clarity_ext.domain.artifact import Artifact
from clarity_ext.domain.analyte import Analyte
from clarity_ext.domain.result_file import ResultFile
from clarity_ext.repository.container_repository import ContainerRepository


class StepRepository(object):
    """
    Provides access to data that's available through a current step.

    All methods return the domain objects, wrapping the REST resources.

    Since the underlying library does caching, this repository does not need
    to do that.
    """

    def __init__(self, session, udf_map=None):
        """
        Creates a new StepRepository

        :param session: A session object for connecting to Clarity
        :param udf_map: A map between domain objects and user defined fields. See `DEFAULT_UDF_MAP` for details
        """
        self.session = session
        self.udf_map = udf_map or DEFAULT_UDF_MAP

    def all_artifacts(self):
        """
        Fetches all artifacts from the input output map, wraps them in to a domain object.
        From then on, the domain object knows the following:
            * From what resource was it built (for debug reasons, e.g. for getting the URL)
            * Is it an input or output artifact
            * What's the corresponding input or output object (input objects have a reference
              to the output object and vice-versa

        After this, all querying should be done on these domain objects.

        The list is not unique, i.e. artifacts will be fetched more than once.

        Performance note: This method may fetch much more data than necessary as it's designed
        for simplified use of the API. If optimal performance is required, use the underlying REST API
        instead.
        """
        input_output_maps = self.session.current_step.input_output_maps
        artifact_keys = set()
        for input, output in input_output_maps:
            artifact_keys.add(input["uri"])
            artifact_keys.add(output["uri"])
        artifacts = self.session.api.get_batch(artifact_keys)
        artifacts_by_uri = {artifact.uri: artifact for artifact in artifacts}
        for input, output in input_output_maps:
            input['uri'] = artifacts_by_uri[input['uri'].uri]
            output['uri'] = artifacts_by_uri[output['uri'].uri]

        ret = []
        # TODO: Ensure that the container repo fetches all containers in one batch call:
        container_repo = ContainerRepository()
        for input, output in input_output_maps:
            input, output = self._wrap_input_output(
                input, output, container_repo)
            ret.append((input, output))

        return ret

    def _wrap_input_output(self, input_info, output_info, container_repo):
        # Create a map of all containers, so we can fill in it while building
        # domain objects.

        # Create a fresh container repository. Then we know that only one container
        # will be created for each object in a call to this method
        input_resource = input_info["uri"]
        output_resource = output_info["uri"]
        input = self._wrap_artifact(input_resource, container_repo)
        input.is_input = True
        output = self._wrap_artifact(output_resource, container_repo)
        output.is_input = False

        gen_type = output_info["output-generation-type"]
        if gen_type == "PerInput":
            output.generation_type = Artifact.PER_INPUT
        elif gen_type == "PerAllInputs":
            output.generation_type = Artifact.PER_ALL_INPUTS
        else:
            raise NotImplementedError(
                "Generation type {} is not implemented".format(gen_type))

        output_type = output_info["output-type"]
        if output_type == "ResultFile":
            output.output_type = Artifact.OUTPUT_TYPE_RESULT_FILE
        elif output_type == "Analyte":
            output.output_type = Artifact.OUTPUT_TYPE_ANALYTE
        elif output_type == "SharedResultFile":
            output.output_type = Artifact.OUTPUT_TYPE_SHARED_RESULT_FILE
        else:
            raise NotImplementedError(
                "Output type {} is not implemented".format(output_type))

        # TODO: define all of these in the base class Artifact (before
        # check-in)

        # Add a reference to the other object for convenience:
        input.output = output
        output.input = input

        return input, output

    def _wrap_artifact(self, artifact, container_repo):
        """
        Wraps an artifact in a domain object, if one exists. The domain objects provide logic
        convenient methods for working with the domain object in extensions.
        """
        if artifact.type == "Analyte":
            return Analyte.create_from_rest_resource(artifact, self.udf_map, container_repo)
        elif artifact.type == "ResultFile":
            return ResultFile.create_from_rest_resource(artifact, self.udf_map, container_repo)
        else:
            raise Exception("Unknown type {}".format(artifact.type))

    def _wrap_artifacts(self, artifacts):
        for artifact in artifacts:
            yield self._wrap_artifact(artifact)

    def update_artifacts(self, artifacts):
        """
        Updates each entry in objects to db
        """
        response = [artifact.assigner.consume() for artifact in artifacts]
        response = sum(response, [])

        api_resources = [artifact.api_resource for artifact in artifacts]

        self.session.api.put_batch(api_resources)
        return response


"""
The default UDF map. Certain features of the library depend on some fields existing on the domain
objects that are only available through UDFs. To make the library usable without having to define
exactly the same names in different implementations, a different UDF map can be provided for
different setups. TODO: Make the UDF map configurable in the settings for the clarity-ext tool.
"""
DEFAULT_UDF_MAP = {
    "Analyte": {
        "concentration": "Conc. Current (ng/ul)",
        "target_concentration": "Target Concentration",
        "target_volume": "Target Volume",
        "volume": "Current sample volume (ul)"
    }
}
