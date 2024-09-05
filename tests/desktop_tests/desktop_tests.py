# -*- coding: utf-8 -*-
import signal
import time
from os.path import join, dirname, isfile
from typing import Optional

from host_tools.utils import Dir

from VBoxWrapper import VirtualMachine, VirtualMachinException
from frameworks.console import MyConsole
from frameworks.decorators import retry
from host_tools import File
from ssh_wrapper import Ssh, Sftp, SshException, ServerData
from tests.desktop_tests.data import LinuxData
from .tools.linux_script_demon import LinuxScriptDemon
from .tools.paths import Paths
from .tools.run_script import RunScript
from .tools.test_data import TestData
from tests.desktop_tests.tools.VboxMachine import VboxMachine
from tests.desktop_tests.tools.desktop_report import DesktopReport
from tests.desktop_tests.tools.ssh_connection import SSHConnection


console = MyConsole().console
print = console.print


def handle_interrupt(signum, frame):
    raise KeyboardInterrupt


signal.signal(signal.SIGINT, handle_interrupt)


class DesktopTest:
    def __init__(self, vm_name: str, test_data: TestData, vm_cpus: int = 4, vm_memory: int = 4096):
        self.paths = Paths()
        self.vm_cores = vm_cpus
        self.vm_memory = vm_memory
        self.data = test_data
        self.vm_name = vm_name
        self.vm_data = None
        Dir.create(self.data.report_dir, stdout=False)

        self.report = DesktopReport(
            join(self.data.report_dir, self.vm_name, f"{self.data.version}_{self.data.title}_report.csv")
        )

        self.run_script = RunScript(
            version=self.data.version,
            old_version=self.data.update_from,
            telegram=self.data.telegram,
            custom_config_path=self.data.custom_config_mode,
            desktop_testing_url=self.data.desktop_testing_url,
            branch=self.data.branch
        )

        self.linux_demon = LinuxScriptDemon(
            exec_script_path=self.run_script.save_path,
            user='root',
            name=self.paths.remote.my_service_name
        )


    @retry(max_attempts=2, exception_type=VirtualMachinException)
    def run(self, headless: bool = True):
        vm = VboxMachine(self.vm_name, cores=self.vm_cores, memory=self.vm_memory)
        try:
            vm.run(headless=headless)
            self.vm_data = vm.data
            self.linux_demon.name = self.vm_data.user
            self.run_script_on_vm(self._get_password(vm.data.local_dir))

        except VirtualMachinException:
            print(f"[bold red]|ERROR|{self.vm_name}| Failed to create  a virtual machine")
            self.report.write(self.data.version, self.vm_name, "FAILED_CREATE_VM")

        except KeyboardInterrupt:
            print("[bold red]|WARNING| Interruption by the user")
            raise

        finally:
            vm.stop()

    def run_script_on_vm(self, user_password: str = None):
        self._clean_know_hosts(self.vm_data.ip)
        _server = self._get_server()
        with Ssh(_server) as ssh, Sftp(_server, ssh.connection) as sftp:
            connect = SSHConnection(ssh=ssh, sftp=sftp)
            connect.change_vm_service_dir_access(self.vm_data.user)

            connect.upload_test_files(
                tg_token=self.data.tg_token,
                tg_chat_id=self.data.tg_chat_id,
                script=self.run_script.create(),
                service=self.linux_demon.create()
            )

            connect.start_my_service(self.linux_demon.start_demon_commands())
            connect.wait_execute_service()

            if connect.download_report(self.data.title, self.data.version, self.report.dir):
                if self.report.column_is_empty("Os"):
                    raise FileNotFoundError
                self.report.insert_vm_name(self.vm_name)
            else:
                print(f"[red]|ERROR| Can't download report from {self.vm_data.name}.")
                self.report.write(self.data.version, self.vm_data.name, "REPORT_NOT_EXISTS")


    def _get_server(self) -> ServerData:
        return ServerData(
            self.vm_data.ip,
            self.vm_data.user,
            self._get_password(self.vm_data.local_dir),
            self.vm_data.name
        )

    def _clean_know_hosts(self, ip: str):
        with open(self.paths.local.know_hosts, 'r') as file:
            filtered_lines = [line for line in file.readlines() if not line.startswith(ip)]
        with open(self.paths.local.know_hosts, 'w') as file:
            file.writelines(filtered_lines)

    def _get_password(self, vm_dir: str) -> Optional[str]:
        try:
            password_file = join(dirname(vm_dir), 'password')
            password = File.read(password_file).strip() if isfile(password_file) else None
            return password if password else self.data.config.get('password', None)
        except (TypeError, FileNotFoundError):
            return self.data.config.get('password', None)
