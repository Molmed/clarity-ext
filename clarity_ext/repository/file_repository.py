from bs4 import UnicodeDammit


class FileRepository:
    """
    Handles remote and local file access.

    TODO: Merge with "OSService"
    """

    def __init__(self, session):
        self.session = session

    def copy_remote_file(self, remote_file_id, local_path):
        # TODO: implemented in the genologics pip package?
        response = self.session.get("files/{}/download".format(remote_file_id))
        with open(local_path, 'wb') as fd:
            for chunk in response.iter_content():
                fd.write(chunk)

    def open_local_file(self, local_path, mode):
        """
        Reads the local file.

        Provided for being able to test with dependency injection instead of patching open.
        Services will always use this way of opening files.
        """
        with open(local_path, 'rb') as f:
            byte_contents = f.read()

        dammit = UnicodeDammit(byte_contents, ['utf-8', 'latin-1'])
        if len(byte_contents) > 0 and \
                (not dammit.original_encoding or not dammit.unicode_markup):
            raise UnicodeError("Failed to detect encoding for this file.")
        encoding = dammit.original_encoding or 'utf-8'
        return open(local_path, mode, encoding=encoding)
