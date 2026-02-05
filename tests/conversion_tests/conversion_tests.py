# -*- coding: utf-8 -*-
import time
from pathlib import Path
from typing import Optional

from host_tools import File, HostInfo
from rich import print

from frameworks import PackageURLChecker, VersionHandler
from frameworks.VboxMachine import VboxMachine
from frameworks.decorators import vm_data_created
from frameworks.package_checker.report import CSVReport
from frameworks.test_tools import TestToolsLinux, TestToolsWindows, TestTools
from frameworks.test_data import PortalData
from tests.conversion_tests.conversion_paths.conversion_local_paths import ConversionLocalPaths

from .conversion_paths import ConversionPaths
from .conversion_test_data import ConversionTestData
from .run_script import RunScript

import subprocess as sb

class Report:
    pass


class ConversionTests:

    def __init__(self, vm_name: str, test_data: ConversionTestData):
        self.data = test_data
        self.host = HostInfo()
        self.portal_data = PortalData()
        self.vm = VboxMachine(vm_name)
        self.test_tools = self._get_test_tools()
        self.package_checker = PackageURLChecker()
        self.__package_name: Optional[str] = None
        self.__package_report: Optional[CSVReport] = None
        self.__packages_config: Optional[dict] = None

    def run(self, headless: bool = True, max_attempts: int = 5, interval: int = 5):
        """
        Runs the conversion tests on the virtual machine.
        :param headless: Whether to run the tests in headless mode.
        :param max_attempts: Maximum number of attempts to run the tests.
        :param interval: Interval between attempts in seconds.
        """
        if not self.check_package_exists():
            return

        attempt = 0
        while attempt < max_attempts:
            try:
                attempt += 1
                if self.is_host_tests():
                    self._run_test_on_host()
                else:
                    self._run_test_on_vm(headless=headless)
                break

            except KeyboardInterrupt:
                print("[bold red]|WARNING| Interruption by the user")
                raise

            except Exception as e:
                print(f"[bold yellow]|WARNING|{self.vm.name}| Attempt {attempt}/{max_attempts} failed: {e}")
                time.sleep(interval)
                if attempt == max_attempts:
                    print(f"[bold red]|ERROR|{self.vm.name}| Max attempts reached. Exiting.")
                    self.handle_vm_creation_failure()
                    raise

            finally:
                if not self.is_host_tests():
                    self.test_tools.stop_vm()

    def is_host_tests(self) -> bool:
        return (
            (self.host.is_windows and self.vm.name == "Windows")
            or (self.host.is_mac and self.vm.name == "MacOS")
        )

    @property
    def packages_config(self) -> dict:
        """
        Returns the packages configuration.
        :return: A dictionary containing the packages configuration.
        """
        if self.__packages_config is None:
            self.__packages_config = self._load_packages_config()
        return self.__packages_config

    @property
    def package_name(self) -> str:
        """
        Returns the package name for the current OS.
        :return: The package name as a string.
        """
        if self.__package_name is None:
            self.__package_name = self._get_package_name()
        return self.__package_name

    @property
    def package_report(self) -> CSVReport:
        """
        Returns the package report for the current version.
        :return: A CSVReport object containing the package report.
        """
        if self.__package_report is None:
            self.__package_report = self.package_checker.get_report(VersionHandler(self.data.version).without_build)
        return self.__package_report

    def _run_test_on_vm(self, headless: bool) -> None:
        """
        Runs a single test on the virtual machine.
        :param headless: Whether to run the test in headless mode.
        """
        self.test_tools.run_vm(headless=headless)
        self._initialize_libs()
        self.test_tools.run_test_on_vm(upload_files=self.get_upload_files(), create_test_dir=[])

    def _run_test_on_host(self) -> None:
        """
        Runs a single test on the host.
        """
        local_paths = ConversionLocalPaths()
        update_commands = [
            f"cd {local_paths.x2ttesting_dir} && git checkout master && git pull",
            f"cd {local_paths.fonts_dir} && git checkout master && git pull",
        ]
        for command in update_commands:
            print(f"[bold green]|INFO|{self.vm.name}| Updating repositories: {command}")
            sb.call(command, shell=True)

        executer = "powershell.exe " if self.host.is_windows else ""
        command = f"cd {local_paths.x2ttesting_dir} && {executer}{self.data.generate_run_command()}"
        sb.call(command, shell=True)

    def _initialize_libs(self) -> None:
        """
        Initializes the libraries required for the tests.
        """
        self._initialize_paths()
        self.test_tools.initialize_libs(
            report=Report(),
            paths=self.paths
        )

    @vm_data_created
    def _initialize_paths(self) -> ConversionPaths:
        """
        Initializes the paths required for the tests.
        :return: The initialized ConversionPaths object.
        """
        self.paths = ConversionPaths(os_info=self.vm.os_info, remote_user_name=self.vm.data.user)
        return self.paths

    def _get_test_tools(self) -> TestTools:
        """
        Returns the appropriate test tools based on the OS type.
        :return: A TestTools object for the current OS.
        """
        self.data.restore_snapshot = False
        self.data.configurate = False
        return TestToolsLinux(vm=self.vm, test_data=self.data)

    @vm_data_created
    def get_upload_files(self) -> list[tuple[str, str]]:
        """
        Returns a list of files to upload to the virtual machine.
        :return: A list of tuples containing local and remote file paths.
        """
        files = [
            (RunScript(test_data=self.data, paths=self.paths).create(), self.paths.remote.script_path),
        ]
        return [file for file in files if all(file)]

    def check_package_exists(self) -> bool:
        """
        Checks if the package exists and handles the case if it does not.
        :return: True if the package exists, False otherwise.
        """
        if not self.package_name:
            print(f"[bold red]|ERROR|{self.vm.name}| Package name is not found in packages_config.json")
            return True

        report_result = self.package_report.get_result(
            version=str(self.data.version),
            name=self.package_name,
            category="core"
        )

        if not report_result:
            result = self.package_checker.run(versions=self.data.version, names=[self.package_name], categories=["core"])
            if not result[str(self.data.version)]["core"][self.package_name]['result']:
                self.handle_package_not_exists()
                return False
        return True

    def handle_package_not_exists(self) -> None:
        """
        Handles the case when the package does not exist.
        """
        print(f"[bold red]|ERROR|{self.vm.name}| Package {self.package_name} is not exists")
        self.report.write(
            version=self.data.version,
            vm_name=self.vm.name,
            exit_code=0,
            stdout=self.portal_data.test_status.not_exists_package
        )

    def handle_vm_creation_failure(self) -> None:
        """
        Handles the failure of virtual machine creation.
        """
        print(f"[bold red]|ERROR|{self.vm.name}| Failed to create a virtual machine")
        self.report.write(
            version=self.data.version,
            vm_name=self.vm.name,
            exit_code=0,
            stdout=self.portal_data.test_status.failed_create_vm
        )

    def _get_package_name(self) -> Optional[str]:
        """
        Gets the package name for the current OS.
        :return: The package name as a string, or None if not found.
        """
        for os_family, os_list in self.packages_config.get('os_family', {}).items():
            if self.vm.name in os_list:
                return os_family
        return None

    def _load_packages_config(self) -> dict[str, list[str]]:
        """
        Loads the packages configuration from a JSON file.
        :return: A dictionary containing the packages configuration.
        """
        config_path = str(Path(__file__).parent / 'packages_config.json')
        return File.read_json(config_path)
