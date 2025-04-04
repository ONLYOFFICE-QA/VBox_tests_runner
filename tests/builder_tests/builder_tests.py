# -*- coding: utf-8 -*-
from frameworks.VboxMachine import VboxMachine
from frameworks.test_tools import TestToolsLinux, TestToolsWindows, TestTools
from .builder_test_data import BuilderTestData


class BuilderTests:

    def __init__(self, vm_name: str, test_data: BuilderTestData):
        self.test_data = test_data
        self.vm = VboxMachine(vm_name)
        self.test_tools = self._get_test_tools()

    def run(self):
        ...

    def _get_test_tools(self) -> TestTools:
        if 'windows' in self.vm.os_type:
            return TestToolsWindows(vm=self.vm, test_data=self.test_data)
        return TestToolsLinux(vm=self.vm, test_data=self.test_data)
