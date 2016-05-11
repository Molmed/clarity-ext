from clarity_ext.extensions import DriverFileExtension
import datetime


class Extension(DriverFileExtension):
    """
    Creates an input file for the Fragment Analyzer.
    """
    def newline(self):
        return "\r\n"

    def filename(self):
        """Returns the name of the file to be uploaded"""
        today = datetime.date.today()
        prefix = today.strftime("%y%m%d")
        return "{}_{}.{}".format(prefix, "FA_input", "txt")

    def shared_file(self):
        """Returns the name of the shared file where this file should be hooked"""
        return "Sample List"

    def content(self):
        """Yields the lines to be written to the file"""
        for well in self.context.input_container.list_wells(self.context.input_container.RIGHT_FIRST):
            yield "{}".format(well.artifact_name or "0")

    def integration_tests(self):
        """Returns metadata for one or more integration test to run against the server"""
        yield "24-3144"
