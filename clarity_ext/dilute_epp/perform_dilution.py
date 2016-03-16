# Calculates dilute volumes, volume from sample and volume from buffer
# for each analyte within a given process.
# User provide target concentration and target volume for each analyte.
# Give error if any volume is less than 2 ul
# Give error if any volume exceeds 50 ul

from genologics.lims import *
from genologics.config import BASEURI, USERNAME, PASSWORD
from argparse import ArgumentParser
from ..domain import Well

DESC = """Calculates dilute volumes and export to dilute driver file"""


class FieldNames:
    def __init__(self):
        self.concentration = "Concentration"
        self.volume = "Volume"
        self.volume_from_sample = "Volume from Sample"
        self.volume_from_buffer = "Volume from Buffer"
        self.target_concentration = "Target Concentration"
        self.target_volume = "Target Volume"
        self.output_type = "output-type"
        self.artifact = "Analyte"
        self.uri = "uri"
        self.location_position = 1


class Dilute:
    # Enclose sample data, user input and derived variables for a
    # single row in a dilution
    def __init__(self, input_analyte, output_analyte):
        field_names = FieldNames()
        try:
            self.target_concentration = float(
                output_analyte.udf[field_names.target_concentration])
            self.target_volume = output_analyte.udf[field_names.target_volume]
        except KeyError:
            raise ValueError("All target concentrations and target volumes "
                             "must be set before proceeding!")
        (row, col) = \
            output_analyte.location[field_names.location_position].split(":")
        self.target_well = Well(row, col)
        self.sample_name = output_analyte.name
        self.source_concentration = input_analyte.udf[field_names.concentration]
        self.sample_volume = None
        self.buffer_volume = None
        self.has_to_evaporate = None


class DBProcessInitializer:
    # Fetch process data from db using API calls
    def __init__(self, process_uri):
        # Create the LIMS interface instance, and check the connection and version.
        lims = Lims(BASEURI, USERNAME, PASSWORD)
        lims.check_version()
        field_names = FieldNames()
        process = Process(lims, process_uri)
        # Prepare batch calls fetching all input and output analytes in two calls
        output_uris = []
        input_uris = []
        for input_uri, output_uri in process.input_output_maps:
            if input_uri:
                input_uris.append(input_uri[field_names.uri])
            if output_uri and output_uri[field_names.output_type] == field_names.artifact:
                output_uris.append(output_uri[field_names.uri])

        # Perform the batch calls
        self.output_analytes = lims.get_batch(output_uris)
        self.input_analytes = lims.get_batch(input_uris)


class HamiltonGenerator:

    def __init__(self):
        pass

    @staticmethod
    def create_row_string(sample_name, sample_volume, buffer_volume):
        return "{}\t{}\t{}\t{:.2f}\t{:.2f}\t{}\t{}"\
            .format(
                sample_name, "WellPosSource", "PlatePosSource",
                sample_volume, buffer_volume, "WellPosTarget",
                "PlatePosTarget")


class DilutionFileBuilder:
    # Creates a robot driver file for the dilution
    def __init__(
            self, input_analytes, output_analytes):
        self.dilutes = []
        for in_analyte, out_analyte in zip(input_analytes, output_analytes):
            self.dilutes.append(Dilute(in_analyte, out_analyte))

    def _create_driver_file_contents(self, robot_generator):
        rows = []
        for dilute in self.dilutes:
            rows.append(
                robot_generator.create_row_string(
                    dilute.sample_name, dilute.sample_volume,
                    dilute.buffer_volume))
        return "\n".join(rows)

    def create_driver_file(self, robot_generator, driver_file):
        driver_file_contents = \
            self._create_driver_file_contents(robot_generator)
        if driver_file:
            with open(driver_file, "w") as file_:
                file_.write(driver_file_contents)
        return driver_file_contents


def create_driver_file(process_uri="https://lims-staging.snpseq.medsci.uu.se/api/v2/processes/24-3251",
                       driver_file=None):

    db_process_initializer = DBProcessInitializer(process_uri)

    dilution_file_builder = DilutionFileBuilder(
        db_process_initializer.input_analytes,
        db_process_initializer.output_analytes)

    for dilute in dilution_file_builder.dilutes:
        dilute.sample_volume = \
            dilute.target_concentration * dilute.target_volume / \
            dilute.source_concentration
        dilute.buffer_volume = \
            max(dilute.target_volume - dilute.sample_volume, 0)
        dilute.has_to_evaporate = \
            (dilute.target_volume - dilute.sample_volume) < 0

    _check_errors(dilution_file_builder)
    _check_warnings(dilution_file_builder)

    return dilution_file_builder.create_driver_file(
        HamiltonGenerator(), driver_file)


def _check_errors(dilution):
    # Check if any volume is < 2 ul, give error
    if any(dilute.sample_volume < 2 for dilute in dilution.dilutes):
        raise ValueError("Error: Too low sample volume")

    # Check if any volume is > 50 ul, give error
    if any(dilute.sample_volume > 50 for dilute in dilution.dilutes):
        raise ValueError("Error: Too high sample volume")

    if any(dilute.buffer_volume > 50 for dilute in dilution.dilutes):
        raise ValueError("Error: Too high buffer volume")


def _check_warnings(dilution):
    # Check if any sample has to be evaporated, give warning
    if any(dilute.has_to_evaporate for dilute in dilution.dilutes):
        raise ValueError("Warning: Sample has to be evaporated")


if __name__ == "__main__":
    parser = ArgumentParser(description=DESC)
    parser.add_argument("--processURI", required=True,
                        help="The process URI from where this script is run")
    parser.add_argument("--driverFile", required=True,
                        help="The path + name of the dilute driver file")
    args = parser.parse_args()
    create_driver_file(args.processURI, args.driverFile)
