# -*- coding: utf-8 -*-
from rich import print

from frameworks import VboxMachine
from .tools import TestToolsLinux, TestToolsWindows, TestTools, TestData


class DesktopTest:
    def __init__(self, vm_name: str, test_data: TestData):
        self.test_data = test_data
        self.vm = VboxMachine(vm_name)
        self.test_tools = self._get_test_tools()

    def run(self, headless: bool = False):
        try:
            self.test_tools.run_vm(headless=headless)
            self.test_tools.run_test_on_vm()

        except KeyboardInterrupt:
            print("[bold red]|WARNING| Interruption by the user")
            raise
        #
        # finally:
        #     self.test_tools.stop_vm()

    def _get_test_tools(self) -> TestTools:
        os_type = self.vm.get_os_type()
        if 'windows' in os_type:
            return TestToolsWindows(vm=self.vm, test_data=self.test_data, os_type=os_type)
        return TestToolsLinux(vm=self.vm, test_data=self.test_data, os_type=os_type)

