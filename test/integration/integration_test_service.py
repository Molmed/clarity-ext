"""Help classes to manage integration tests"""


class IntegrationTest:
    def __init__(self, pid=None, run_argument_dict=None, update_matrix=None):
        self.run_argument_dict = {}
        if pid:
            self.run_argument_dict = {"pid": pid}
        if run_argument_dict:
            self.run_argument_dict.update(run_argument_dict)

        if update_matrix:
            self.preparer = IntegrationTestPrepare(update_matrix)

    def pid(self):
        return self.run_argument_dict["pid"]


class IntegrationTestPrepare:
    def __init__(self, update_matrix):
        self.update_matrix = update_matrix

    def prepare(self, artifact_service):
        input_artifacts = artifact_service.all_input_artifacts()
        artifact_dict = {artifact.id: artifact for artifact in input_artifacts}
        self._check_artifacts_exists(artifact_dict)
        update_queue = []
        for update_row in self.update_matrix:
            art_id = update_row[0]
            udf_name = update_row[1]
            value = update_row[2]
            artifact = artifact_dict[art_id]
            artifact.set_udf(udf_name, value)
            update_queue.append(artifact)

        artifact_service.update_artifacts(update_queue)

    def _check_artifacts_exists(self, artifact_dict):
        for update_row in self.update_matrix:
            art_id = update_row[0]
            if art_id not in artifact_dict:
                raise ArtifactsNotFound("Given lims-id is not matching artifacts in step ({})".format(art_id))


class ArtifactsNotFound(Exception):
    pass



