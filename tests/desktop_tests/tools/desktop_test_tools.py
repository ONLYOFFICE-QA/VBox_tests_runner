# -*- coding: utf-8 -*-
from os.path import join, isfile
from typing import Optional

from rich import print

from host_tools.utils import Dir

from frameworks.VboxMachine import VboxMachine
from frameworks.decorators import vm_data_created
from frameworks.test_tools import TestTools, TestToolsWindows, TestToolsLinux
from frameworks.test_data import PortalData

from vboxwrapper import VirtualMachinException

from .desktop_paths import DesktopPaths
from .desktop_report import DesktopReport
from .desktop_package_manager import DesktopPackageManager
from .run_script import RunScript


class DesktopTestTools:

    def __init__(self, vm_name: str, test_data):
        self.data = test_data
        self.portal_data = PortalData()
        self.vm = VboxMachine(vm_name)
        self.test_tools = self._get_test_tools()
        self._initialize_report()
        self.package_manager = DesktopPackageManager(vm_name, str(test_data.version), self.vm.os_name)

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
        Check if package exists using optimized package manager
        :return: True if package exists, False otherwise
        """
        if not self.package_manager.check_package_exists('desktop'):
            self.package_manager.handle_package_not_exists(self.report)
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
                print(f"[cyan]|INFO|{self.vm.name}| Package {package} is not compatible with Windows")
                return False
        return True

    def handle_package_not_exists(self):
        """Handle package not exists using package manager"""
        self.package_manager.handle_package_not_exists(self.report)

    def handle_vm_creation_failure(self):
        """Handle VM creation failure using package manager"""
        self.package_manager.handle_vm_creation_failure(self.report)

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
