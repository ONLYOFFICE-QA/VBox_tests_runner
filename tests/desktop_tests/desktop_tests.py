# -*- coding: utf-8 -*-
import time
from os.path import join, isfile

from VBoxWrapper import VirtualMachinException
from host_tools.utils import Dir
from rich import print


from frameworks.VboxMachine import VboxMachine
from frameworks.decorators import vm_data_created
from frameworks.test_tools import TestToolsWindows, TestToolsLinux, TestTools

from . import DesktopReport

from .tools import DesktopTestData
from .tools.desktop_paths import DesktopPaths
from .tools.run_script import RunScript


class DesktopTest:
    def __init__(self, vm_name: str, test_data: DesktopTestData):
        self.data = test_data
        self.vm = VboxMachine(vm_name)
        self.test_tools = self._get_test_tools()
        self._initialize_report()

    def run(self, headless: bool = False, max_attempts: int = 5, interval: int = 5) -> None:
        if self.test_tools.is_windows and self.data.snap:
            return print(f"[cyan]|INFO|{self.test_tools.vm_name}| Unable to install snap package on windows")

        if self.test_tools.is_windows and self.data.appimage:
            return print(f"[cyan]|INFO|{self.test_tools.vm_name}| Unable to install appimage on windows")

        if self.test_tools.is_windows and self.data.flatpak:
            return print(f"[cyan]|INFO|{self.test_tools.vm_name}| Unable to install flatpak on windows")

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
                    self.handle_vm_creation_failure()
                    raise

            finally:
                self.test_tools.stop_vm()

    def _run_test(self, headless: bool) -> None:
        self.test_tools.run_vm(headless=headless)
        self._initialize_libs()
        self.test_tools.run_test_on_vm(upload_files=self.get_upload_files(), create_test_dir=self.get_test_dirs())
        if not self.report.exists():
            raise VirtualMachinException

    def _initialize_libs(self):
        self.test_tools.initialize_libs(
            report=self._initialize_report(),
            paths=self._initialize_paths,
            remote_report_path=f"{self.paths.remote.report_dir}/{self.data.title}/{self.data.version}"
        )

    def _get_test_tools(self) -> TestTools:
        if 'windows' in self.vm.os_type:
            return TestToolsWindows(vm=self.vm, test_data=self.data)
        return TestToolsLinux(vm=self.vm, test_data=self.data)

    def _initialize_report(self):
        report_file = join(self.data.report_dir, self.vm.name, f"{self.data.version}_{self.data.title}_report.csv")
        self.report = DesktopReport(report_file)
        Dir.delete(self.report.dir, clear_dir=True)
        return self.report

    @vm_data_created
    def _initialize_paths(self):
        self.paths = DesktopPaths(os_type=self.vm.os_type, remote_user_name=self.vm.data.user)
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

    def handle_vm_creation_failure(self):
        print(f"[bold red]|ERROR|{self.vm.name}| Failed to create a virtual machine")
        self.report.write(self.data.version, self.vm.name, "FAILED_CREATE_VM")
