# -*- coding: utf-8 -*-
import time
from rich import print
from os.path import join, dirname, realpath
from typing import Optional

from host_tools import File
from .tools import DesktopTestData, DesktopTestTools



class DesktopTest:
    def __init__(self, vm_name: str, test_data: DesktopTestData):
        """
        Initialize DesktopTest instance
        :param vm_name: Name of the virtual machine
        :param test_data: Test data object
        """
        self.data = test_data
        self.test_tools = DesktopTestTools(vm_name=vm_name, test_data=self.data)
        self.vm = self.test_tools.vm

    def run(self, headless: bool = False, max_attempts: int = 5, interval: int = 5) -> None:
        """
        Run desktop test with retry mechanism
        :param headless: Run in headless mode
        :param max_attempts: Maximum number of retry attempts
        :param interval: Delay between retries in seconds
        """
        if not self.test_tools.is_incompatible_package():
            return

        if not self.test_tools.check_package_exists():
            return

        for attempt in range(1, max_attempts + 1):
            try:
                self.test_tools.run_test(headless=headless)
                break
            except KeyboardInterrupt:
                print("[bold red]|WARNING| Interruption by the user")
                raise
            except Exception as e:
                if attempt == max_attempts:
                    print(f"[bold red]|ERROR|{self.vm.name}| Max attempts reached. Exiting.")
                    self.test_tools.handle_vm_creation_failure()
                    raise
                print(f"[bold yellow]|WARNING|{self.vm.name}| Attempt {attempt}/{max_attempts} failed: {e}")
                time.sleep(interval)
            finally:
                self.test_tools.test_tools.stop_vm()
