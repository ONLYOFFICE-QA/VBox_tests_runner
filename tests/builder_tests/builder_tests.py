# -*- coding: utf-8 -*-
from os.path import join, isfile

from vboxwrapper import VirtualMachinException
from host_tools import File

from frameworks import VersionHandler
from frameworks.decorators import vm_data_created
from frameworks.test_tools import TestToolsLinux, TestToolsWindows, TestTools
from frameworks.test_data import PortalData

from tests.common import BaseTest
from .builder_paths import BuilderPaths, BuilderLocalPaths
from .builder_report import BuilderReport
from .builder_test_data import BuilderTestData
from .builder_package_manager import BuilderPackageManager
from .run_script import RunScript

class BuilderTests(BaseTest):

    def __init__(self, vm_name: str, test_data: BuilderTestData):
        """
        Initializes the BuilderTests class with a virtual machine name and test data.
        :param vm_name: The name of the virtual machine to use for testing.
        :param test_data: The test data to use for the tests.
        """
        super().__init__(vm_name, test_data)
        self.portal_data = PortalData()
        self.package_manager = BuilderPackageManager(vm_name, test_data.version)
        self._initialize_report()

    def run(self, headless: bool = False, max_attempts: int = 5, interval: int = 5):
        """
        Runs the builder tests on the virtual machine.
        :param headless: Whether to run the tests in headless mode.
        :param max_attempts: Maximum number of attempts to run the tests.
        :param interval: Interval between attempts in seconds.
        """
        if not self.package_manager.check_package_exists('builder'):
            self.package_manager.handle_package_not_exists(self.report)
            return

        self.run_with_retry(self._run_test, headless, max_attempts, interval)

    @property
    def packages_config(self) -> dict:
        """Returns the packages configuration."""
        return self.package_manager.packages_config

    @property
    def package_name(self) -> str:
        """Returns the package name for the current OS."""
        return self.package_manager.package_name

    @property
    def package_report(self):
        """Returns the package report for the current version."""
        return self.package_manager.package_report

    def _run_test(self, headless: bool) -> None:
        """
        Runs a single test on the virtual machine.
        :param headless: Whether to run the test in headless mode.
        """
        self.test_tools.run_vm(headless=headless)
        self._initialize_libs()
        self.test_tools.run_test_on_vm(upload_files=self.get_upload_files(), create_test_dir=self.get_test_dirs())
        self.test_tools.download_report(path_from=self.paths.remote.builder_report_dir, path_to=self.report.dir)
        self.report.path = File.last_modified(self.report.dir)
        if not isfile(self.report.path) or self.report.column_is_empty('Os'):
            raise VirtualMachinException

    def _initialize_libs(self) -> None:
        """
        Initializes the libraries required for the tests.
        """
        self._initialize_paths()
        self.test_tools.initialize_libs(
            report=self.report,
            paths=self.paths
        )

    def _initialize_report(self) -> BuilderReport:
        """
        Initializes the report for the builder tests.
        :return: The initialized BuilderReport object.
        """
        report_file = join(
            BuilderLocalPaths.builder_report_dir,
            self.data.version,
            self.vm.name,
            f"builder_report_v{self.data.version}.csv"
        )
        self.report = BuilderReport(report_file)
        return self.report

    @vm_data_created
    def _initialize_paths(self) -> BuilderPaths:
        """
        Initializes the paths required for the tests.
        :return: The initialized BuilderPaths object.
        """
        self.paths = BuilderPaths(os_info=self.vm.os_info, remote_user_name=self.vm.data.user)
        return self.paths

    def _get_test_tools(self) -> TestTools:
        """
        Returns the appropriate test tools based on the OS type.
        :return: A TestTools object for the current OS.
        """
        if 'windows' in self.vm.os_type:
            return TestToolsWindows(vm=self.vm, test_data=self.data)
        return TestToolsLinux(vm=self.vm, test_data=self.data)


    @vm_data_created
    def get_upload_files(self) -> list[tuple[str, str]]:
        """
        Returns a list of files to upload to the virtual machine.
        :return: A list of tuples containing local and remote file paths.
        """
        files = [
            (self.data.token_file, self.paths.remote.tg_token_file),
            (self.data.chat_id_file, self.paths.remote.tg_chat_id_file),
            (RunScript(test_data=self.data, paths=self.paths).create(), self.paths.remote.script_path),
            (self.paths.local.dep_test_archive, self.paths.remote.dep_test_archive),
        ]

        return [file for file in files if all(file)]

    def get_test_dirs(self) -> list[str]:
        """
        Returns a list of directories to create on the virtual machine for testing.
        :return: A list of remote directory paths.
        """
        remote_test_dirs = [
            self.paths.remote.script_dir,
            self.paths.remote.tg_dir,
        ]

        return remote_test_dirs

    def handle_failure(self) -> None:
        """Handle test failure by delegating to package manager"""
        self.package_manager.handle_vm_creation_failure(self.report)
