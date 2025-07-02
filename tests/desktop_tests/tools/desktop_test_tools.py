# -*- coding: utf-8 -*-
from os.path import join, isfile, dirname, realpath
from typing import Optional

from rich import print

from host_tools import File
from host_tools.utils import Dir

from frameworks.VboxMachine import VboxMachine
from frameworks.decorators import vm_data_created
from frameworks.test_tools import TestTools, TestToolsWindows, TestToolsLinux
from frameworks.package_checker.check_packages import PackageURLChecker

from vboxwrapper import VirtualMachinException

from .desktop_paths import DesktopPaths
from .desktop_report import DesktopReport
from .run_script import RunScript


class DesktopTestTools:

    def __init__(self, vm_name: str, test_data):
        self.data = test_data
        self.vm = VboxMachine(vm_name)
        self.test_tools = self._get_test_tools()
        self._initialize_report()
        self.packages_config = self._load_packages_config()
        self.package_checker = PackageURLChecker()
        self.package_name = self._get_package_name(self.packages_config, self.vm.os_name)
        self.package_report = self.package_checker.get_report(self.data.version.without_build)

    def run_test(self, headless: bool) -> None:
        self.test_tools.run_vm(headless=headless)
        self.initialize_libs()
        self.test_tools.run_test_on_vm(upload_files=self.get_upload_files(), create_test_dir=self.get_test_dirs())
        self.test_tools.download_report(path_from=self._get_remote_report_path(), path_to=self.report.dir)
        if not self.report.exists() and self.report.column_is_empty("Os"):
            raise VirtualMachinException
        self.report.insert_vm_name(self.vm.name)

    def check_package_exists(self) -> bool:
        """
        Check if package exists and handle if not
        :return: True if package exists, False otherwise
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
                self.handle_package_not_exists()
                return False
        return True

    def is_incompatible_package(self) -> bool:
        """
        Check if the package is incompatible with Windows (snap, appimage, flatpak)
        :return: True if the package is compatible with Windows, False otherwise
        """
        incompatible_packages = {
            'snap': self.data.snap,
            'appimage': self.data.appimage,
            'flatpak': self.data.flatpak
        }
        for package, is_enabled in incompatible_packages.items():
            if self.is_windows and is_enabled:
                print(f"[cyan]|INFO|{self.vm.name}| Package {package} is compatible with Windows")
                return False
        return True

    def handle_package_not_exists(self):
        print(f"[bold red]|ERROR|{self.vm.name}| Package {self.package_name} is not exists")
        self.report.write(self.data.version, self.vm.name, "PACKAGE_NOT_EXISTS")

    def handle_vm_creation_failure(self):
        print(f"[bold red]|ERROR|{self.vm.name}| Failed to create a virtual machine")
        self.report.write(self.data.version, self.vm.name, "FAILED_CREATE_VM")

    def get_upload_files(self) -> list:
        files = [
            (self.data.token_file, self.paths.remote.tg_token_file),
            (self.data.chat_id_file, self.paths.remote.tg_chat_id_file),
            (RunScript(test_data=self.data, paths=self.paths).create(), self.paths.remote.script_path),
            (self.data.config_path, self.paths.remote.custom_config_path)
        ]
        optional_files = [
            (self.paths.local.proxy_config, self.paths.remote.proxy_config_file),
            (self.paths.local.lic_file, self.paths.remote.lic_file)
        ]
        files.extend((src, dst) for src, dst in optional_files if isfile(src))
        return [file for file in files if all(file)]

    def get_test_dirs(self) -> list:
        remote_test_dirs = [
            self.paths.remote.script_dir,
            self.paths.remote.tg_dir,
        ]
        if self.test_tools.is_windows:
            return remote_test_dirs
        return remote_test_dirs + [self.paths.remote.github_token_dir]

    @property
    def is_windows(self) -> bool:
        return self.test_tools.is_windows

    def initialize_libs(self):
        self.test_tools.initialize_libs(
            report=self._initialize_report(),
            paths=self._initialize_paths(),
        )

    def _get_remote_report_path(self) -> str:
        return f"{self.paths.remote.report_dir}/{self.data.title}/{self.data.version}"

    def _initialize_report(self):
        report_file = join(self.data.report_dir, self.vm.name, f"{self.data.version}_{self.data.title}_report.csv")
        self.report = DesktopReport(report_file)
        Dir.delete(self.report.dir, clear_dir=True)
        return self.report

    @vm_data_created
    def _initialize_paths(self):
        self.paths = DesktopPaths(os_info=self.vm.os_info, remote_user_name=self.vm.data.user)
        return self.paths

    def _get_test_tools(self) -> TestTools:
        if 'windows' in self.vm.os_type:
            return TestToolsWindows(vm=self.vm, test_data=self.data)
        return TestToolsLinux(vm=self.vm, test_data=self.data)

    def _load_packages_config(self) -> dict:
        """
        Load packages configuration from JSON file
        :param self: DesktopTestTools instance
        :return: Packages configuration dictionary
        """
        config_path = join(dirname(realpath(__file__)), '../packages_config.json')
        return File.read_json(config_path)

    def _get_package_name(self, packages_config: dict, os_name: str) -> Optional[str]:
        """
        Get the package name for the current OS
        :param packages_config: Packages configuration dictionary
        :param os_name: Name of the OS
        :return: Package name string
        """
        for os_family, os_list in packages_config.get('os_family', {}).items():
            if os_name in os_list:
                return os_family
        return None
