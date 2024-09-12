# -*- coding: utf-8 -*-
from frameworks.console import MyConsole
from .tools import TestTools, TestData


console = MyConsole().console
print = console.print


class DesktopTest:
    def __init__(self, vm_name: str, test_data: TestData, vm_cpus: int = 4, vm_memory: int = 4096):
        self.test_tools = TestTools(
            vm_name=vm_name,
            test_data=test_data,
            vm_cpus=vm_cpus,
            vm_memory=vm_memory
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
