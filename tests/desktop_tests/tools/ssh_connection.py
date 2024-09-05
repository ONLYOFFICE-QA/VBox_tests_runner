# -*- coding: utf-8 -*-
import contextlib
import time

from frameworks.console import MyConsole
from tests.desktop_tests.tools.paths import Paths
from tempfile import gettempdir
from ssh_wrapper import Ssh, Sftp, SshException

console = MyConsole().console
print = console.print

class SSHConnection:

    def __init__(self, ssh: Ssh, sftp: Sftp):
        self.ssh = ssh
        self.sftp = sftp
        self.path = Paths()
        self.tmp_dir = gettempdir()

    def upload_test_files(self, tg_token, tg_chat_id, service, script):
        self.create_test_dirs()
        self.upload(tg_token, self.path.remote.tg_token_file)
        self.upload(tg_chat_id, self.path.remote.tg_chat_id_file)
        self.upload(self.path.local.proxy_config_path, self.path.remote.proxy_config_file)
        self.upload(service, self.path.remote.my_service_path)
        self.upload(script, self.path.remote.script_path)
        self.upload(self.path.local.config_path, self.path.remote.custom_config_path)
        self.upload(self.path.local.lic_file, self.path.remote.lic_file)

    def upload(self, local_path: str, remote_path: str):
        self.sftp.upload_file(local_path=local_path, remote_path=remote_path, stdout=True)

    def create_test_dirs(self):
        for cmd in [f'mkdir {self.path.remote.script_dir}', f'mkdir {self.path.remote.tg_dir}']:
            self.exec_cmd(cmd)

    def change_vm_service_dir_access(self, user_name: str):
        for cmd in [
            f'sudo chown {user_name}:{user_name} {self.path.remote.services_dir}',
            f'sudo chmod u+w {self.path.remote.services_dir}'
        ]:
            self.exec_cmd(cmd)

    def start_my_service(self, start_service_cmd: list):
        self.exec_cmd(f"sudo rm /var/log/journal/*/*.journal")  # clean journal
        for cmd in start_service_cmd:
            self.exec_cmd(cmd)

    def wait_execute_service(self, timeout: int = None, status_bar: bool = False):
        service_name = self.path.remote.my_service_name
        server_info = f"{self.ssh.server.custom_name}|{self.ssh.server.ip}"
        msg = f"[cyan]|INFO|{server_info}| Waiting for execution of {service_name}"

        print(f"[bold cyan]{'-' * 90}\n|INFO|{server_info}| Waiting for script execution on VM\n{'-' * 90}")

        with console.status(msg) if status_bar else contextlib.nullcontext() as status:
            print(msg) if not status_bar else None
            start_time = time.time()
            while self.exec_cmd(f'systemctl is-active {service_name}', stderr=True).stdout == 'active':
                if status_bar:
                    status.update(f"{msg}\n{self._get_my_service_log()}")

                time.sleep(0.5)

                if isinstance(timeout, int) and (time.time() - start_time) >= timeout:
                    raise SshException(
                        f'[bold red]|WARNING|{server_info}| The service {service_name} waiting time has expired.'
                    )
        print(
            f"[blue]{'-' * 90}\n|INFO|{server_info}| Service {service_name} log:\n{'-' * 90}\n\n"
            f"{self._get_my_service_log(1000, stdout=False)}\n{'-' * 90}"
        )

    def _get_my_service_log(self, line_num: str | int = 20, stdout: bool = True, stderr: bool = True) -> str:
        command = f'sudo journalctl -n {line_num} -u {self.path.remote.my_service_name}'
        return self.exec_cmd(command, stdout=stdout, stderr=stderr).stdout

    def download_report(self, product_title: str, version: str, report_dir: str):
        try:
            remote_report_dir = f"{self.path.remote.report_dir}/{product_title}/{version}"
            self.sftp.download_dir(remote_report_dir, report_dir)
            return True
        except (FileExistsError, FileNotFoundError) as e:
            print(e)
            return False

    def exec_cmd(self,cmd, stderr=False, stdout=False):
        return self.ssh.exec_command(cmd, stderr=stderr, stdout=stdout)
