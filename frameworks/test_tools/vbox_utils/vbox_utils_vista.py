# -*- coding: utf-8 -*-
import re
import time
from contextlib import nullcontext
from os.path import join, dirname
from subprocess import CompletedProcess

from host_tools.utils import Dir
from rich import print

from VBoxWrapper import VirtualMachine
from host_tools import File
from rich.console import Console
from tempfile import gettempdir

from .schtasks_command import SchtasksCommand
from .vbox_utils_windows import VboxUtilsWindows

from frameworks.test_data import TestData, Paths


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
        self.tmp_log_file = join(File.unique_name(gettempdir(), 'txt'))
        self.schtasks = SchtasksCommand(task_name=self.task_name)
        self.shell = 'cmd.exe'

    def upload_test_files(self,  upload_files: list[(str, str)]) -> None:
        for local, remote in upload_files:
            self._upload(local, remote)
            time.sleep(1)

    def run_script_on_vm(self, status_bar: bool) -> None:
        self.create_schtasks()
        self.run_schtasks()
        self.wait_until_running(status_bar=status_bar)

    def wait_until_running(self, status_bar: bool, timeout: int = 10) -> None:
        server_info = f"{self.file.vm.name}|{self.file.vm.network.get_ip()}"
        print(f"[bold cyan]{'-' * 90}\n|INFO|{server_info}| Waiting for execution script on VM\n{'-' * 90}")
        msg = f'[cyan]|INFO|{server_info}| Waiting for execution script'

        with Console().status(msg) if status_bar else nullcontext() as status:
            while self._is_task_running():
                time.sleep(timeout)
                if status_bar:
                    self._update_status_bar(status)

        self._download_log_file()
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

        self._download_log_file()
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

    @staticmethod
    def _find_status(stdout: str) -> str:
        match = re.search(r'Status:\s+(.*?)\n', stdout)
        return match.group(1).strip() if match else ''

    def _download_log_file(self) -> None:
        Dir.create(dirname(self.tmp_log_file), stdout=False)
        self.file.copy_from(self.log_file, self.tmp_log_file)
