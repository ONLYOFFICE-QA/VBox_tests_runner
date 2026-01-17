# -*- coding: utf-8 -*-
import contextlib
import time

from tempfile import gettempdir
from ssh_wrapper import Ssh, Sftp, SshException

from frameworks.console import MyConsole
from posixpath import join

console = MyConsole().console
print = console.print

class SSHConnection:
    my_service_name = 'myscript.service'
    services_dir = join('/etc', 'systemd', 'system')
    my_service_path = join(services_dir, my_service_name)

    def __init__(self, ssh: Ssh, sftp: Sftp):
        self.ssh = ssh
        self.sftp = sftp
        self.tmp_dir = gettempdir()

    def upload_test_files(self, upload_files: list[(str, str)]):
        for local, remote in upload_files:
            self.upload(local, remote)

    def upload(self, local_path: str, remote_path: str):
        self.sftp.upload_file(local=local_path, remote=remote_path, stdout=True)
        time.sleep(1)

    def create_test_dirs(self, create_dirs: list) -> None:
        for test_dir in create_dirs:
            self.exec_cmd(f"mkdir {test_dir}")

    def change_vm_service_dir_access(self, user_name: str):
        for cmd in [
            f'sudo chown {user_name}:{user_name} {self.services_dir}',
            f'sudo chmod u+w {self.services_dir}'
        ]:
            self.exec_cmd(cmd)

    def start_my_service(self, start_service_cmd: list):
        self.clean_log_journal()
        for cmd in start_service_cmd:
            self.exec_cmd(cmd)

    def clean_log_journal(self):
        self.exec_cmd("sudo rm /var/log/journal/*/*.journal")

    def wait_execute_service(self, timeout: int = None, status_bar: bool = False, interval: int = 1):
        service_name = self.my_service_name
        server_info = f"{self.ssh.server.custom_name}|{self.ssh.server.ip}"
        msg = f"[cyan]|INFO|{server_info}| Waiting for execution of {service_name}"

        print(f"[bold cyan]{'-' * 90}\n|INFO|{server_info}| Waiting for script execution on VM with interval {interval} seconds\n{'-' * 90}")

        with console.status(msg) if status_bar else contextlib.nullcontext() as status:
            print(msg) if not status_bar else None
            start_time = time.time()
            while self.service_is_active(service_name=service_name):
                status.update(f"{msg}\n{self.get_my_service_log(stdout=False)}") if status_bar else None
                time.sleep(interval)

                if isinstance(timeout, int) and (time.time() - start_time) >= timeout:
                    raise SshException(
                        f'[bold red]|WARNING|{server_info}| The service {service_name} waiting time has expired.'
                    )
        print(
            f"[blue]{'-' * 90}\n|INFO|{server_info}| Service {service_name} log:\n{'-' * 90}\n\n"
            f"{self.get_my_service_log(1000, stdout=False)}\n{'-' * 90}"
        )

    def service_is_active(self, service_name: str) -> bool:
        return self.exec_cmd(f'systemctl is-active {service_name}', stderr=True).stdout.lower() == 'active'

    def get_my_service_log(self, line_num: str | int = 20, stdout: bool = True, stderr: bool = True) -> str:
        command = f'sudo journalctl -n {line_num} -u {self.my_service_name}'
        return self.exec_cmd(command, stdout=stdout, stderr=stderr).stdout

    def download_report(self, path_from: str, save_path: str):
        try:
            self.sftp.download_dir(path_from, save_path)
            return True
        except (FileExistsError, FileNotFoundError) as e:
            print(e)
            return False

    def exec_cmd(self,cmd, stderr=False, stdout=False):
        return self.ssh.exec_command(cmd, stderr=stderr, stdout=stdout)
