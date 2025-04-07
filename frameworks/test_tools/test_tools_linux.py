# -*- coding: utf-8 -*-
from os.path import dirname

from VBoxWrapper import VirtualMachinException
from ssh_wrapper import Ssh, Sftp, ServerData

from frameworks.decorators import retry, vm_data_created

from .test_tools import TestTools, VboxMachine
from .ssh_connection import SSHConnection, LinuxScriptDemon
from ..TestData import TestData


class TestToolsLinux(TestTools):

    def __init__(self,  vm: VboxMachine, test_data: TestData):
        super().__init__(vm=vm, test_data=test_data)
        self.remote_report_path = None
        self.paths = None
        self.report = None
        self.connect = None

    @retry(max_attempts=2, exception_type=VirtualMachinException)
    def run_vm(self, headless: bool = True) -> None:
        self.vm.run(headless=headless, status_bar=self.data.status_bar)

    def initialize_libs(self, report, paths, remote_report_path: str) -> None:
        self.report = report
        self.paths = paths
        self.remote_report_path = remote_report_path
        self._initialize_linux_demon()

    def run_test_on_vm(self, upload_files: list, create_test_dir: list):
        self._clean_known_hosts(self.vm.data.ip)
        server = self._get_server()

        with Ssh(server) as ssh, Sftp(server, ssh.connection) as sftp:
            self.connect = SSHConnection(ssh=ssh, sftp=sftp)
            self.connect.change_vm_service_dir_access(self.vm.data.user)
            self.connect.create_test_dirs(self._get_create_dir(create_test_dir))
            self.connect.upload_test_files(self._get_linux_upload_files(upload_files))
            self.connect.start_my_service(self.linux_demon.start_demon_commands())
            self.connect.wait_execute_service(status_bar=self.data.status_bar)
            self.download_report()

    def download_report(self):
        if (
                self.connect.download_report(self.remote_report_path, self.report.dir)
                and not self.report.column_is_empty("Os")
        ):
            self.report.insert_vm_name(self.vm_name)
        else:
            print(f"[red]|ERROR| Can't download report from {self.vm.data.name}.")

    def _get_server(self) -> ServerData:
        return ServerData(
            ip=self.vm.data.ip,
            username=self.vm.data.user,
            password=self._get_password(self.vm.data.local_dir),
            custom_name=self.vm.data.name
        )

    @vm_data_created
    def _initialize_linux_demon(self):
        self.linux_demon = LinuxScriptDemon(
            exec_script_path=self.paths.remote.script_path,
            user=self.vm.data.user,
            name=SSHConnection.my_service_name
        )

    def _clean_known_hosts(self, ip: str):
        with open(self.paths.local.known_hosts, 'r') as file:
            filtered_lines = [line for line in file if not line.startswith(ip)]
        with open(self.paths.local.known_hosts, 'w') as file:
            file.writelines(filtered_lines)

    def _get_linux_upload_files(self, upload_files: list) -> list:
        return upload_files + [
            (self.linux_demon.create(), SSHConnection.my_service_path),
            (self.paths.local.github_token, self.paths.remote.github_token_path)
        ]

    def _get_create_dir(self, create_dirs: list) -> list:
        return create_dirs + [
            self.paths.remote.github_token_dir
        ]
