from clarity_ext.domain import Container, Analyte, Well, ContainerPosition, Sample, Artifact
from mock import MagicMock
from clarity_ext.service import ArtifactService, FileService


def fake_analyte(container_id=None, artifact_id=None, sample_id=None, analyte_name=None,
                 well_key=None, is_input=None, **kwargs):
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
    container = Container(container_type=Container.CONTAINER_TYPE_96_WELLS_PLATE)
    container.id = container_id
    container.name = container_id
    pos = ContainerPosition.create(well_key)
    well = Well(pos, container)
    sample = Sample(sample_id)
    api_resource = None
    analyte = Analyte(api_resource, analyte_name, well, sample, **kwargs)
    analyte.id = artifact_id
    analyte.is_input = is_input
    analyte.generation_type = Artifact.PER_INPUT
    well.artifact = analyte
    return analyte


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
                      concentration=134, volume=30),
         fake_analyte("cont-id3", "art-id1", "sample1", "art-name1", "B:5", False,
                      target_concentration=100, target_volume=20)),
        (fake_analyte("cont-id2", "art-id2", "sample2", "art-name2", "A:5", True,
                      concentration=134, volume=40),
         fake_analyte("cont-id4", "art-id2", "sample2", "art-name2", "A:3", False,
                      target_concentration=100, target_volume=20)),
        (fake_analyte("cont-id2", "art-id3", "sample3", "art-name3", "B:7", True,
                      concentration=134, volume=50),
         fake_analyte("cont-id3", "art-id3", "sample3", "art-name3", "D:6", False,
                      target_concentration=100, target_volume=20)),
        (fake_analyte("cont-id2", "art-id4", "sample4", "art-name4", "E:12", True,
                      concentration=134, volume=60),
         fake_analyte("cont-id4", "art-id4", "sample4", "art-name4", "E:9", False,
                      target_concentration=100, target_volume=20))
    ]
    return ret
