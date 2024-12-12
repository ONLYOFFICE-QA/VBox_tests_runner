# -*- coding: utf-8 -*-
from VBoxWrapper import FileUtils, VirtualMachine
from rich import print

from tests.desktop_tests.tools import TestData
from tests.desktop_tests.tools.paths import Paths
from .run_script import RunScript


class VboxUtils:

    def __init__(self, vm_id: VirtualMachine, user_name: str, password: str, test_data: TestData, paths: Paths):
        self.file = FileUtils(vm_id=vm_id, username=user_name, password=password)
        self.data = test_data
        self.paths = paths

    def upload_test_files(self, script: RunScript):
        self.create_test_dirs()
        self._upload(self.data.token_file, self.paths.remote.tg_token_file)
        self._upload(self.data.chat_id_file, self.paths.remote.tg_chat_id_file)
        self._upload(script.create(), self.paths.remote.script_path)
        self._upload(self.paths.local.proxy_config, self.paths.remote.proxy_config_file)
        self._upload(self.data.config_path, self.paths.remote.custom_config_path)
        self._upload(self.paths.local.lic_file, self.paths.remote.lic_file)

    def create_test_dirs(self):
        for cmd in [f'mkdir {self.paths.remote.script_dir}', f'mkdir {self.paths.remote.tg_dir}']:
            self.file.run_cmd(cmd, stdout=False)

    def run_script_on_vm(self):
        cmd = f"-ExecutionPolicy Bypass -File '{self.paths.remote.script_path}'"
        server_info = f"{self.file.vm.name}|{self.file.vm.network.get_ip()}"
        line = f"{'-' * 90}"
        print(f"[cyan]{line}\n|INFO|{server_info}| Waiting for execution script on VM\n{line}")

        process = self.file.run_cmd(cmd, status_bar=self.data.status_bar, stdout=self.data.status_bar)
        print(
            f"[cyan]{line}\n|INFO|{self.file.vm.name}|Script execution log:\n{line}\n"
            f"{process.stdout}\n Exit Code: {process.returncode}\n{line}"
        )

    def download_report(self, product_title: str, version: str, report_dir: str):
        try:
            remote_report_dir = f"{self.paths.remote.report_dir}/{product_title}/{version}"
            self.file.copy_from(remote_report_dir, report_dir)
            return True
        except (FileExistsError, FileNotFoundError) as e:
            print(e)
            return False

    def _upload(self, local_path: str, remote_path: str) -> None:
        print(f"[green]|INFO| Upload file [cyan]{local_path}[/] to [cyan]{remote_path}[/]")
        self.file.copy_to(local_path=local_path, remote_path=remote_path)
