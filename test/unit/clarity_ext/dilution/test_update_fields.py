import unittest
from clarity_ext.dilution import DILUTION_WASTE_VOLUME
from mock import MagicMock
from clarity_ext.dilution import DilutionScheme
from clarity_ext.dilution import CONCENTRATION_REF_NGUL
from clarity_ext.dilution import VOLUME_CALC_BY_CONC
from clarity_ext.service.artifact_service import ArtifactService
from clarity_ext.extensions import ExtensionContext
from test.unit.clarity_ext import helpers
from test.unit.clarity_ext.helpers import fake_analyte
from test.unit.clarity_ext.helpers import mock_step_repository
from test.unit.clarity_ext.helpers import mock_context
from test.unit.clarity_ext.helpers import *

UDF_MAP = {
    "concentration_ngul": "conc",
    "requested_concentration_ngul": "rconc",
    "volume": "volume",
}


class UpdateFieldsForDilutionTests(unittest.TestCase):

    def _init_dilution_scheme(self, concentration_ref, analyte_set=None):
        def udf_adapted_analyte_set():
            return analyte_set(udf_map=UDF_MAP)

        repo = mock_step_repository(analyte_set=udf_adapted_analyte_set)
        svc = ArtifactService(step_repository=repo)
        context = mock_context(artifact_service=svc, step_repo=repo)
        dilution_scheme = DilutionScheme.create(
            artifact_service=svc, robot_name="Hamilton",
            concentration_ref=concentration_ref, volume_calc_method=VOLUME_CALC_BY_CONC)

        return dilution_scheme, context

    def _update_fields(self, dilution_scheme, context):
        aliquot_pair_by_transfer = dilution_scheme.aliquot_pair_by_transfer
        for transfer in dilution_scheme.unsplit_transfers:
            # Make preparation, fetch the analyte to be updated
            source_analyte = aliquot_pair_by_transfer(transfer).input_artifact
            destination_analyte = aliquot_pair_by_transfer(
                transfer).output_artifact

            # Update fields for analytes
            source_analyte.set_udf("volume", max(
                transfer.source_initial_volume - transfer.sample_volume - DILUTION_WASTE_VOLUME, 0))

            destination_analyte.set_udf("conc", transfer.sample_volume *
                                        transfer.source_concentration /
                                        (transfer.sample_volume + transfer.buffer_volume))

            destination_analyte.set_udf(
                "volume", transfer.sample_volume + transfer.buffer_volume)

            context.update(source_analyte)
            context.update(destination_analyte)

        context.commit()

    def test_source_volume_update_1(self):
        dilution_scheme, context = self._init_dilution_scheme(
            concentration_ref=CONCENTRATION_REF_NGUL, analyte_set=analyte_set_with_blank)
        self._update_fields(dilution_scheme, context)
        dilute = dilution_scheme.unsplit_transfers[-1]
        expected = 29.0
        outcome = dilution_scheme.aliquot_pair_by_transfer(
            dilute).input_artifact.volume
        print(dilute.aliquot_name)
        self.assertEqual(expected, outcome)

    def test_source_volume_update_all(self):
        dilution_scheme, context = self._init_dilution_scheme(
            concentration_ref=CONCENTRATION_REF_NGUL, analyte_set=analyte_set_with_blank)
        self._update_fields(dilution_scheme, context)
        source_volume_sum = 0
        for dilute in dilution_scheme.unsplit_transfers:
            outcome = dilution_scheme.aliquot_pair_by_transfer(
                dilute).input_artifact.volume
            source_volume_sum += outcome
        expected_sum = 57.0
        self.assertEqual(expected_sum, source_volume_sum)

    def test_dilute_aliqout_matching(self):
        dilution_scheme, context = self._init_dilution_scheme(
            concentration_ref=CONCENTRATION_REF_NGUL, analyte_set=analyte_set_with_blank)
        self._update_fields(dilution_scheme, context)
        aliquot_pair_by_transfer = dilution_scheme.aliquot_pair_by_transfer
        for transfer in dilution_scheme.unsplit_transfers:
            source_aliquot = aliquot_pair_by_transfer(transfer).input_artifact
            print("transfer sample name: {}".format(transfer.aliquot_name))
            print("source aliquot sample name: {}".format(source_aliquot.name))
            self.assertEqual(transfer.aliquot_name, source_aliquot.name)

    def test_update_base(self):
        dilution_scheme, context = self._init_dilution_scheme(
            concentration_ref=CONCENTRATION_REF_NGUL, analyte_set=analyte_set_with_blank)

        self._update_fields(dilution_scheme, context)
        actual = context.response
        expected = [
            ("Analyte", "art1", "volume", "9.0"),
            ("Analyte", "art2", "volume", "20.0"),
            ("Analyte", "art2", "conc", "100.0"),
            ("Analyte", "art3", "volume", "19.0"),
            ("Analyte", "art4", "volume", "20.0"),
            ("Analyte", "art4", "conc", "100.0"),
            ("Analyte", "art5", "volume", "29.0"),
            ("Analyte", "art6", "volume", "20.0"),
            ("Analyte", "art6", "conc", "100.0"),
        ]

        self.assertEqual(expected, actual)

    def test_update_split_rows(self):
        def analyte_set_split_rows(udf_map=None):
            api_resource = MagicMock()
            api_resource.udf = {}
            return [
                (fake_analyte("cont1", "art7", "sample4", "sample4", "E:2", True, is_control=True,
                              udf_map=udf_map, api_resource=api_resource),
                 fake_analyte("cont2", "art8", "sample4", "sample4", "E:2", False, is_control=True,
                              udf_map=udf_map, api_resource=api_resource,
                              requested_concentration_ngul=100, requested_volume=20)),
                (fake_analyte("cont1", "art1", "sample1", "sample1", "B:2", True,
                              udf_map=udf_map, api_resource=api_resource,
                              concentration_ngul=100, volume=30),
                 fake_analyte("cont2", "art2", "sample1", "sample1", "B:2", False,
                              udf_map=udf_map, api_resource=api_resource,
                              requested_concentration_ngul=100, requested_volume=70)),
            ]

        dilution_scheme, context = self._init_dilution_scheme(
            concentration_ref=CONCENTRATION_REF_NGUL, analyte_set=analyte_set_split_rows)
        self._update_fields(dilution_scheme, context)

        actual = context.response
        expected = [
            ("Analyte", "art1", "volume", "0"),
            ("Analyte", "art2", "volume", "70.0"),
            ("Analyte", "art2", "conc", "100.0"),
        ]

        # repo = context.artifact_service.step_repository
        # cache = repo.orig_state_cache
        # print_out_dict([cache[art] for art in cache if cache[art].name == "sample1"], "orig state cache")
        #
        # print_out_dict([a for a in context._update_queue if a.name == "sample1"], "updated analytes")

        print_list(actual, "actual:")

        self.assertEqual(expected, actual)


