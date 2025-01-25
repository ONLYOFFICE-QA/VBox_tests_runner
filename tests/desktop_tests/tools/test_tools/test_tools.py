# -*- coding: utf-8 -*-
import signal
from abc import ABC, abstractmethod
from os.path import join, dirname, isfile
from typing import Optional

from VBoxWrapper import VirtualMachinException
from host_tools import File, Dir

from frameworks.decorators import retry, vm_data_created
from frameworks import  MyConsole

from ..desktop_report import DesktopReport
from ..paths import Paths
from ..run_script import RunScript
from ..test_data import TestData
from ..VboxMachine import VboxMachine


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

        self._initialize_report()

    @retry(max_attempts=2, exception_type=VirtualMachinException)
    @abstractmethod
    def run_vm(self, headless: bool = True) -> None: ...

    @vm_data_created
    @abstractmethod
    def run_test_on_vm(self): ...

    @abstractmethod
    def download_and_check_report(self, *args) -> bool: ...

    def stop_vm(self):
        self.vm.stop()

    def _initialize_report(self):
        report_file = join(self.data.report_dir, self.vm_name, f"{self.data.version}_{self.data.title}_report.csv")
        self.report = DesktopReport(report_file)
        Dir.delete(self.report.dir, clear_dir=True)

    @vm_data_created
    def _initialize_run_script(self):
        self.run_script = RunScript(test_data=self.data, paths=self.paths)

    @vm_data_created
    def _initialize_paths(self):
        self.paths = Paths(os_type=self.vm.os_type, remote_user_name=self.vm.data.user)

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

    def handle_vm_creation_failure(self):
        print(f"[bold red]|ERROR|{self.vm_name}| Failed to create a virtual machine")
        self.report.write(self.data.version, self.vm_name, "FAILED_CREATE_VM")

    def get_upload_files(self) -> list:
        return [
            (self.data.token_file, self.paths.remote.tg_token_file),
            (self.data.chat_id_file, self.paths.remote.tg_chat_id_file),
            (self.paths.local.proxy_config, self.paths.remote.proxy_config_file),
            (self.run_script.create(), self.paths.remote.script_path),
            (self.data.config_path, self.paths.remote.custom_config_path),
            (self.paths.local.lic_file, self.paths.remote.lic_file),
        ]
