# -*- coding: utf-8 -*-
import time
from os.path import join, isfile, dirname, realpath
from typing import Optional

from vboxwrapper import VirtualMachinException
from host_tools import File
from rich import print

from frameworks import PackageURLChecker, VersionHandler
from frameworks.VboxMachine import VboxMachine
from frameworks.decorators import vm_data_created
from frameworks.package_checker.report import CSVReport
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
        self.package_checker = PackageURLChecker()
        self.__package_name: Optional[str] = None
        self.__package_report: Optional[CSVReport] = None
        self.__packages_config: Optional[dict] = None

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

    @property
    def packages_config(self) -> dict:
        if self.__packages_config is None:
            self.__packages_config = self._load_packages_config()
        return self.__packages_config

    @property
    def package_name(self) -> str:
        if self.__package_name is None:
            self.__package_name = self._get_package_name()
        return self.__package_name

    @property
    def package_report(self) -> CSVReport:
        if self.__package_report is None:
            self.__package_report = self.package_checker.get_report(VersionHandler(self.data.version).without_build)
        return self.__package_report

    def _run_test(self, headless: bool) -> None:
        if not self.check_package_exists():
            return

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
        self.paths = BuilderPaths(os_info=self.vm.os_info, remote_user_name=self.vm.data.user)
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
            category="builder"
        )

        if not report_result:
            result = self.package_checker.run(versions=self.data.version, names=[self.package_name], categories=["builder"])
            if not result[str(self.data.version)]["builder"][self.package_name]['result']:
                self.handle_package_not_exists()
                return False
        return True

    def handle_package_not_exists(self):
        print(f"[bold red]|ERROR|{self.vm.name}| Package {self.package_name} is not exists")
        self.report.writer(mode='a', message=[self.data.version, self.vm.name, "PACKAGE_NOT_EXISTS"])

    def _get_package_name(self) -> Optional[str]:
        """
        Get the package name for the current OS
        :param packages_config: Packages configuration dictionary
        :param os_name: Name of the OS
        :return: Package name string
        """
        for os_family, os_list in self.packages_config.get('os_family', {}).items():
            if self.vm.name in os_list:
                return os_family
        return None

    def _load_packages_config(self) -> dict:
        """
        Load packages configuration from JSON file
        :param self: DesktopTestTools instance
        :return: Packages configuration dictionary
        """
        config_path = join(dirname(realpath(__file__)), './packages_config.json')
        return File.read_json(config_path)