def analyte_set_with_blank(udf_map=None):
    api_resource = MagicMock()
    api_resource.udf = {}
    return [
        (fake_analyte("cont1", "art7", "sample4", "sample4", "E:2", True, is_control=True,
                      udf_map=udf_map, api_resource=api_resource),
         fake_analyte("cont2", "art8", "sample4", "sample4", "E:2", False, is_control=True,
                      udf_map=udf_map, api_resource=api_resource,
                      requested_concentration_ngul=100, requested_volume=20)),
        (fake_analyte("cont1", "art1", "sample1", "sample1", "B:2", True,
                      udf_map=udf_map, api_resource=api_resource,
                      concentration_ngul=100, volume=30),
         fake_analyte("cont2", "art2", "sample1", "sample1", "B:2", False,
                      udf_map=udf_map, api_resource=api_resource,
                      requested_concentration_ngul=100, requested_volume=20)),
        (fake_analyte("cont1", "art3", "sample2", "sample2", "C:2", True,
                      udf_map=udf_map, api_resource=api_resource,
                      concentration_ngul=100, volume=40),
         fake_analyte("cont2", "art4", "sample2", "sample2", "C:2", False,
                      udf_map=udf_map, api_resource=api_resource,
                      requested_concentration_ngul=100, requested_volume=20)),
        (fake_analyte("cont1", "art5", "sample3", "sample3", "D:2", True,
                      udf_map=udf_map, api_resource=api_resource,
                      concentration_ngul=100, volume=50),
         fake_analyte("cont2", "art6", "sample3", "sample3", "D:2", False,
                      udf_map=udf_map, api_resource=api_resource,
                      requested_concentration_ngul=100, requested_volume=20)),
    ]

