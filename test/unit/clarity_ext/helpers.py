from clarity_ext.domain import Container
from mock import MagicMock
from mock import patch
from mock import PropertyMock
from clarity_ext.service import ArtifactService, FileService
from clarity_ext.repository.step_repository import StepRepository
from clarity_ext.context import ExtensionContext
from clarity_ext.domain.analyte import Analyte
from clarity_ext.domain.container import Well
from clarity_ext.domain.container import ContainerPosition
from clarity_ext.domain.aliquot import Sample
from clarity_ext.domain.artifact import Artifact
from clarity_ext.domain.result_file import ResultFile
from clarity_ext.domain.shared_result_file import SharedResultFile
from clarity_ext.repository.step_repository import DEFAULT_UDF_MAP


def fake_shared_result_file(artifact_id=None, name=None):
    udf_map = dict()
    api_resource = MagicMock()
    return SharedResultFile(api_resource=api_resource,
                            id=artifact_id, name=name,
                            artifact_specific_udf_map=udf_map)


def fake_result_file(artifact_id=None, name=None, container_id=None, well_key=None,
                     is_input=None, udf_map=None, **kwargs):
    container = fake_container(container_id=container_id)
    pos = ContainerPosition.create(well_key)
    well = Well(pos, container)
    api_resource = MagicMock()
    if not udf_map:
        udf_map = DEFAULT_UDF_MAP["ResultFile"]
    ret = ResultFile(api_resource=api_resource, is_input=is_input, id=artifact_id, sample=None,
                     name=name, well=well, artifact_specific_udf_map=udf_map, **kwargs)

    if container:
        container.set_well(well.position, artifact=ret)
    return ret


def fake_analyte(container_id=None, artifact_id=None, sample_ids=None, analyte_name=None,
                 well_key=None, is_input=None, is_control=False, udf_map=None, api_resource=None,
                 **kwargs):
    """
    Creates a fake Analyte domain object

    :container_id: The ID of the Container
    :artifact_id: The ID of the Artifact
    :sample_id: The ID of the Sample
    :analyte_name: The name of the Analyte
    :well_key: The locator key for the well, e.g. "A1"
    :is_input: True if the analyte is an input analyte, False otherwise.
    :kwargs: Any UDF. Use the key names specified in the udf_map being used.
    """
    container = fake_container(container_id)
    pos = ContainerPosition.create(well_key)
    well = Well(pos, container)
    if not isinstance(sample_ids, list):
        sample_ids = [sample_ids]
    samples = [Sample(id, id, MagicMock()) for id in sample_ids]
    if not udf_map:
        udf_map = DEFAULT_UDF_MAP['Analyte']
    analyte = Analyte(api_resource=api_resource, is_input=is_input,
                      name=analyte_name, well=well, is_control=is_control,
                      samples=samples, artifact_specific_udf_map=udf_map, **kwargs)
    analyte.id = artifact_id
    analyte.generation_type = Artifact.PER_INPUT
    well.artifact = analyte
    return analyte


def fake_container(container_id):
    if container_id:
        container = Container(
            container_type=Container.CONTAINER_TYPE_96_WELLS_PLATE)
        container.id = container_id
        container.name = container_id
    else:
        container = None
    return container


def mock_artifact_resource(resouce_id=None, sample_name=None, well_position=None):
    api_resource = MagicMock()
    if well_position:
        api_resource.location = [None, well_position]
    sample = MagicMock()
    sample.id = sample_name
    api_resource.samples = [sample]
    api_resource.id = resouce_id
    api_resource.name = sample_name
    return api_resource


def mock_container_repo(container_id=None):
    container_repo = MagicMock()
    container = None
    if container_id:
        container = fake_container(container_id=container_id)
    container_repo.get_container.return_value = container
    return container_repo


def mock_two_containers_artifact_service():
    """
    Returns an ArtifactService that works as expected, but has a mocked repository service
    """
    return mock_artifact_service(two_containers_artifact_set)


def mock_artifact_service(artifact_set):
    """
    Given a function returning a set of artifacts as they're returned from the StepInputOutputRepository,
    returns a real ArtifactService that mocks the repo.
    """
    repo = MagicMock()
    repo.all_artifacts = artifact_set
    svc = ArtifactService(repo)
    return svc


def mock_step_repository(analyte_set):
    """
    To be able to achieve a response matrix containing
    updates from update_artifacts()
    :param analyte_set:
    :return:
    """
    session = MagicMock()
    session.api = MagicMock()
    step_repo = StepRepository(session=session)
    step_repo.all_artifacts = analyte_set
    step_repo._add_to_orig_state_cache(analyte_set())
    return step_repo


def mock_context(artifact_service=None, step_repo=None):
    session = MagicMock()
    file_service = MagicMock()
    current_user = MagicMock()
    step_logger_service = MagicMock()
    return ExtensionContext(session=session, artifact_service=artifact_service,
                            file_service=file_service,
                            current_user=current_user, step_logger_service=step_logger_service,
                            step_repo=step_repo)


def mock_file_service(artifact_set):
    """
    Given a function returning a set of artifacts as they're returned from the StepInputOutputRepository,
    returns a real ArtifactService that mocks the repo.
    """
    artifact_svc = MagicMock()
    artifact_svc.all_artifacts = artifact_set
    file_repo = MagicMock()
    svc = FileService(artifact_svc, file_repo, False)
    return svc


def two_containers_artifact_set():
    """
    Returns a list of (inputs, outputs) fake analytes for a particular step.

    Analytes have been sorted, as they would be when queried from the repository.
    """
    ret = [
        (fake_analyte("cont-id1", "art-id1", "sample1", "art-name1", "D:5", True,
                      concentration_ngul=134, volume=30),
         fake_analyte("cont-id3", "art-id1", "sample1", "art-name1", "B:5", False,
                      requested_concentration_ngul=100, requested_volume=20)),
        (fake_analyte("cont-id2", "art-id2", "sample2", "art-name2", "A:5", True,
                      concentration_ngul=134, volume=40),
         fake_analyte("cont-id4", "art-id2", "sample2", "art-name2", "A:3", False,
                      requested_concentration_ngul=100, requested_volume=20)),
        (fake_analyte("cont-id2", "art-id3", "sample3", "art-name3", "B:7", True,
                      concentration_ngul=134, volume=50),
         fake_analyte("cont-id3", "art-id3", "sample3", "art-name3", "D:6", False,
                      requested_concentration_ngul=100, requested_volume=20)),
        (fake_analyte("cont-id2", "art-id4", "sample4", "art-name4", "E:12", True,
                      concentration_ngul=134, volume=60),
         fake_analyte("cont-id4", "art-id4", "sample4", "art-name4", "E:9", False,
                      requested_concentration_ngul=100, requested_volume=20))
    ]
    return ret


def print_out_dict(object_list, caption):
    print("{}:".format(caption))
    print("-----------------------------------------")
    for o in object_list:
        print("{}:".format(o))
        for key in o.__dict__:
            print("{} {}".format(key, o.__dict__[key]))
        print("-----------------------------------------\n")


def print_list(object_list, caption):
    print("{}:".format(caption))
    print("-------------------------------------------")
    for o in object_list:
        print("{}".format(o))
    print("-------------------------------------------\n")
