# -*- coding: utf-8 -*-
import re
import time
from contextlib import nullcontext
from os.path import join
from subprocess import CompletedProcess
from rich import print

from VBoxWrapper import VirtualMachine
from host_tools import File
from rich.console import Console

from .schtasks_command import SchtasksCommand
from .vbox_utils_windows import VboxUtilsWindows

from ...paths import Paths
from ...test_data import TestData


class VboxUtilsVista(VboxUtilsWindows):
    task_name = "RunScript"

    def __init__(
            self,
            vm: VirtualMachine,
            user_name: str,
            password: str,
            test_data: TestData,
            paths: Paths,
    ):
        super().__init__(vm=vm, user_name=user_name, password=password, test_data=test_data, paths=paths)
        self.user = user_name
        self.log_file = fr"C:\Users\{self.user}\log.txt"
        self.tmp_log_file = join(File.unique_name(self.paths.local.tmp_dir, 'txt'))
        self.schtasks = SchtasksCommand(task_name=self.task_name)

    def upload_test_files(self,  upload_files: list[(str, str)]) -> None:
        self.create_test_dirs()
        for local, remote in upload_files:
            self._upload(local, remote)
            time.sleep(1)

    def run_script_on_vm(self) -> None:
        self.create_schtasks()
        self.run_schtasks()
        self.wait_until_running()

    def wait_until_running(self, task_name: str = None, timeout: int = 10) -> None:
        server_info = f"{self.file.vm.name}|{self.file.vm.network.get_ip()}"
        print(f"[bold cyan]{'-' * 90}\n|INFO|{server_info}| Waiting for execution script on VM\n{'-' * 90}")
        msg = f'[cyan]|INFO|{server_info}| Waiting for execution script'

        with Console().status(msg) if self.data.status_bar else nullcontext() as status:
            while self._is_task_running():
                time.sleep(timeout)
                if self.data.status_bar:
                    self._update_status_bar(status)

        self.file.copy_from(self.log_file, self.tmp_log_file)
        print(f'[cyan]|INFO|{File.read(self.tmp_log_file)}')

    def get_schtasks_status(self) -> str:
        return self._find_status(self._retry_cmd(self.schtasks.status()).stdout)

    def create_schtasks(self) -> None:
        print(f"[green]|INFO| Create task: {self.task_name}")
        self._retry_cmd(self.schtasks.create(command=f"{self.paths.remote.script_path} >> {self.log_file} 2>&1"))

    def run_schtasks(self) -> None:
        print(f"[green]|INFO| Run task: {self.task_name}")
        self._retry_cmd(self.schtasks.run())

    def _update_status_bar(self, status: Console().status) -> None:

        def tail_lines(lines: list, max_stdout_lines: int = 20) -> list:
            return lines[-max_stdout_lines:]

        self.file.copy_from(self.log_file, self.tmp_log_file)
        recent_lines = ''.join(tail_lines(self._read_lines(self.tmp_log_file)))
        status.update(f"[cyan]{recent_lines}")

    def _is_task_running(self) -> bool:
        return self.get_schtasks_status().lower() == "running"

    @staticmethod
    def _read_lines(file_path, mode='r') -> list:
        with open(file_path, mode) as file:
            return file.readlines()

    def _retry_cmd(self, cmd: str, max_retries: int = 20, delay: int = 1) -> CompletedProcess:
        for _ in range(max_retries):
            out = self._run_cmd(cmd, stdout=False, status_bar=False)
            if out.returncode != 0 and not out.stderr:
                time.sleep(delay)
            else:
                return out

        raise RuntimeError("Command execution failed after retries.")

    def _run_cmd(self, cmd: str, status_bar: bool = False, stdout: bool = True) -> CompletedProcess:
        return self.file.run_cmd(command=cmd, status_bar=status_bar, stdout=stdout, shell='cmd.exe')

    @staticmethod
    def _find_status(stdout: str) -> str:
        match = re.search(r'Status:\s+(.*?)\n', stdout)
        return match.group(1).strip() if match else ''
