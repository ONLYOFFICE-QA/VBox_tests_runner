# -*- coding: utf-8 -*-
import time
from subprocess import CompletedProcess
from typing import Optional

from VBoxWrapper import FileUtils, VirtualMachine
from rich import print

from tests.desktop_tests.tools import TestData
from tests.desktop_tests.tools.paths import Paths


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

    def upload_test_files(self, upload_files: list[(str, str)]):
        for local, remote in upload_files:
            self._upload(local, remote)

    def create_test_dirs(self, test_dirs: list, try_num: int = 10, interval: int = 1):
        for test_dir in test_dirs:
            print(f"[green]|INFO|{self.file.vm.name}| Creating test dir: [cyan]{cmd}[/]")
            self._create_dir(f"mkdir {test_dir}", try_num=try_num, interval=interval)

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
            out = self._run_cmd(command, stdout=False, stderr=False)

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

    def _run_cmd(
            self,
            cmd: str,
            status_bar: bool = False,
            stdout: bool = True,
            stderr: bool = True
    ) -> CompletedProcess:
        return self.file.run_cmd(command=cmd, status_bar=status_bar, stdout=stdout, stderr=stderr, shell=self.shell)
