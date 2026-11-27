# -*- coding: utf-8 -*-
import time
from rich import print
from .tools import PuppeteerTestData, PuppeteerTestTools


class DesktopPuppeteerTest:
    def __init__(self, vm_name: str, test_data: PuppeteerTestData):
        """
        Initialize DesktopPuppeteerTest instance
        :param vm_name: Name of the virtual machine
        :param test_data: Test data object
        """
        self.data = test_data
        self.test_tools = PuppeteerTestTools(vm_name=vm_name, test_data=self.data)
        self.vm = self.test_tools.vm

    def run(self, headless: bool = False, max_attempts: int = 3, interval: int = 5) -> None:
        """
        Run Dep.Tests/puppeteer tests on the VM with retry mechanism
        :param headless: Run in headless mode (Linux VMs only; Windows VMs always run with GUI)
        :param max_attempts: Maximum number of retry attempts
        :param interval: Delay between retries in seconds
        """
        if not self.test_tools.is_supported_os():
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
