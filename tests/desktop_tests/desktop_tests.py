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
        self.vm = VboxMachine(self.vm_name, cores=self.vm_cores, memory=self.vm_memory)
        self.vm_data = None
        self.password_cache = None

        self._initialize_report()
        self._initialize_run_script()

    @retry(max_attempts=2, exception_type=VirtualMachinException)
    def run(self, headless: bool = True):
        try:
            self.vm.run(headless=headless)
            self.vm_data = self.vm.data
            self._initialize_linux_demon()
            password = self._get_password(self.vm.data.local_dir)
            self.run_script_on_vm(password)

        except VirtualMachinException:
            self._handle_vm_creation_failure()

        except KeyboardInterrupt:
            print("[bold red]|WARNING| Interruption by the user")
            raise

        finally:
            self.vm.stop()

    def run_script_on_vm(self, user_password: str = None):
        self._clean_known_hosts(self.vm_data.ip)
        server = self._get_server()

        with Ssh(server) as ssh, Sftp(server, ssh.connection) as sftp:
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

            if self._download_and_check_report(connect):
                self.report.insert_vm_name(self.vm_name)

    def _download_and_check_report(self, connect):
        if connect.download_report(self.data.title, self.data.version, self.report.dir):
            if self.report.column_is_empty("Os"):
                raise FileNotFoundError
            return True
        else:
            print(f"[red]|ERROR| Can't download report from {self.vm_data.name}.")
            self.report.write(self.data.version, self.vm_data.name, "REPORT_NOT_EXISTS")
            return False

    def _get_server(self) -> ServerData:
        return ServerData(
            self.vm_data.ip,
            self.vm_data.user,
            self._get_password(self.vm_data.local_dir),
            self.vm_data.name
        )

    def _initialize_report(self):
        report_file = join(self.data.report_dir, self.vm_name, f"{self.data.version}_{self.data.title}_report.csv")
        Dir.create(dirname(report_file), stdout=False)
        self.report = DesktopReport(report_file)

    def _initialize_run_script(self):
        self.run_script = RunScript(
            version=self.data.version,
            old_version=self.data.update_from,
            telegram=self.data.telegram,
            custom_config_path=self.data.custom_config_mode,
            desktop_testing_url=self.data.desktop_testing_url,
            branch=self.data.branch
        )

    def _initialize_linux_demon(self):
        self.linux_demon = LinuxScriptDemon(
            exec_script_path=self.run_script.save_path,
            user=self.vm_data.user,
            name=self.paths.remote.my_service_name
        )

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
