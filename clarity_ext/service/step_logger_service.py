import logging
import sys
import time
from clarity_ext.service.file_service import SharedFileNotFound
from clarity_ext.utils import lazyprop


class StepLoggerService:
    """
    Provides support for logging to shared files in a step.
    """

    def __init__(self, step_logger_name, file_service, raise_if_not_found=False, append=True, extension="log",
                 write_to_stdout=True):
        self.core_logger = logging.getLogger(__name__)
        self.step_logger_name = step_logger_name
        self.file_service = file_service
        self.raise_if_not_found = raise_if_not_found
        self.append = append
        self.extension = extension
        self.write_to_stdout = write_to_stdout

        # Use Windows line endings for now, since most clients are currently Windows.
        # TODO: This should be configurable.
        self.NEW_LINE = "\r\n"

    @lazyprop
    def step_log(self):
        try:
            mode = "ab" if self.append else "wb"
            return self.file_service.local_shared_file(self.step_logger_name, extension=self.extension,
                                                       mode=mode, modify_attached=True)
        except SharedFileNotFound:
            if self.raise_if_not_found:
                raise
            else:
                return None

    def _log(self, level, msg):
        if self.step_log:
            # TODO: Get formatting from the core logging framework
            if level:
                self.step_log.write("{} - {} - {}".format(time.strftime("%Y-%m-%d %H:%M:%S"),
                                                          logging.getLevelName(level), msg + self.NEW_LINE))
            else:
                self.step_log.write("{}".format(msg + self.NEW_LINE))

        # Forward to the core logger:
        if level:
            self.core_logger.log(level, msg)
        elif self.write_to_stdout:
            # Forward to stdout for dev
            sys.stdout.write("STEPLOG> {}\n".format(msg))

    def error(self, msg):
        self._log(logging.ERROR, msg)

    def warning(self, msg):
        self._log(logging.WARNING, msg)

    def info(self, msg):
        self._log(logging.INFO, msg)

    def log(self, msg):
        # Logs without forwarding to the core logger, and without any formatting
        self._log(None, msg)

    def get(self, name):
        # This factory method is added for readability in the extensions.
        return StepLoggerService(name, self.file_service, raise_if_not_found=True, append=False)

