import unittest
from mock import MagicMock
from mock import call
import logging
from clarity_ext.extensions import ValidationService
from clarity_ext.domain.validation import ValidationException
from clarity_ext.domain.validation import ValidationType
from test.unit.clarity_ext.helpers import mock_context


class TestValidationService(unittest.TestCase):

    def setUp(self):
        self.logger = logging.getLogger(self.__class__.__module__)

    def test_validation_logging(self):
        context = mock_context()
        validation_service = ValidationService(
            context=context, logger=self.logger)
        step_logger_service = MagicMock()
        step_logger_service.log = MagicMock()
        validation_service.step_logger_service = step_logger_service
        error_exception = ValidationException(
            "Error message", validation_type=ValidationType.ERROR)
        warning_exception = ValidationException(
            "Warning message", validation_type=ValidationType.WARNING)
        validation_service.handle_validation([error_exception])

        validation_service.step_logger_service.log.assert_called_once_with(
            "{}".format(error_exception))
        self.assertEqual(validation_service.has_errors, True)
        self.assertEqual(validation_service.has_warnings, False)

        validation_service.handle_validation(
                [error_exception, warning_exception])
        calls = [call("{}".format(error_exception)),
                 call("{}".format(warning_exception))]
        validation_service.step_logger_service.log.assert_has_calls(
            calls, any_order=False)
        self.assertEqual(validation_service.has_errors, True)
        self.assertEqual(validation_service.has_warnings, True)
