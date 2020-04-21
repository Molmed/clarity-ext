import unittest
from clarity_ext.domain.udf import UdfMapping
from clarity_ext.domain import ResultFile, Analyte, SharedResultFile, Process
from clarity_ext.domain.udf import UdfMappingNotUniqueException


class TestUdfMappingInfo(unittest.TestCase):

    def test_udf_mapping(self):
        """
        Asserts that we can create a UdfMapping and use the getter
        """
        mapping = UdfMapping()

        # Add key/values to the mapping:
        mapping.add("% Total", 10)

        # We should now be able to access the field by either the original value
        # or the Python name `udf_total`
        self.assertTrue(mapping.unwrap("% Total").value, 10)
        self.assertTrue(mapping.unwrap("udf_total").value, 10)

        mapping.unwrap("% Total").value = 20
        self.assertTrue(mapping.unwrap("% Total").is_dirty())

    def test_udf_mapping_dictionary_like(self):
        mapping = UdfMapping({"Custom #1": 10, "Custom #2": 20})

        self.assertTrue("Custom #1" in mapping)
        self.assertTrue("Custom #2" in mapping)
        self.assertTrue("udf_custom_1" in mapping)
        self.assertTrue("udf_custom_2" in mapping)

    def test_udf_mapping_raises_on_non_unique(self):
        """
        If the Python name for a UDF doesn't map directly
        to a clarity UDF, raise an exception when trying to use it
        """
        udf_map = self._get_non_unique_udf_mapping()
        # Apply the map to some domain object:
        result_file = ResultFile(None, False, "abc", None, None, udf_map=udf_map)

        # Try to fetch by the udf:
        with self.assertRaises(UdfMappingNotUniqueException):
            print result_file.udf_total

        # Try to set using the same UDF
        with self.assertRaises(UdfMappingNotUniqueException):
            result_file.udf_total = 20

    def test_can_set_udf_on_result_file(self):
        domain_object = ResultFile(None, False, "abc", udf_map=self._get_unique_udf_mapping())
        self._test_can_set_udf_on_domain_object(domain_object)

    def test_can_set_udf_on_shared_result_file(self):
        domain_object = SharedResultFile(udf_map=self._get_unique_udf_mapping())
        self._test_can_set_udf_on_domain_object(domain_object)

    def test_can_set_udf_on_analyte(self):
        domain_object = Analyte(None, True, udf_map=self._get_unique_udf_mapping())
        self._test_can_set_udf_on_domain_object(domain_object)

    def test_can_set_udf_on_process(self):
        domain_object = Process(None, "pid", None, self._get_unique_udf_mapping(),
                                "https://notavail", "some instrument")
        self._test_can_set_udf_on_domain_object(domain_object)

    def _test_can_set_udf_on_domain_object(self, domain_object):
        # Apply the map to some domain object:
        original = domain_object.udf_total
        domain_object.udf_total *= 2
        self.assertTrue(domain_object.udf_map["udf_total"].is_dirty())
        self.assertEqual(domain_object.udf_total, original * 2)

    def test_can_only_set_existing_udfs(self):
        """
        Validates that UDFs can't be set dynamically to the object after creation

        Setting anything that starts with udf_ will fail unless it exists in the domain object's UDF map
        """
        domain_object = SharedResultFile(udf_map=self._get_unique_udf_mapping())
        domain_object.udf_total = 10
        with self.assertRaises(AttributeError):
            domain_object.udf_does_not_exist = 5

    def test_equality_check_takes_udfs_into_account(self):
        # Since the udfs are not actual python attributes, but rather
        # fetched through __setattr__ __getattr__, we need to make sure
        # that the equality test actually takes this into account
        result_file1 = ResultFile(None, False, "abc", udf_map=self._get_unique_udf_mapping())
        result_file2 = ResultFile(None, False, "abc", udf_map=self._get_unique_udf_mapping())
        self.assertEqual(result_file1, result_file2, "Objects should equal before changing them")

        result_file2.udf_total *= 2
        self.assertNotEqual(result_file1, result_file2)

    def test_can_change_udfs_by_original(self):
        """
        End users should always be able to set UDFs by the original name in Clarity,
        even if the python attributes collide with them.
        """
        result_file1 = ResultFile(None, False, "abc",
                                  udf_map=self._get_unique_udf_mapping())
        original = result_file1.udf_total
        result_file1.udf_map["% Total"].value *= 2
        result_file1.udf_total == original * 2

    @staticmethod
    def _get_non_unique_udf_mapping():
        original = {"% Total": 10,
                    "# Total": 20}
        return UdfMapping(original)

    @staticmethod
    def _get_unique_udf_mapping():
        original = {"% Total": 10,
                    "Conc.": 0.5}
        return UdfMapping(original)
