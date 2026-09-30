# -*- coding: utf-8 -*-
import os
import re
import sys
import time
from datetime import datetime
from os.path import dirname, join
from pathlib import Path
from tempfile import gettempdir
from typing import Optional

from host_tools import File, HostInfo
from rich import print
from telegram import Telegram

from frameworks import PackageURLChecker, VersionHandler
from frameworks.VboxMachine import VboxMachine
from frameworks.decorators import vm_data_created
from frameworks.diagnostics import diagnostics, install_vbox_probe
from frameworks.package_checker.report import CSVReport
from frameworks.test_tools import VBoxGuestTestTools, TestTools
from tests.conversion_tests.conversion_paths.conversion_local_paths import ConversionLocalPaths

from .conversion_paths import ConversionPaths
from .conversion_test_data import ConversionTestData
from .run_script import RunScript

import subprocess as sb

class Report:
    """Stub class for report functionality."""
    pass


class ConversionTests:

    def __init__(self, vm_name: str, test_data: ConversionTestData):
        self.data = test_data
        self.host = HostInfo()
        self.vm = VboxMachine(vm_name)
        self.test_tools = self._get_test_tools()
        self.package_checker = PackageURLChecker()
        self.__package_name: Optional[str] = None
        self.__package_report: Optional[CSVReport] = None
        self.__packages_config: Optional[dict] = None

    def run(self, headless: bool = False, max_attempts: int = 5, interval: int = 5):
        """
        Runs the conversion tests on the virtual machine.
        :param headless: Whether to run the tests in headless mode.
        :param max_attempts: Maximum number of attempts to run the tests.
        :param interval: Interval between attempts in seconds.
        """
        diag = diagnostics()
        diag.start(f"conversion_{self.vm.name}")
        install_vbox_probe(diag)
        print(f"[green]|INFO|{self.vm.name}| Diagnostics log: [cyan]{diag.log_path}[/]")

        try:
            self._run(headless=headless, max_attempts=max_attempts, interval=interval)
        finally:
            diag.stop()

    def _run(self, headless: bool, max_attempts: int, interval: int) -> None:
        """
        Runs the conversion tests, retrying the whole test when it fails.
        :param headless: Whether to run the tests in headless mode.
        :param max_attempts: Maximum number of attempts to run the tests.
        :param interval: Interval between attempts in seconds.
        """
        diag = diagnostics()

        with diag.phase("check_package_exists"):
            if not self.check_package_exists():
                return

        attempt = 0
        while attempt < max_attempts:
            try:
                attempt += 1
                with diag.phase(f"attempt_{attempt}_of_{max_attempts}"):
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
                    try:
                        with diag.phase("stop_vm"):
                            self.test_tools.stop_vm()
                    except Exception as stop_error:
                        print(
                            f"[bold yellow]|WARNING|{self.vm.name}| "
                            f"stop_vm after attempt failed: {stop_error}"
                        )

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
        diag = diagnostics()

        with diag.phase("run_vm"):
            self.test_tools.run_vm(headless=headless)

        with diag.phase("initialize_libs"):
            self._initialize_libs()

        with diag.phase("run_test_on_vm"):
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
        log_path = self._get_host_run_log_path()
        return_code = self._run_with_log(command, log_path)

        if return_code != 0:
            print(
                f"[bold red]|ERROR|{self.vm.name}| Conversion tests failed with exit code {return_code}. "
                f"Log: [cyan]{log_path}[/]"
            )
            self._send_host_failure_to_tg(return_code, log_path)

    def _get_host_run_log_path(self) -> str:
        """
        Returns the path of the log file for the conversion run on the host.
        :return: Path to the log file next to the diagnostics log, or in the temp directory.
        """
        log_dir = dirname(diagnostics().log_path) if diagnostics().log_path else gettempdir()
        return join(log_dir, f"conversion_{self.vm.name}_{datetime.now():%Y%m%d_%H%M%S}_output.log")

    @staticmethod
    def _run_with_log(command: str, log_path: str) -> int:
        """
        Runs the command, streaming its output to the console and saving it to the log file.
        :param command: Command to run.
        :param log_path: Path to the log file.
        :return: Exit code of the command.
        """
        env = {**os.environ, "PYTHONUTF8": "1", "FORCE_COLOR": "1", "TTY_COMPATIBLE": "1"}
        with open(log_path, 'wb') as log, sb.Popen(
                command, shell=True, stdout=sb.PIPE, stderr=sb.STDOUT, env=env
        ) as process:
            while chunk := process.stdout.read1(4096):
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
                log.write(chunk)
            return_code = process.wait()

        with open(log_path, 'r', encoding='utf-8', errors='replace') as log:
            text = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', log.read())
        with open(log_path, 'w', encoding='utf-8') as log:
            log.write(text)

        return return_code

    def _send_host_failure_to_tg(self, return_code: int, log_path: str) -> None:
        """
        Sends a message about the failed conversion run with the log to Telegram.
        :param return_code: Exit code of the conversion run.
        :param log_path: Path to the log file.
        """
        if not self.data.telegram:
            return

        caption = (
            f"Conversion tests failed on version: `{self.data.version}`\n\n"
            f"VM: `{self.vm.name}`\n"
            f"Exit code: `{return_code}`\n"
            f"Error: `{self._get_last_error(log_path)}`\n"
            f"Host: `{self.host.name(pretty=True)} {self.host.arch}`"
        )
        try:
            Telegram(token=self.data.tg_token, chat_id=self.data.tg_chat_id).send_document(log_path, caption=caption)
        except Exception as e:
            print(f"[bold red]|ERROR|{self.vm.name}| Failed to send the conversion failure to Telegram: {e}")

    @staticmethod
    def _get_last_error(log_path: str, max_length: int = 500) -> str:
        """
        Returns the last error line from the log file.
        :param log_path: Path to the log file.
        :param max_length: Maximum length of the returned line.
        :return: The last exception line, or the last non-empty line if there is none.
        """
        with open(log_path, 'r', encoding='utf-8', errors='replace') as log:
            lines = [line.strip() for line in log if line.strip()]

        errors = [line for line in lines if re.match(r'^[\w.]+(Error|Exception)\b', line)]
        error = (errors or lines or ['Unknown error'])[-1]
        return error.replace('`', "'")[:max_length]

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
        return VBoxGuestTestTools(vm=self.vm, test_data=self.data)

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

    def handle_vm_creation_failure(self) -> None:
        """
        Handles the failure of virtual machine creation.
        """
        print(f"[bold red]|ERROR|{self.vm.name}| Failed to create a virtual machine")

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
