# -*- coding: utf-8 -*-
import time
from rich import print
from os.path import join, dirname, realpath
from typing import Optional

from host_tools import File
from .tools import DesktopTestData, DesktopTestTools
from frameworks.package_checker.check_packages import PackageURLChecker


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
        self.packages_config = self._load_packages_config()
        self.package_checker = PackageURLChecker()
        self.package_name = self._get_package_name()
        self.package_report = self.package_checker.get_report(self.data.version.without_build)

    @staticmethod
    def _load_packages_config() -> dict:
        """
        Load packages configuration from JSON file
        :return: Packages configuration dictionary
        """
        config_path = join(dirname(realpath(__file__)), 'packages_config.json')
        return File.read_json(config_path)

    def _get_package_name(self) -> Optional[str]:
        """
        Get the package name for the current OS
        :return: Package name string
        """
        for os_family, os_list in self.packages_config.get('os_family', {}).items():
            if self.vm.os_name in os_list:
                return os_family
        return None

    def _is_incompatible_package(self) -> bool:
        """
        Check if the package is incompatible with Windows
        :return: Name of the incompatible package or empty string
        """
        incompatible_packages = {
            'snap': self.data.snap,
            'appimage': self.data.appimage,
            'flatpak': self.data.flatpak
        }
        for package, is_enabled in incompatible_packages.items():
            if self.test_tools.is_windows and is_enabled:
                print(f"[cyan]|INFO|{self.vm.name}| Package {package} is compatible with Windows")
                return False
        return True

    def _check_package_exists(self) -> bool:
        """
        Check if package exists and handle if not
        """
        if not self.package_name:
            print(f"[bold red]|ERROR|{self.vm.name}| Package name is not found in packages_config.json")
            return True

        report_result = self.package_report.get_result(
            version=str(self.data.version),
            name=self.package_name,
            category="desktop"
        )

        if not report_result:
            result = self.package_checker.run(versions=self.data.version, names=[self.package_name], categories=["desktop"])
            if not result[self.data.version]["desktop"][self.package_name]['result']:
                self.test_tools.handle_package_not_exists()
                return False

        return True

    def run(self, headless: bool = False, max_attempts: int = 5, interval: int = 5) -> None:
        """
        Run desktop test with retry mechanism
        :param headless: Run in headless mode
        :param max_attempts: Maximum number of retry attempts
        :param interval: Delay between retries in seconds
        """
        if not self._check_package_exists():
            return

        if not self._is_incompatible_package():
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
