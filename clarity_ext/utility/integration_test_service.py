"""Help classes to manage integration tests"""
from itertools import chain


class IntegrationTest:
    """
    Option to update a context to a specified state before the integration test is run.
    Context state is updated by either update_matrix_by_limsid, or update_matrix_by_artnames,
    or both.

    Format for update_matrix_by_limsid:
    [
        ('limsid', 'field name', field value),
        ...
    ]

    Format for update_matrix_by_artnames:
    [
        ('input/output ref', 'artifact name', 'field name', field value),
        ...
    ]
    with input/output ref either of:
        'input'
        'output'
    """

    def __init__(self, pid=None, run_argument_dict=None, update_matrix_by_limsid=None,
                 update_matrix_by_artnames=None, commit=True):
        """
        :param commit: Set to False to override all calls to commit on the context object.
        """
        self.run_argument_dict = {}
        if pid:
            self.run_argument_dict = {"pid": pid, "commit": commit}
        if run_argument_dict:
            self.run_argument_dict.update(run_argument_dict)

        if not update_matrix_by_limsid:
            update_matrix_by_limsid = []

        self.preparer = None
        self.preparer = IntegrationTestPrepare(
            update_matrix_by_limsid=update_matrix_by_limsid, update_matrix_by_artnames=update_matrix_by_artnames)
        self.commit = commit

    def pid(self):
        return self.run_argument_dict["pid"]

    def __getitem__(self, item):
        return self.run_argument_dict[item]

    def __repr__(self):
        return repr(self.run_argument_dict)


class IntegrationTestPrepare:

    def __init__(self, update_matrix_by_limsid=None, update_matrix_by_artnames=None):
        self._update_matrix_by_limsid = update_matrix_by_limsid
        self._update_matrix_by_artnames = update_matrix_by_artnames
        self._update_matrix = None
        # artifact service is not defined in outer scope until the prepare
        # method is called
        self.artifact_service = None

    def prepare(self, artifact_service):
        self.artifact_service = artifact_service
        artifacts = chain(artifact_service.all_input_artifacts(),
                          artifact_service.all_output_artifacts())
        artifact_dict = {artifact.id: artifact for artifact in artifacts}
        self._check_artifacts_exists(artifact_dict)
        update_queue = []
        for update_row in self._get_update_matrix():
            art_id = update_row[0]
            udf_name = update_row[1]
            value = update_row[2]
            artifact = artifact_dict[art_id]
            artifact.udf_map[udf_name] = value
            update_queue.append(artifact)

        artifact_service.update_artifacts(update_queue)

    def _check_artifacts_exists(self, artifact_dict):
        for update_row in self._get_update_matrix():
            art_id = update_row[0]
            if art_id not in artifact_dict:
                raise ArtifactsNotFound(
                    "Given lims-id is not matching artifacts in step ({})".format(art_id))

    def _get_update_matrix(self):
        if not self._update_matrix:
            matrix = self._transform_update_matrix_by_artnames(
                update_matrix_by_artnames=self._update_matrix_by_artnames)
            if not matrix:
                matrix = []
            if not self._update_matrix_by_limsid:
                self._update_matrix_by_limsid = []
            self._update_matrix = self._update_matrix_by_limsid + matrix
        return self._update_matrix

    def _transform_update_matrix_by_artnames(self, update_matrix_by_artnames=None):
        if not update_matrix_by_artnames:
            return
        update_matrix_by_limsid = []
        for row in update_matrix_by_artnames:
            artifact = self._fetch_artifact(
                input_output_ref=row[0], artifact_name=row[1])
            new_row = ("{}".format(artifact.id), row[2], row[3])
            update_matrix_by_limsid.append(new_row)
        return update_matrix_by_limsid

    def _fetch_artifact(self, input_output_ref=None, artifact_name=None):
            if input_output_ref == 'input':
                artifacts = self.artifact_service.all_input_artifacts()
            elif input_output_ref == 'output':
                artifacts = self.artifact_service.all_output_artifacts()
            else:
                raise ValueError(
                    "Not recognized key word in matrix, should be either ''input'' or ''output'', {}".format(row[0]))
            arts = [art for art in artifacts if art.name == artifact_name]
            return arts[0]


class ArtifactsNotFound(Exception):
    pass



