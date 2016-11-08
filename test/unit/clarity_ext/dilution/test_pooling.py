import unittest
from mock import MagicMock
from clarity_ext.dilution import DilutionScheme
from clarity_ext.dilution import CONCENTRATION_REF_NM
from clarity_ext.dilution import VOLUME_CALC_BY_CONC
from clarity_ext.domain.validation import ValidationException
from clarity_ext.domain.validation import ValidationType
from test.unit.clarity_ext.helpers import fake_analyte
from test.unit.clarity_ext.helpers import print_list
from test.unit.clarity_ext import helpers
from itertools import groupby


UDF_MAP = {
            "requested_concentration_nm": "Target Concentration",
            "requested_volume": "Target Volume",
            "concentration_nm": "Conc",
            "volume": "Vol"
          }


class TestLibraryPooling(unittest.TestCase):
    def _default_dilution_scheme(self, artifact_service, scale_up_low_volumes=True):
        return DilutionScheme.create(artifact_service=artifact_service, robot_name="Hamilton",
                                     scale_up_low_volumes=scale_up_low_volumes,
                                     concentration_ref=CONCENTRATION_REF_NM, include_blanks=False,
                                     volume_calc_method=VOLUME_CALC_BY_CONC, make_pools=True)

    def test_single_pool_creation(self):
        def pooled_analyte_set():
            samples = ["sample1", "sample2", "sample3"]
            pool = fake_analyte("cont2", "art4", samples, "Pool1", "B:4",
                                is_input=False, udf_map=UDF_MAP,
                                requested_concentration_nm=15, requested_volume=40)
            return [
                (fake_analyte("cont1", "art1", "sample1", "analyte1", "A:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=10, volume=300),
                 pool),
                (fake_analyte("cont1", "art2", "sample2", "analyte2", "A:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=25, volume=300),
                 pool),
                (fake_analyte("cont1", "art3", "sample3", "analyte3", "A:3", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=30, volume=300),
                 pool),
            ]

        svc = helpers.mock_artifact_service(pooled_analyte_set)
        dilution_scheme = self._default_dilution_scheme(svc)

        expected = [
            ['analyte1', 1, 'DNA1', 20.0, 5.3, 26, 'END1'],
            ['analyte2', 9, 'DNA1', 8.0, 0, 26, 'END1'],
            ['analyte3', 17, 'DNA1', 6.7, 0, 26, 'END1'],
        ]

        # Test:
        actual = [
            [dilute.aliquot_name,
             dilute.source_well_index,
             dilute.source_plate_pos,
             round(dilute.sample_volume, 1),
             round(dilute.buffer_volume, 1),
             dilute.target_well_index,
             dilute.target_plate_pos] for dilute in dilution_scheme.split_row_transfers
        ]

        validation_results = list(post_validate_dilution(dilution_scheme))

        # Assert:
        self.assertEqual(expected, actual)
        self.assertEqual(0, len(validation_results))

    def test_two_pools_creation(self):
        svc = helpers.mock_artifact_service(two_pool_analyte_set)
        dilution_scheme = self._default_dilution_scheme(svc)

        expected = [
            ['analyte1', 1, 'DNA1', 20.0, 5.3, 26, 'END1'],
            ['analyte2', 2, 'DNA1', 8.0, 0, 26, 'END1'],
            ['analyte3', 3, 'DNA1', 6.7, 0, 26, 'END1'],
            ['analyte4', 9, 'DNA1', 20.0, 5.3, 27, 'END1'],
            ['analyte5', 10, 'DNA1', 8.0, 0, 27, 'END1'],
            ['analyte6', 11, 'DNA1', 6.7, 0, 27, 'END1'],
        ]

        # Test:
        actual = [
            [dilute.aliquot_name,
             dilute.source_well_index,
             dilute.source_plate_pos,
             round(dilute.sample_volume, 1),
             round(dilute.buffer_volume, 1),
             dilute.target_well_index,
             dilute.target_plate_pos] for dilute in dilution_scheme.split_row_transfers
        ]

        validation_results = list(post_validate_dilution(dilution_scheme))

        print_list(expected, "expected")
        print_list(actual, "actual")

        # Assert:
        self.assertEqual(expected, actual)
        self.assertEqual(0, len(validation_results))

    def test_dilution_scheme_source_volume_not_set(self):
        def invalid_analyte_set():
            pool1 = fake_analyte("cont-id1", "art-id1", ["sample1", "sample2"], "pool1", "B:5",
                                  False, requested_concentration_nm=100, requested_volume=20)
            return [
                    (fake_analyte("cont-id1", "art-id1", "sample1", "art-name1", "D:5",
                                  True, concentration_nm=100),
                     pool1),
                    (fake_analyte("cont-id1", "art-id1", "sample2", "art-name1", "D:5",
                                  True, concentration_nm=100, volume=20),
                     pool1),
                    ]
        svc = helpers.mock_artifact_service(invalid_analyte_set)
        dilution_scheme = self._default_dilution_scheme(svc)
        actual = set(str(result)
                     for result in pre_validate_dilution(dilution_scheme))
        expected = set(["Error: art-name1, source volume is not set."])
        self.assertEqual(expected, actual)

    def test_dilution_scheme_source_concentration_not_set(self):
        def invalid_analyte_set():
            pool1 = fake_analyte("cont-id1", "art-id1", ["sample1", "sample2"], "pool1", "B:5",
                                  False, requested_concentration_nm=100, requested_volume=20)
            return [
                    (fake_analyte("cont-id1", "art-id1", "sample1", "art-name1", "D:5",
                                  True, volume=100),
                     pool1),
                    (fake_analyte("cont-id1", "art-id1", "sample2", "art-name1", "D:5",
                                  True, concentration_nm=100, volume=20),
                     pool1),
                    ]
        svc = helpers.mock_artifact_service(invalid_analyte_set)
        dilution_scheme = self._default_dilution_scheme(svc)
        actual = set(str(result)
                     for result in pre_validate_dilution(dilution_scheme))
        expected = set(["Error: art-name1, source concentration not set."])
        self.assertEqual(expected, actual)

    def test_dilution_scheme_source_concentration_zero(self):
        def invalid_analyte_set():
            pool1 = fake_analyte("cont-id1", "art-id1", ["sample1", "sample2"], "pool1", "B:5",
                                  False, requested_concentration_nm=100, requested_volume=20)
            return [
                    (fake_analyte("cont-id1", "art-id1", "sample1", "art-name1", "D:5",
                                  True, concentration_nm=0, volume=100),
                     pool1),
                    (fake_analyte("cont-id1", "art-id1", "sample2", "art-name1", "D:5",
                                  True, concentration_nm=100, volume=20),
                     pool1),
                    ]
        svc = helpers.mock_artifact_service(invalid_analyte_set)
        dilution_scheme = self._default_dilution_scheme(svc)
        actual = set(str(result)
                     for result in pre_validate_dilution(dilution_scheme))
        expected = set(["Error: art-name1, source concentration not set."])
        self.assertEqual(expected, actual)

    def test_too_high_destination_volume(self):
        def invalid_analyte_set():
            samples = ["sample1", "sample2", "sample3"]
            pool1 = fake_analyte("cont2", "art4", samples, "Pool1", "B:4",
                                is_input=False, udf_map=UDF_MAP,
                                requested_concentration_nm=15, requested_volume=40)
            samples = ["sample4", "sample5", "sample6"]
            pool2 = fake_analyte("cont2", "art5", samples, "Pool2", "C:4",
                                is_input=False, udf_map=UDF_MAP,
                                requested_concentration_nm=15, requested_volume=101)
            return [
                (fake_analyte("cont1", "art1", "sample1", "analyte1", "A:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=10, volume=300),
                 pool1),
                (fake_analyte("cont1", "art2", "sample2", "analyte2", "B:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=25, volume=300),
                 pool1),
                (fake_analyte("cont1", "art3", "sample3", "analyte3", "C:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=30, volume=300),
                 pool1),
                (fake_analyte("cont1", "art4", "sample4", "analyte4", "A:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=10, volume=300),
                 pool2),
                (fake_analyte("cont1", "art5", "sample5", "analyte5", "B:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=25, volume=300),
                 pool2),
                (fake_analyte("cont1", "art6", "sample6", "analyte6", "C:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=30, volume=300),
                 pool2),
            ]

        svc = helpers.mock_artifact_service(invalid_analyte_set)
        dilution_scheme = self._default_dilution_scheme(svc)
        actual = set(str(result)
                     for result in post_validate_dilution(dilution_scheme))
        expected = set(["Error: Pool2, too high destination volume (cont2(C4))."])
        self.assertEqual(expected, actual)

    def test_too_high_destination_volume_due_to_evaporation(self):
        def invalid_analyte_set():
            samples = ["sample1", "sample2", "sample3"]
            pool1 = fake_analyte("cont2", "art4", samples, "Pool1", "B:4",
                                is_input=False, udf_map=UDF_MAP,
                                requested_concentration_nm=15, requested_volume=40)
            samples = ["sample4", "sample5", "sample6"]
            pool2 = fake_analyte("cont2", "art5", samples, "Pool2", "C:4",
                                is_input=False, udf_map=UDF_MAP,
                                requested_concentration_nm=40, requested_volume=70)
            return [
                (fake_analyte("cont1", "art1", "sample1", "analyte1", "A:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=10, volume=300),
                 pool1),
                (fake_analyte("cont1", "art2", "sample2", "analyte2", "B:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=25, volume=300),
                 pool1),
                (fake_analyte("cont1", "art3", "sample3", "analyte3", "C:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=30, volume=300),
                 pool1),
                (fake_analyte("cont1", "art4", "sample4", "analyte4", "A:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=10, volume=300),
                 pool2),
                (fake_analyte("cont1", "art5", "sample5", "analyte5", "B:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=25, volume=300),
                 pool2),
                (fake_analyte("cont1", "art6", "sample6", "analyte6", "C:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=30, volume=300),
                 pool2),
            ]

        svc = helpers.mock_artifact_service(invalid_analyte_set)
        dilution_scheme = self._default_dilution_scheme(svc)
        actual = set(str(result)
                     for result in post_validate_dilution(dilution_scheme))
        expected = set(["Error: Pool2, too high destination volume (cont2(C4)).",
                       "Warning: Pool2, pool has to be evaporated (cont2(C4))."])
        self.assertEqual(expected, actual)

    def test_evaporation_warning(self):
        def invalid_analyte_set():
            samples = ["sample1", "sample2", "sample3"]
            pool1 = fake_analyte("cont2", "art4", samples, "Pool1", "B:4",
                                is_input=False, udf_map=UDF_MAP,
                                requested_concentration_nm=15, requested_volume=40)
            samples = ["sample4", "sample5", "sample6"]
            pool2 = fake_analyte("cont2", "art5", samples, "Pool2", "C:4",
                                is_input=False, udf_map=UDF_MAP,
                                requested_concentration_nm=30, requested_volume=30)
            return [
                (fake_analyte("cont1", "art1", "sample1", "analyte1", "A:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=10, volume=300),
                 pool1),
                (fake_analyte("cont1", "art2", "sample2", "analyte2", "B:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=25, volume=300),
                 pool1),
                (fake_analyte("cont1", "art3", "sample3", "analyte3", "C:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=30, volume=300),
                 pool1),
                (fake_analyte("cont1", "art4", "sample4", "analyte4", "A:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=10, volume=300),
                 pool2),
                (fake_analyte("cont1", "art5", "sample5", "analyte5", "B:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=25, volume=300),
                 pool2),
                (fake_analyte("cont1", "art6", "sample6", "analyte6", "C:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=30, volume=300),
                 pool2),
            ]

        svc = helpers.mock_artifact_service(invalid_analyte_set)
        dilution_scheme = self._default_dilution_scheme(svc)
        actual = set(str(result)
                     for result in post_validate_dilution(dilution_scheme))
        expected = set(
            ["Warning: Pool2, pool has to be evaporated (cont2(C4))."])
        self.assertEqual(expected, actual)

    def test_scaled_up_warning(self):
        def invalid_analyte_set():
            samples = ["sample1", "sample2", "sample3"]
            pool1 = fake_analyte("cont2", "art4", samples, "Pool1", "B:4",
                                is_input=False, udf_map=UDF_MAP,
                                requested_concentration_nm=15, requested_volume=5)
            samples = ["sample4", "sample5", "sample6"]
            pool2 = fake_analyte("cont2", "art5", samples, "Pool2", "C:4",
                                is_input=False, udf_map=UDF_MAP,
                                requested_concentration_nm=10, requested_volume=40)
            return [
                (fake_analyte("cont1", "art1", "sample1", "analyte1", "A:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=10, volume=300),
                 pool1),
                (fake_analyte("cont1", "art2", "sample2", "analyte2", "B:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=25, volume=300),
                 pool1),
                (fake_analyte("cont1", "art3", "sample3", "analyte3", "C:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=30, volume=300),
                 pool1),
                (fake_analyte("cont1", "art4", "sample4", "analyte4", "A:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=10, volume=300),
                 pool2),
                (fake_analyte("cont1", "art5", "sample5", "analyte5", "B:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=25, volume=300),
                 pool2),
                (fake_analyte("cont1", "art6", "sample6", "analyte6", "C:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=30, volume=300),
                 pool2),
            ]

        svc = helpers.mock_artifact_service(invalid_analyte_set)
        dilution_scheme = self._default_dilution_scheme(svc)
        actual = set(str(result)
                     for result in post_validate_dilution(dilution_scheme))
        expected = set(
            ["Warning: Pool1, volume has been scaled up due to the min pipetting volume of 2 ul (cont2(B4))."])
        self.assertEqual(expected, actual)

    def test_scaled_up_and_split_rows(self):
        def invalid_analyte_set():
            samples = ["sample1", "sample2", "sample3"]
            pool1 = fake_analyte("cont2", "art4", samples, "Pool1", "B:4",
                                is_input=False, udf_map=UDF_MAP,
                                requested_concentration_nm=15, requested_volume=40)
            samples = ["sample4", "sample5", "sample6"]
            pool2 = fake_analyte("cont2", "art5", samples, "Pool2", "C:4",
                                is_input=False, udf_map=UDF_MAP,
                                requested_concentration_nm=7, requested_volume=80)
            return [
                (fake_analyte("cont1", "art1", "sample1", "analyte1", "A:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=10, volume=300),
                 pool1),
                (fake_analyte("cont1", "art2", "sample2", "analyte2", "B:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=25, volume=300),
                 pool1),
                (fake_analyte("cont1", "art3", "sample3", "analyte3", "C:1", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=30, volume=300),
                 pool1),
                (fake_analyte("cont1", "art4", "sample4", "analyte4", "A:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=3, volume=300),
                 pool2),
                (fake_analyte("cont1", "art5", "sample5", "analyte5", "B:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=25, volume=300),
                 pool2),
                (fake_analyte("cont1", "art6", "sample6", "analyte6", "C:2", is_input=True, udf_map=UDF_MAP,
                              concentration_nm=180, volume=300),
                 pool2),
            ]

        svc = helpers.mock_artifact_service(invalid_analyte_set)
        dilution_scheme = self._default_dilution_scheme(svc)

        expected = [
            ['analyte1', 1, 'DNA1', 20.0, 5.3, 26, 'END1'],
            ['analyte2', 2, 'DNA1', 8.0, 0, 26, 'END1'],
            ['analyte3', 3, 'DNA1', 6.7, 0, 26, 'END1'],
            ['analyte4', 9, 'DNA1', 40.0, 17.9, 27, 'END1'],
            ['analyte4', 9, 'DNA1', 40.0, 0, 27, 'END1'],
            ['analyte4', 9, 'DNA1', 40.0, 0, 27, 'END1'],
            ['analyte5', 10, 'DNA1', 14.4, 0, 27, 'END1'],
            ['analyte6', 11, 'DNA1', 2, 0, 27, 'END1'],
        ]

        # Test:
        actual = [
            [dilute.aliquot_name,
             dilute.source_well_index,
             dilute.source_plate_pos,
             round(dilute.sample_volume, 1),
             round(dilute.buffer_volume, 1),
             dilute.target_well_index,
             dilute.target_plate_pos] for dilute in dilution_scheme.split_row_transfers
        ]

        print_list(expected, "expected")
        print_list(actual, "actual")

        # Assert:
        self.assertEqual(expected, actual)


def two_pool_analyte_set():
    samples = ["sample1", "sample2", "sample3"]
    pool1 = fake_analyte("cont2", "art4", samples, "Pool1", "B:4",
                        is_input=False, udf_map=UDF_MAP,
                        requested_concentration_nm=15, requested_volume=40)
    samples = ["sample4", "sample5", "sample6"]
    pool2 = fake_analyte("cont2", "art5", samples, "Pool2", "C:4",
                        is_input=False, udf_map=UDF_MAP,
                        requested_concentration_nm=15, requested_volume=40)
    return [
        (fake_analyte("cont1", "art1", "sample1", "analyte1", "A:1", is_input=True, udf_map=UDF_MAP,
                      concentration_nm=10, volume=300),
         pool1),
        (fake_analyte("cont1", "art4", "sample4", "analyte4", "A:2", is_input=True, udf_map=UDF_MAP,
                      concentration_nm=10, volume=300),
         pool2),
        (fake_analyte("cont1", "art2", "sample2", "analyte2", "B:1", is_input=True, udf_map=UDF_MAP,
                      concentration_nm=25, volume=300),
         pool1),
        (fake_analyte("cont1", "art3", "sample3", "analyte3", "C:1", is_input=True, udf_map=UDF_MAP,
                      concentration_nm=30, volume=300),
         pool1),
        (fake_analyte("cont1", "art5", "sample5", "analyte5", "B:2", is_input=True, udf_map=UDF_MAP,
                      concentration_nm=25, volume=300),
         pool2),
        (fake_analyte("cont1", "art6", "sample6", "analyte6", "C:2", is_input=True, udf_map=UDF_MAP,
                      concentration_nm=30, volume=300),
         pool2),
    ]


def pre_validate_dilution(dilution_scheme):
    """
    Check that all pertinent variables are initiated so that calculations
    are possible to perform
    """
    for transfer in dilution_scheme.unsplit_transfers:
        if not transfer.source_initial_volume:
            yield ValidationException("{}, source volume is not set.".format(transfer.aliquot_name))
        if not transfer.source_concentration:
            yield ValidationException("{}, source concentration not set.".format(transfer.aliquot_name))


def post_validate_dilution(dilution_scheme):
    """
    Check calculation results if its conform to hardware restrictions
    """
    def pos_str(transfer):
        return "{}".format(transfer.target_well)

    sorted_transfers = sorted(
        dilution_scheme.unsplit_transfers, key=lambda t: t.target_aliquot_name)
    grouped_transfers = groupby(
        sorted_transfers, key=lambda t: t.target_aliquot_name)

    for key, g in grouped_transfers:
        g = list(g)
        total_volume = sum(map(lambda t: t.sample_volume + t.buffer_volume, g))
        if total_volume > 100:
            yield ValidationException("{}, too high destination volume ({}).".format(
                g[0].target_aliquot_name, pos_str(g[0])))
        if g[0].has_to_evaporate:
            yield ValidationException("{}, pool has to be evaporated ({}).".format(
                g[0].target_aliquot_name, pos_str(g[0])), ValidationType.WARNING)
        if g[0].scaled_up:
            yield ValidationException("{}, volume has been scaled up due to "
                                      "the min pipetting volume of 2 ul ({}).".format(
                g[0].target_aliquot_name, pos_str(g[0])), ValidationType.WARNING)
