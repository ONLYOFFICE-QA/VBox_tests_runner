# -*- coding: utf-8 -*-
import time

from VBoxWrapper import VirtualMachinException
from rich import print
from .tools import TestToolsLinux, TestToolsWindows, TestData, VboxMachine, TestTools



class DesktopTest:
    def __init__(self, vm_name: str, test_data: TestData):
        self.test_data = test_data
        self.vm = VboxMachine(vm_name)
        self.test_tools = self._get_test_tools()

    def run(self, headless: bool = False, max_attempts: int = 5, interval: int = 5) -> None:
        attempt = 0
        while attempt < max_attempts:
            try:
                attempt += 1
                self._run_test(headless=headless)
                break

            except KeyboardInterrupt:
                print("[bold red]|WARNING| Interruption by the user")
                raise

            except Exception as e:
                print(f"[bold yellow]|WARNING|{self.vm.name}| Attempt {attempt}/{max_attempts} failed: {e}")
                time.sleep(interval)
                if attempt == max_attempts:
                    print(f"[bold red]|ERROR|{self.vm.name}| Max attempts reached. Exiting.")
                    self.test_tools.handle_vm_creation_failure()
                    raise

            finally:
                self.test_tools.stop_vm()

    def _run_test(self, headless: bool) -> None:
        self.test_tools.run_vm(headless=headless)
        self.test_tools.run_test_on_vm()
        if not self.test_tools.report.exists():
            raise VirtualMachinException

    def _get_test_tools(self) -> TestTools:
        if 'windows' in self.vm.os_type:
            return TestToolsWindows(vm=self.vm, test_data=self.test_data)
        return TestToolsLinux(vm=self.vm, test_data=self.test_data)
