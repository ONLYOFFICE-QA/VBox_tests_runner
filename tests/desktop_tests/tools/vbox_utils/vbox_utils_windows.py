# -*- coding: utf-8 -*-
import time
from subprocess import CompletedProcess
from typing import Optional

from VBoxWrapper import FileUtils, VirtualMachine
from rich import print

from tests.desktop_tests.tools import TestData
from tests.desktop_tests.tools.paths import Paths
from tests.desktop_tests.tools.run_script import RunScript


class VboxUtilsWindows:

    def __init__(
            self,
            vm: VirtualMachine,
            user_name: str,
            password: str,
            test_data: TestData,
            paths: Paths,
    ):
        self.file = FileUtils(vm_id=vm, username=user_name, password=password)
        self.data = test_data
        self.paths = paths
        self.shell = self._get_shell()

    def upload_test_files(self, script: RunScript):
        self.create_test_dirs()
        for local, remote in self.get_upload_files(script=script):
            self._upload(local, remote)

    def create_test_dirs(self, try_num: int = 10, interval: int = 1):
        commands = [
            f'mkdir {self.paths.remote.script_dir}',
            f'mkdir {self.paths.remote.tg_dir}'
        ]

        for cmd in commands:
            print(f"[green]|INFO|{self.file.vm.name}| Creating test dir: [cyan]{cmd}[/]")
            self._create_dir(cmd, try_num=try_num, interval=interval)

    def run_script_on_vm(self):
        server_info = f"{self.file.vm.name}|{self.file.vm.network.get_ip()}"
        line = f"{'-' * 90}"
        print(f"[bold cyan]{line}\n|INFO|{server_info}| Waiting for execution script on VM\n{line}")

        out = self._run_cmd(self._get_run_script_cmd(), status_bar=self.data.status_bar, stdout=self.data.status_bar)
        print(
            f"[cyan]{line}\n|INFO|{self.file.vm.name}|Script execution log:\n{line}\n"
            f"{out.stdout}\n Exit Code: {out.returncode}\n{line}"
        )

    def download_report(self, product_title: str, version: str, report_dir: str):
        remote_report_dir = f"{self.paths.remote.report_dir}/{product_title}/{version}"
        out = self.file.copy_from(remote_report_dir, report_dir)

        if out.stderr and 'no such file or directory' in out.stderr.lower():
            return False

        return True

    def _run_cmd(self, cmd: str, status_bar: bool = False, stdout: bool = True) -> CompletedProcess:
        return self.file.run_cmd(command=cmd, status_bar=status_bar, stdout=stdout, shell=self.shell)

    def _upload(self, local_path: str, remote_path: str, try_num: int = 10, interval: int = 1) -> None:
        print(f"[green]|INFO|{self.file.vm.name}| Upload file [cyan]{local_path}[/] to [cyan]{remote_path}[/]")
        while try_num > 0:
            out = self.file.copy_to(local_path=local_path, remote_path=remote_path)

            if out.returncode == 0:
                break

            if 'File copy failed' not in out.stderr:
                break

            time.sleep(interval)
            try_num -= 1

    def _create_dir(self, command: str, try_num: int = 10, interval: int = 1):
        while try_num > 0:
            out = self._run_cmd(command, stdout=False)

            if out.returncode == 0:
                break

            if 'already exists' in out.stderr:
                break

            time.sleep(interval)
            try_num -= 1

    def _get_shell(self) -> Optional[str]:
        if self.paths.remote.run_script_name.endswith(".bat"):
            return "cmd.exe"

        if self.paths.remote.run_script_name.endswith(".ps1"):
            return "powershell.exe"

        return None

    def _get_run_script_cmd(self):
        if self.paths.remote.run_script_name.endswith(".bat"):
            return self.paths.remote.script_path

        if self.paths.remote.run_script_name.endswith(".ps1"):
            return f"-ExecutionPolicy Bypass -File '{self.paths.remote.script_path}'"

        raise ValueError("Unsupported script type.")

    def get_upload_files(self, script: RunScript) -> list:
        return [
            (self.data.token_file, self.paths.remote.tg_token_file),
            (self.data.chat_id_file, self.paths.remote.tg_chat_id_file),
            (script.create(), self.paths.remote.script_path),
            (self.paths.local.proxy_config, self.paths.remote.proxy_config_file),
            (self.data.config_path, self.paths.remote.custom_config_path),
            (self.paths.local.lic_file, self.paths.remote.lic_file),
        ]

