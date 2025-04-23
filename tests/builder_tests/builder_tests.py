# -*- coding: utf-8 -*-
import time
from os.path import join, isfile

from vboxwrapper import VirtualMachinException
from host_tools import File
from rich import print

from frameworks.VboxMachine import VboxMachine
from frameworks.decorators import vm_data_created
from frameworks.test_tools import TestToolsLinux, TestToolsWindows, TestTools

from .builder_paths import BuilderPaths
from .builder_report import BuilderReport
from .builder_test_data import BuilderTestData
from .run_script import RunScript


class BuilderTests:

    def __init__(self, vm_name: str, test_data: BuilderTestData):
        self.data = test_data
        self.vm = VboxMachine(vm_name)
        self.test_tools = self._get_test_tools()

    def run(self, headless: bool = False, max_attempts: int = 5, interval: int = 5):
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
        self.test_tools.download_report(path_from=self.paths.remote.builder_report_dir, path_to=self.report.dir)
        self.report.path = File.last_modified(self.report.dir)
        if not isfile(self.report.path) or self.report.column_is_empty('Os'):
            raise VirtualMachinException

    def _initialize_libs(self):
        self._initialize_paths()
        self._initialize_report()
        self.test_tools.initialize_libs(
            report=self.report,
            paths=self.paths
        )

    def _initialize_report(self):
        report_file = join(
            self.paths.local.builder_report_dir,
            self.data.version,
            self.vm.name,
            f"builder_report_v{self.data.version}.csv"
        )
        self.report = BuilderReport(report_file)
        return self.report

    @vm_data_created
    def _initialize_paths(self):
        self.paths = BuilderPaths(os_type=self.vm.os_type, remote_user_name=self.vm.data.user)
        return self.paths

    def _get_test_tools(self) -> TestTools:
        if 'windows' in self.vm.os_type:
            return TestToolsWindows(vm=self.vm, test_data=self.data)
        return TestToolsLinux(vm=self.vm, test_data=self.data)

    def handle_vm_creation_failure(self):
        print(f"[bold red]|ERROR|{self.vm.name}| Failed to create a virtual machine")
        self.report.writer(mode='a', message=[self.data.version, self.vm.name, "FAILED_CREATE_VM"])

    @vm_data_created
    def get_upload_files(self) -> list:
        files = [
            (self.data.token_file, self.paths.remote.tg_token_file),
            (self.data.chat_id_file, self.paths.remote.tg_chat_id_file),
            (RunScript(test_data=self.data, paths=self.paths).create(), self.paths.remote.script_path),
            (self.paths.local.dep_test_archive, self.paths.remote.dep_test_archive),
        ]

        return [file for file in files if all(file)]

    def get_test_dirs(self) -> list:
        remote_test_dirs = [
            self.paths.remote.script_dir,
            self.paths.remote.tg_dir,
        ]

        return remote_test_dirs
