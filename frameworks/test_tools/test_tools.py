# -*- coding: utf-8 -*-
import signal
from abc import ABC, abstractmethod
from os.path import join, dirname, isfile
from typing import Optional

from vboxwrapper import VirtualMachinException
from host_tools import File

from frameworks.test_data import TestData
from frameworks.decorators import retry, vm_data_created
from frameworks import MyConsole

from frameworks.VboxMachine import VboxMachine

console = MyConsole().console
print = console.print


def handle_interrupt(signum, frame):
    """
    Signal handler for keyboard interrupt (Ctrl+C).

    :param signum: Signal number
    :param frame: Current stack frame
    :raises KeyboardInterrupt: Always raises KeyboardInterrupt
    """
    raise KeyboardInterrupt


signal.signal(signal.SIGINT, handle_interrupt)


class TestTools(ABC):
    """
    Abstract base class for test execution tools.

    Provides common functionality for running tests on VirtualBox VMs
    including VM management, test execution, and report handling.
    """

    def __init__(self, vm: VboxMachine, test_data: TestData):
        """
        Initialize test tools with VM and test data.

        :param vm: VboxMachine instance to run tests on
        :param test_data: TestData instance containing test configuration
        """
        self.data = test_data
        self.vm = vm
        self.vm_name = self.vm.name
        self.password_cache = None

    @retry(max_attempts=2, exception_type=VirtualMachinException)
    @abstractmethod
    def run_vm(self, headless: bool = True) -> None:
        """
        Start and configure the virtual machine for testing.

        :param headless: Whether to run VM in headless mode
        """
        ...

    @vm_data_created
    @abstractmethod
    def run_test_on_vm(self, upload_files: list, create_test_dir: list):
        """
        Execute tests on the virtual machine.

        :param upload_files: List of files to upload to VM
        :param create_test_dir: List of directories to create on VM
        """
        ...

    @abstractmethod
    def download_report(self, path_from: str, path_to: str) -> bool:
        """
        Download test report from VM to local machine.

        :param path_from: Source path on VM
        :param path_to: Destination path on local machine
        :return: True if download successful, False otherwise
        """
        ...

    @abstractmethod
    def initialize_libs(self, report, paths) -> None:
        """
        Initialize required libraries and components for testing.

        :param report: Report object for test results
        :param paths: Paths configuration object
        """
        ...

    def stop_vm(self):
        """
        Stop the virtual machine.
        """
        self.vm.stop()

    @property
    def is_windows(self) -> bool:
        """
        Check if the VM is running Windows OS.

        :return: True if VM OS is Windows, False otherwise
        """
        return 'windows' in self.vm.os_type

    def _get_password(self, vm_dir: str) -> Optional[str]:
        """
        Retrieve VM password from cache, password file, or configuration.

        :param vm_dir: VM directory path for locating password file
        :return: VM password string
        :raises ValueError: If password cannot be obtained from any source
        """
        if self.password_cache:
            return self.password_cache

        try:
            password_file = join(dirname(vm_dir), 'password')
            password = File.read(password_file).strip() if isfile(password_file) else None
            self.password_cache = password or self.data.config.get('password')
        except (TypeError, FileNotFoundError):
            self.password_cache = self.data.config.get('password')

        if not self.password_cache:
            raise ValueError("Can't get VM password")

        return self.password_cache
