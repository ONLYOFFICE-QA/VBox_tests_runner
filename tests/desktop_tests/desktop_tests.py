# -*- coding: utf-8 -*-
import time
from rich import print

from .tools import DesktopTestData, DesktopTestTools


class DesktopTest:
    def __init__(self, vm_name: str, test_data: DesktopTestData):
        self.data = test_data
        self.test_tools = DesktopTestTools(vm_name=vm_name, test_data=self.data)
        self.vm = self.test_tools.vm

    def run(self, headless: bool = False, max_attempts: int = 5, interval: int = 5) -> None:
        if self.test_tools.is_windows and self.data.snap:
            return print(f"[cyan]|INFO|{self.vm.name}| Unable to install snap package on windows")

        if self.test_tools.is_windows and self.data.appimage:
            return print(f"[cyan]|INFO|{self.vm.name}| Unable to install appimage on windows")

        if self.test_tools.is_windows and self.data.flatpak:
            return print(f"[cyan]|INFO|{self.vm.name}| Unable to install flatpak on windows")

        attempt = 0
        while attempt < max_attempts:
            try:
                attempt += 1
                self.test_tools.run_test(headless=headless)
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
                self.test_tools.test_tools.stop_vm()
