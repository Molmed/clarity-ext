from genologics.entities import *

from test.unit.clarity_ext.mock.mock_base import MockBase


class DilutionMock1(MockBase):

    def set_up(self):

        container1 = Container(self.lims, id="container1")
        container2 = Container(self.lims, id="container2")
        container3 = Container(self.lims, id="container3")
        container4 = Container(self.lims, id="container4")

        _artifact = Artifact(self.lims, id="in_art3")
        _artifact.samples = [Sample(self.lims, id="sample3")]
        _artifact.name = "username3"
        _artifact.type = "Analyte"
        _artifact.location = container2, "B:7"
        _artifact.udf = {"Concentration": 123}
        self.process.all_inputs().append(_artifact)

        _artifact = Artifact(self.lims, id="in_art1")
        _artifact.samples = [Sample(self.lims, id="sample1")]
        _artifact.name = "username1"
        _artifact.type = "Analyte"
        _artifact.location = container1, "D:5"
        _artifact.udf = {"Concentration": 134}
        self.process.all_inputs().append(_artifact)

        _artifact = Artifact(self.lims, id="in_art2")
        _artifact.samples = [Sample(self.lims, id="sample2")]
        _artifact.name = "username2"
        _artifact.type = "Analyte"
        _artifact.location = container2, "A:5"
        _artifact.udf = {"Concentration": 134}
        self.process.all_inputs().append(_artifact)

        _artifact = Artifact(self.lims, id="in_art4")
        _artifact.samples = [Sample(self.lims, id="sample4")]
        _artifact.name = "username4"
        _artifact.type = "Analyte"
        _artifact.location = container2, "E:12"
        _artifact.udf = {"Concentration": 134}
        self.process.all_inputs().append(_artifact)

        _artifact = Artifact(self.lims, id="out_art2")
        _artifact.samples = [Sample(self.lims, id="sample2")]
        _artifact.name = "username2"
        _artifact.location = container4, "A:3"
        _artifact.type = "Analyte"
        _artifact.udf = {"Target Concentration": 100,
                         "Target Volume": 20,}
        self.process.all_outputs().append(_artifact)

        _artifact = Artifact(self.lims, id="out_art1")
        _artifact.samples = [Sample(self.lims, id="sample1")]
        _artifact.name = "username1"
        _artifact.location = container3, "B:5"
        _artifact.type = "Analyte"
        _artifact.udf = {"Target Concentration": 100,
                         "Target Volume": 20,}
        self.process.all_outputs().append(_artifact)

        _artifact = Artifact(self.lims, id="out_art3")
        _artifact.samples = [Sample(self.lims, id="sample3")]
        _artifact.name = "username3"
        _artifact.location = container3, "D:6"
        _artifact.type = "Analyte"
        _artifact.udf = {"Target Concentration": 100,
                         "Target Volume": 20,}
        self.process.all_outputs().append(_artifact)

        _artifact = Artifact(self.lims, id="out_art4")
        _artifact.samples = [Sample(self.lims, id="sample4")]
        _artifact.name = "username4"
        _artifact.location = container4, "E:9"
        _artifact.type = "Analyte"
        _artifact.udf = {"Target Concentration": 100,
                         "Target Volume": 20,}
        self.process.all_outputs().append(_artifact)

