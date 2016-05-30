from genologics.entities import *
from genologics.lims import Lims
from clarity_ext.context import FakingEntityMonkey
from clarity_ext.context import ExtensionContext
from clarity_ext.context import ClarityService
from abc import abstractmethod


class MockBase:

    def __init__(self):
        self.monkey = FakingEntityMonkey()
        self.lims = Lims("xxx", "xxx", "xxx")
        self.process = Process(self.lims, id="123")
        clarity_svc = ClarityService(self.lims, "123")
        self.context = ExtensionContext(clarity_svc=clarity_svc)
        self.context.current_step = self.process
        self.set_up()

    @abstractmethod
    def set_up(self):
        pass

    def clean_up(self):
        self.monkey.reset()
