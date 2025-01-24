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
from ...run_script import RunScript
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

    def upload_test_files(self, script: RunScript) -> None:
        self.create_test_dirs()
        for local, remote in self.get_upload_files(script=script):
            self._upload(local, remote)
            time.sleep(1)

    def run_script_on_vm(self) -> None:
        self.create_schtasks()
        self.run_schtasks()
        self.wait_until_running()

    def wait_until_running(self, task_name: str = None, timeout: int = 10) -> None:
        server_info = f"{self.file.vm.name}|{self.file.vm.network.get_ip()}"
        line = f"{'-' * 90}"
        msg = f'[cyan]|INFO|{server_info}| Waiting for execution script'
        print(f"[bold cyan]{line}\n|INFO|{server_info}| Waiting for execution script on VM\n{line}")

        with Console().status(msg) if self.data.status_bar else nullcontext() as status:
            while self.get_schtasks_status(task_name=task_name).lower() == "running":
                time.sleep(timeout)
                if self.data.status_bar:
                    self.file.copy_from(self.log_file, self.tmp_log_file)
                    recent_lines = ''.join(self.tail_lines(self._read_lines(self.tmp_log_file)))
                    status.update(f"[cyan]{recent_lines}")

        self.file.copy_from(self.log_file, self.tmp_log_file)
        print(f'[cyan]|INFO|{File.read(self.tmp_log_file)}')

    def get_schtasks_status(self, task_name: str = None) -> str:
        cmd = self.schtasks.status()
        out = self._run_cmd(cmd, stdout=False, status_bar=False)

        while out.returncode != 0 and not out.stderr:
            time.sleep(1)
            out = self._run_cmd(cmd, stdout=False, status_bar=False)

        return self._find_status(out.stdout)

    @staticmethod
    def tail_lines(lines: list, max_stdout_lines: int = 20) -> list:
        """Keeps only the last `max_lines` from the given list of lines."""
        return lines[-max_stdout_lines:]

    def _run_cmd(self, cmd: str, status_bar: bool = False, stdout: bool = True) -> CompletedProcess:
        return self.file.run_cmd(command=cmd, status_bar=status_bar, stdout=stdout, shell='cmd.exe')

    @staticmethod
    def _find_status(stdout: str) -> str:
        match = re.search(r'Status:\s+(.*?)\n', stdout)
        return match.group(1).strip() if match else ''

    def create_schtasks(self) -> None:
        print(f"[green]|INFO| Create task: {self.task_name}")
        cmd = self.schtasks.create(f'cmd.exe /c "{self.paths.remote.script_path} >> {self.log_file} 2>&1"')
        out = self._run_cmd(cmd, status_bar=False, stdout=True)
        while out.returncode != 0 and not out.stderr:
            time.sleep(1)
            out = self._run_cmd(cmd, status_bar=False, stdout=True)

    def run_schtasks(self) -> None:
        print(f"[green]|INFO| Run task: {self.task_name}")
        cmd = self.schtasks.run()
        out = self._run_cmd(cmd, status_bar=False, stdout=True)
        while out.returncode != 0 and not out.stderr or 'SUCCESS' not in out.stdout.upper():
            time.sleep(1)
            out = self._run_cmd(cmd, status_bar=False, stdout=True)

    @staticmethod
    def _read_lines(file_path, mode='r') -> list:
        with open(file_path, mode) as file:
            return file.readlines()
