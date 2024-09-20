# -*- coding: utf-8 -*-
from rich import print
from .tools import TestTools, TestData


class DesktopTest:
    def __init__(self, vm_name: str, test_data: TestData):
        self.test_tools = TestTools(
            vm_name=vm_name,
            test_data=test_data
        )

    def run(self, headless: bool = True):
        try:
            self.test_tools.run_vm(headless=headless)
            self.test_tools.run_test_on_vm()

        except KeyboardInterrupt:
            print("[bold red]|WARNING| Interruption by the user")
            raise

        finally:
            self.test_tools.stop_vm()
