# -*- coding: utf-8 -*-
import signal
from os.path import join, dirname, isfile
from typing import Optional

from VBoxWrapper import VirtualMachinException
from frameworks.console import MyConsole
from frameworks.decorators import retry, vm_data_created
from host_tools import File, Dir
from ssh_wrapper import Ssh, Sftp, ServerData

from .VboxMachine import VboxMachine
from .desktop_report import DesktopReport
from .paths import Paths
from .ssh_connection import SSHConnection
from .linux_script_demon import LinuxScriptDemon
from .run_script import RunScript
from .test_data import TestData


console = MyConsole().console
print = console.print

def handle_interrupt(signum, frame):
    raise KeyboardInterrupt

signal.signal(signal.SIGINT, handle_interrupt)


class TestTools:

    def __init__(self, vm_name: str, test_data: TestData, vm_cpus: int = 4, vm_memory: int = 4096):
        self.vm_cores = vm_cpus
        self.vm_memory = vm_memory
        self.data = test_data
        self.vm_name = vm_name
        self.vm = VboxMachine(self.vm_name, cores=self.vm_cores, memory=self.vm_memory)
        self.password_cache = None

        self._initialize_report()

    @retry(max_attempts=2, exception_type=VirtualMachinException)
    def run_vm(self, headless: bool = True):
        try:
            self.vm.run(headless=headless, status_bar=self.data.status_bar)
            self._initialize_paths()
            self._initialize_run_script()
            self._initialize_linux_demon()

        except VirtualMachinException:
            self._handle_vm_creation_failure()

    def stop_vm(self):
        self.vm.stop()

    @vm_data_created
    def run_script_on_vm(self):
        self._clean_known_hosts(self.vm.data.ip)
        server = self._get_server()

        with Ssh(server) as ssh, Sftp(server, ssh.connection) as sftp:
            connect = SSHConnection(ssh=ssh, sftp=sftp, test_data=self.data, paths=self.paths)
            connect.change_vm_service_dir_access(self.vm.data.user)
            connect.upload_test_files(self.linux_demon, self.run_script)
            connect.start_my_service(self.linux_demon.start_demon_commands())
            connect.wait_execute_service(status_bar=self.data.status_bar)

            if self._download_and_check_report(connect):
                self.report.insert_vm_name(self.vm_name)

    def _download_and_check_report(self, connect):
        if connect.download_report(self.data.title, self.data.version, self.report.dir):
            if self.report.column_is_empty("Os"):
                raise FileNotFoundError
            return True

        print(f"[red]|ERROR| Can't download report from {self.vm.data.name}.")
        self.report.write(self.data.version, self.vm.data.name, "REPORT_NOT_EXISTS")
        return False

    def _get_server(self) -> ServerData:
        return ServerData(
            self.vm.data.ip,
            self.vm.data.user,
            self._get_password(self.vm.data.local_dir),
            self.vm.data.name
        )

    def _initialize_report(self):
        report_file = join(self.data.report_dir, self.vm_name, f"{self.data.version}_{self.data.title}_report.csv")
        Dir.create(dirname(report_file), stdout=False)
        self.report = DesktopReport(report_file)

    @vm_data_created
    def _initialize_run_script(self):
        self.run_script = RunScript(
            version=self.data.version,
            old_version=self.data.update_from,
            telegram=self.data.telegram,
            custom_config_path=self.data.custom_config_mode,
            desktop_testing_url=self.data.desktop_testing_url,
            branch=self.data.branch,
            paths=self.paths
        )

    @vm_data_created
    def _initialize_linux_demon(self):
        self.linux_demon = LinuxScriptDemon(
            exec_script_path=self.paths.remote.script_path,
            user=self.vm.data.user,
            name=self.paths.remote.my_service_name
        )

    @vm_data_created
    def _initialize_paths(self):
        self.paths = Paths(remote_user_name=self.vm.data.user)

    def _clean_known_hosts(self, ip: str):
        with open(self.paths.local.know_hosts, 'r') as file:
            filtered_lines = [line for line in file if not line.startswith(ip)]
        with open(self.paths.local.know_hosts, 'w') as file:
            file.writelines(filtered_lines)

    def _get_password(self, vm_dir: str) -> Optional[str]:
        if self.password_cache:
            return self.password_cache

        try:
            password_file = join(dirname(vm_dir), 'password')
            password = File.read(password_file).strip() if isfile(password_file) else None
            self.password_cache = password or self.data.config.get('password')
        except (TypeError, FileNotFoundError):
            self.password_cache = self.data.config.get('password')

        return self.password_cache

    def _handle_vm_creation_failure(self):
        print(f"[bold red]|ERROR|{self.vm_name}| Failed to create a virtual machine")
        self.report.write(self.data.version, self.vm_name, "FAILED_CREATE_VM")
