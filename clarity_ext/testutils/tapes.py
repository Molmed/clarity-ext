import shutil
import os
import vcr
from xmldiff import main
from genologics.config import BASEURI
from urllib.parse import urlparse
import unittest
from click.testing import CliRunner
from clarity_ext.cli import main as clarity_ext_entry_point
from datetime import datetime


def get_uri():
    parsed = urlparse(BASEURI)
    return parsed.netloc

def replace_server(request):
    uri = get_uri()
    # Replace the lims-server instance. This is primarily so that one can run already taped
    # tests without worrying about what server is configured.
    if request.body:
        request.body = request.body.replace(
                str.encode(uri), b"lims-server")
    if request.uri:
        request.uri = request.uri.replace(
                uri, "lims-server")


def replace_server_in_response(response):
    uri = get_uri()
    # Replace the lims-server instance. This is primarily so that one can run already taped
    # tests without worrying about what server is configured.
    try:
        response['body']['string'] = response['body']['string'].replace(
                str.encode(uri), b"lims-server")
    except KeyError:
        pass

    headers = response['headers']

    locations = headers.get('Location', None)

    if locations:
        new_locations = list()

        # Elements in the header are saved as a list for some reason
        for location in locations:
            new_location = location.replace(uri, "lims-server")
            new_locations.append(new_location)
        headers['Location'] = new_locations


def matcher(req1, req2):
    assert req1.method == req2.method, "method doesn't match"
    assert req1.scheme == req2.scheme, "scheme doesn't match"
    assert req1.host == req2.host, "host doesn't match"
    assert req1.port == req2.port, "port doesn't match"
    assert req1.path == req2.path, "path doesn't match"
    assert req1.query == req2.query, "query doesn't match"

    content_type1 = req1.headers.get("Content-Type", None)
    content_type2 = req2.headers.get("Content-Type", None)

    if content_type1 != content_type2:
        return

    if req1.body and req2.body and content_type1 == "application/xml":
        the_diff = main.diff_texts(req1.body, req1.body)
        assert len(the_diff) == 0, the_diff
        if the_diff:
            print(len(the_diff))
            exit()
    else:
        assert req1.body == req2.body, "bodies differ"


def create_vcr(fixture_path="./test/fixtures/cassettes"):
    """
    Creates a vcr that filters authorization codes and the URL to the lims instance.
    """
    ret = vcr.VCR(
        cassette_library_dir=os.path.realpath(fixture_path),
        record_mode='once',
        filter_headers=['authorization'],
    )

    ret.register_matcher('matcher', matcher)
    ret.match_on = ['matcher']
    return ret


class BaseVcrTest(unittest.TestCase):
    def record_or_run_recording(self, cassette_name, step_id, module, custom_checks=None):
        """
        Runs an extension for a step, taping all network communication if required, otherwise
        running using the existing tape for the test.

        If a tape doesn't exist, the step and extension must exist in the Clarity instance
        clarity-ext is configured to run in.
        """
        vcr = create_vcr()
        runner = CliRunner()

        timestamp = datetime.now().strftime("%y%m%dT%H%M%S")

        # This is a quick fix to get the context files out of the way
        test_dir = os.path.realpath(f"./test/acceptance/runs/{module}/{step_id}/{timestamp}/")

        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
        os.makedirs(test_dir)
        os.chdir(test_dir)

        with vcr.use_cassette(cassette_name) as cass:
            result = runner.invoke(clarity_ext_entry_point,
                ["extension", "--args", f"pid={step_id}", module, "exec"])

            if custom_checks:
                custom_checks(result, cass)
            else:
                assert result.exit_code == 0, result.output

