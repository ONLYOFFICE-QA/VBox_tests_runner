# -*- coding: utf-8 -*-
import signal
from abc import ABC, abstractmethod
from os.path import join, dirname, isfile
from typing import Optional

from VBoxWrapper import VirtualMachinException
from host_tools import File

from frameworks.test_data import TestData
from frameworks.decorators import retry, vm_data_created
from frameworks import MyConsole

from frameworks.VboxMachine import VboxMachine

console = MyConsole().console
print = console.print


def handle_interrupt(signum, frame):
    raise KeyboardInterrupt


signal.signal(signal.SIGINT, handle_interrupt)


class TestTools(ABC):

    def __init__(self, vm: VboxMachine, test_data: TestData):
        self.data = test_data
        self.vm = vm
        self.vm_name = self.vm.name
        self.password_cache = None

    @retry(max_attempts=2, exception_type=VirtualMachinException)
    @abstractmethod
    def run_vm(self, headless: bool = True) -> None:
        ...

    @vm_data_created
    @abstractmethod
    def run_test_on_vm(self, upload_files: list, create_test_dir: list):
        ...

    @abstractmethod
    def download_report(self, path_from: str, path_to: str) -> bool:
        ...

    @abstractmethod
    def initialize_libs(self, report, paths) -> None:
        ...

    def stop_vm(self):
        self.vm.stop()

    @property
    def is_windows(self) -> bool:
        return 'windows' in self.vm.os_type

    def _get_password(self, vm_dir: str) -> Optional[str]:
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