import os
import difflib


class DriverFileIntegrationTests(object):
    @staticmethod
    def _locate_driver_file_pair(run_directory, frozen_directory, test):
        def locate_driver_file(path):
            files = os.listdir(path)
            count = len(files)
            if count != 1:
                raise UnexpectedNumberOfFilesException("{}: {}".format(path, count))

            for file_name in files:
                import fnmatch
                if fnmatch.fnmatch(file_name, "{}*".format(test["out_file"])):
                    return os.path.join(path, file_name)
                else:
                    raise FrozenFileNotFoundException("No frozen file found")

        frozen_path = os.path.join(frozen_directory, "uploaded")
        run_path = os.path.join(run_directory, "uploaded")

        # We want to find one file (can currently only be one) and it should
        # start with the step name. The rest of the file name can be anything and is not
        # tested here
        frozen_file = locate_driver_file(frozen_path)
        run_file = locate_driver_file(run_path)
        return frozen_file, run_file

    def validate(self, run_directory, frozen_directory, test):
        pair = self._locate_driver_file_pair(run_directory, frozen_directory, test)
        fromfile, tofile = pair
        fromlines = open(fromfile, 'r').readlines()
        tolines = open(tofile, 'r').readlines()
        diff = list(difflib.unified_diff(fromlines, tolines, fromfile, tofile))
        if len(diff) > 0:
            raise FilesDifferException("Diff (max 100 lines):\n{}".format("".join(diff[0:100])))


class FilesDifferException(Exception):
    pass


class FrozenFileNotFoundException(Exception):
    pass


class UnexpectedNumberOfFilesException(Exception):
    pass

