# -*- coding: utf-8 -*-
from VBoxWrapper import VirtualMachinException
from ssh_wrapper import Ssh, Sftp, ServerData

from frameworks.decorators import retry, vm_data_created
from .test_tools import TestTools, TestData, VboxMachine
from ..linux_script_demon import LinuxScriptDemon
from ..ssh_connection import SSHConnection


class TestToolsLinux(TestTools):

    def __init__(self,  vm: VboxMachine, test_data: TestData):
        super().__init__(vm=vm, test_data=test_data)

    @retry(max_attempts=2, exception_type=VirtualMachinException)
    def run_vm(self, headless: bool = True) -> None:
        self.vm.run(headless=headless, status_bar=self.data.status_bar)
        self._initialize_paths()
        self._initialize_run_script()
        self._initialize_linux_demon()

    def run_test_on_vm(self):
        self._clean_known_hosts(self.vm.data.ip)
        server = self._get_server()

        with Ssh(server) as ssh, Sftp(server, ssh.connection) as sftp:
            connect = SSHConnection(ssh=ssh, sftp=sftp, test_data=self.data, paths=self.paths)
            connect.change_vm_service_dir_access(self.vm.data.user)
            connect.upload_test_files(self.linux_demon, self.run_script)
            connect.start_my_service(self.linux_demon.start_demon_commands())
            connect.wait_execute_service(status_bar=self.data.status_bar)

            if self.download_and_check_report(connect):
                self.report.insert_vm_name(self.vm_name)

    def download_and_check_report(self, connect: SSHConnection):
        if (
                connect.download_report(self.data.title, self.data.version, self.report.dir)
                and not self.report.column_is_empty("Os")
        ):
            return True

        print(f"[red]|ERROR| Can't download report from {self.vm.data.name}.")
        return False

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
            name=self.paths.remote.my_service_name
        )

    def _clean_known_hosts(self, ip: str):
        with open(self.paths.local.know_hosts, 'r') as file:
            filtered_lines = [line for line in file if not line.startswith(ip)]
        with open(self.paths.local.know_hosts, 'w') as file:
            file.writelines(filtered_lines)
