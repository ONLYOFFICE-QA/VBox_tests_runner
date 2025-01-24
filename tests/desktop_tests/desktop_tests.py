# -*- coding: utf-8 -*-
from VBoxWrapper import VirtualMachinException
from rich import print

from frameworks import VboxMachine
from .tools import TestToolsLinux, TestToolsWindows, TestTools, TestData


class DesktopTest:
    def __init__(self, vm_name: str, test_data: TestData):
        self.test_data = test_data
        self.vm = VboxMachine(vm_name)
        self.test_tools = self._get_test_tools()

    def run(self, headless: bool = False, max_attempts: int = 5):
        attempt = 0
        while attempt < max_attempts:
            try:
                attempt += 1
                self.test_tools.run_vm(headless=headless)
                self.test_tools.run_test_on_vm()
                if not self.test_tools.report.exists():
                    raise VirtualMachinException

                break

            except KeyboardInterrupt:
                print("[bold red]|WARNING| Interruption by the user")
                raise

            except Exception as e:
                print(f"[bold yellow]|WARNING| Attempt {attempt} failed: {e}")
                if attempt == max_attempts:
                    print("[bold red]|ERROR| Max attempts reached. Exiting.")
                    self.test_tools.handle_vm_creation_failure()
                    raise

            finally:
                self.test_tools.stop_vm()

    def _get_test_tools(self) -> TestTools:
        if 'windows' in self.vm.os_type:
            return TestToolsWindows(vm=self.vm, test_data=self.test_data)
        return TestToolsLinux(vm=self.vm, test_data=self.test_data)

