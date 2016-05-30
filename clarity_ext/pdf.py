from PyPDF2 import PdfFileReader, PdfFileWriter


class PdfSplitter:
    def __init__(self, stream):
        self._stream = stream
        self._input_pdf = PdfFileReader(self._stream)

    def split(self, pages, filename):
        """
        Split pages from the wrapped pdf file (see constructor) into
        a new file called `filename`

        :param pages: Either a zero indexed page number or a list of pages
        :param filename: The name of the new file
        :return: None
        """
        if type(pages) is int:
            pages = [pages]

        output_writer = PdfFileWriter()
        for page in pages:
            output_writer.addPage(self._input_pdf.getPage(page))

        with open(filename, "wb") as output_stream:
            output_writer.write(output_stream)

    def close(self):
        self._stream.close()

