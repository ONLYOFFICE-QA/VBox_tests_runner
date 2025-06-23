# -*- coding: utf-8 -*-
from os.path import join, isfile

from vboxwrapper import VirtualMachinException
from host_tools.utils import Dir

from frameworks.VboxMachine import VboxMachine
from frameworks.decorators import vm_data_created
from frameworks.test_tools import TestTools, TestToolsWindows, TestToolsLinux


from .desktop_paths import DesktopPaths
from .desktop_report import DesktopReport
from .run_script import RunScript


class DesktopTestTools:

    def __init__(self, vm_name: str, test_data):
        self.data = test_data
        self.vm = VboxMachine(vm_name)
        self.test_tools = self._get_test_tools()
        self._initialize_report()

    def run_test(self, headless: bool) -> None:
        self.test_tools.run_vm(headless=headless)
        self.initialize_libs()
        self.test_tools.run_test_on_vm(upload_files=self.get_upload_files(), create_test_dir=self.get_test_dirs())
        self.test_tools.download_report(path_from=self._get_remote_report_path(), path_to=self.report.dir)
        if not self.report.exists() and self.report.column_is_empty("Os"):
            raise VirtualMachinException

        self.report.insert_vm_name(self.vm.name)

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

    @vm_data_created
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

    def handle_package_not_exists(self):
        print(f"[bold red]|ERROR|{self.vm.name}| Package {self.package_name} is not exists")
        self.report.write(self.data.version, self.vm.name, "PACKAGE_NOT_EXISTS")

    def handle_vm_creation_failure(self):
        print(f"[bold red]|ERROR|{self.vm.name}| Failed to create a virtual machine")
        self.report.write(self.data.version, self.vm.name, "FAILED_CREATE_VM")

    def _get_test_tools(self) -> TestTools:
        if 'windows' in self.vm.os_type:
            return TestToolsWindows(vm=self.vm, test_data=self.data)
        return TestToolsLinux(vm=self.vm, test_data=self.data)
