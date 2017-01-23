from clarity_ext.domain import Container
from mock import MagicMock
from clarity_ext.repository.step_repository import StepRepository
from clarity_ext.context import ExtensionContext
from clarity_ext.service import ArtifactService, FileService, ClarityService
from clarity_ext.domain.analyte import Analyte
from clarity_ext.domain.container import Well
from clarity_ext.domain.container import ContainerPosition
from clarity_ext.domain.aliquot import Sample
from clarity_ext.domain.artifact import Artifact
from clarity_ext.domain.result_file import ResultFile
from clarity_ext.domain.shared_result_file import SharedResultFile
from clarity_ext.domain.udf import UdfMapping


# A temporary udf mapping to map from the old UDF map to the new, will be removed later (used to limit the size of the
# commit)
TEST_UDF_MAP = {
    "volume": "Current sample volume (ul)",  # current_sample_volume_ul
    "concentration_ngul": "Conc. Current (ng/ul)",  # udf_conc_current_ngul
    "requested_volume": "Target vol. (ul)",  # udf_target_vol_ul
    "requested_concentration_ngul": "Target conc. (ng/ul)",  # udf_target_conc_ngul
    "concentration_nm": "Conc. Current (nM)",  # udf_conc_current_nm
    "requested_concentration_nm": "Target conc. (nM)",  # udf_target_conc_nm

    # These didn't map directly to anything real:
    "concentration": "concentration",
    "requested_concentration": "requested_concentration"
}


def fake_shared_result_file(artifact_id=None, name=None, udfs=None):
    udf_map = UdfMapping(udfs)
    api_resource = MagicMock()
    return SharedResultFile(api_resource=api_resource,
                            id=artifact_id, name=name,
                            udf_map=udf_map)


def fake_result_file(artifact_id=None, name=None, container_id=None, well_key=None,
                     is_input=None, udfs=None, **kwargs):
    """
    :param artifact_id: Artifact name
    :param name: Artifact name
    :param container_id: Container ID
    :param well_key: Location of the artifact in the container, e.g. A:1
    :param is_input: True if this is an input artifact, false if not. TODO: Does that ever make sense for result files?
    :param udfs: Mapping of UDFs as they would appear in Clarity (e.g. {"Concentration": 10})
    :param kwargs: Mapping of UDFs that use legacy names (will be refactored). Ignored if udfs is used.
    """
    container = fake_container(container_id=container_id)
    pos = ContainerPosition.create(well_key)
    well = Well(pos, container)
    api_resource = MagicMock()
    if udfs is None:
        udfs = {TEST_UDF_MAP[key]: value for key, value in kwargs.items()}
    udf_map = UdfMapping(udfs)
    ret = ResultFile(api_resource=api_resource, is_input=is_input, id=artifact_id, samples=None, udf_map=udf_map,
                     name=name, well=well)

    if container:
        container.set_well(well.position, artifact=ret)
    return ret


def fake_analyte(container_id=None, artifact_id=None, sample_ids=None, analyte_name=None,
                 well_key=None, is_input=None, is_control=False, api_resource=None, udfs=None,
                 **kwargs):
    """
    Creates a fake Analyte domain object

    :container_id: The ID of the Container
    :artifact_id: The ID of the Artifact
    :sample_id: The ID of the Sample
    :analyte_name: The name of the Analyte
    :well_key: The locator key for the well, e.g. "A1"
    :is_input: True if the analyte is an input analyte, False otherwise.
    :udfs: A map of udfs in the name that appears in Clarity.
    :kwargs: UDFs, where the udfs must be in the test udf mapping. Ignored if udfs is provided.
    """
    if udfs is None:
        udfs = {TEST_UDF_MAP[key]: value for key, value in kwargs.items()}
    # TODO: Always have an api_resource, remove from signature
    api_resource = MagicMock()
    api_resource.udf = udfs
    udf_map = UdfMapping(udfs)
    container = fake_container(container_id)
    pos = ContainerPosition.create(well_key)
    well = Well(pos, container)
    if not isinstance(sample_ids, list):
        sample_ids = [sample_ids]
    samples = [Sample(id, id, MagicMock()) for id in sample_ids]
    analyte = Analyte(api_resource=api_resource, is_input=is_input,
                      name=analyte_name, well=well, is_control=is_control,
                      samples=samples, udf_map=udf_map)
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


def mock_analytes_to_result_files_service():
    return mock_artifact_service(analytes_to_result_files_set)


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
    return step_repo


def mock_context(artifact_service=None, step_repo=None):
    session = MagicMock()
    file_service = MagicMock()
    current_user = MagicMock()
    step_logger_service = MagicMock()
    return ExtensionContext(session=session,
                            artifact_service=artifact_service,
                            file_service=file_service,
                            current_user=current_user,
                            step_logger_service=step_logger_service,
                            clarity_service=MagicMock(),
                            dilution_service=MagicMock(),
                            step_repo=step_repo)


def mock_clarity_service(artifact_set):
    repo = MagicMock()
    repo.all_artifacts = artifact_set
    svc = ClarityService(repo)
    return svc


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
                      concentration_ngul=134.0, volume=30.0),
         fake_analyte("cont-id3", "art-id1", "sample1", "art-name1", "B:5", False,
                      requested_concentration_ngul=100.0, requested_volume=20.0)),
        (fake_analyte("cont-id2", "art-id2", "sample2", "art-name2", "A:5", True,
                      concentration_ngul=134.0, volume=40.0),
         fake_analyte("cont-id4", "art-id2", "sample2", "art-name2", "A:3", False,
                      requested_concentration_ngul=100.0, requested_volume=20.0)),
        (fake_analyte("cont-id2", "art-id3", "sample3", "art-name3", "B:7", True,
                      concentration_ngul=134.0, volume=50.0),
         fake_analyte("cont-id3", "art-id3", "sample3", "art-name3", "D:6", False,
                      requested_concentration_ngul=100.0, requested_volume=20.0)),
        (fake_analyte("cont-id2", "art-id4", "sample4", "art-name4", "E:12", True,
                      concentration_ngul=134.0, volume=60.),
         fake_analyte("cont-id4", "art-id4", "sample4", "art-name4", "E:9", False,
                      requested_concentration_ngul=100.0, requested_volume=20.0))
    ]
    return ret


def analytes_to_result_files_set():
    return [
        (fake_analyte("cont-id1", "art-id1", "sample1", "art-name1", "A:1", True,
                      udfs={"Concentration": 10, "Volume": 100}),
         fake_result_file("art-id1", "art-name1", "cont-id1", "B:1", False,
                          udfs={"Concentration": 10, "Volume": 100}))
    ]


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


def mock_context(**kwargs):
    """Creates a mock with the service provided as keyword arguments, filling the rest with MagicMock"""

    for arg in ["session", "artifact_service", "file_service", "current_user", "step_logger_service",
                "step_repo", "clarity_service", "dilution_service", "upload_file_service"]:
        kwargs.setdefault(arg, MagicMock())
    return ExtensionContext(**kwargs)
