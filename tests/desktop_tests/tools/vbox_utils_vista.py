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

from .paths import Paths
from .run_script import RunScript
from .vbox_utils import VboxUtils
from tests.desktop_tests.tools import TestData


class VboxUtilsVista(VboxUtils):
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

    def upload_test_files(self, script: RunScript):
        time.sleep(30)
        self.create_test_dirs()
        for local, remote in self.get_upload_files(script=script):
            self._upload(local, remote)
            time.sleep(1)

    def run_script_on_vm(self):
        self.create_schtasks()
        self.run_schtasks()
        self.wait_until_running()

    def wait_until_running(self, task_name: str = None, time_out: int = 10):
        self.data.status_bar = True
        with Console().status(f'[cyan]Exec command:') if self.data.status_bar else nullcontext() as status:
            while self.get_schtasks_status(task_name=task_name).lower() == "running":
                time.sleep(time_out)
                if self.data.status_bar:
                    self.file.copy_from(self.log_file, self.tmp_log_file)
                    recent_lines = ''.join(self.tail_lines(self._read_lines(self.tmp_log_file)))
                    status.update(f"[cyan]{recent_lines}")

        print(f'[cyan]|INFO|{File.read(self.tmp_log_file)}')

    def get_schtasks_status(self, task_name: str = None) -> str:
        cmd = f'schtasks /query /tn "{task_name or self.task_name}" /v /fo LIST'
        out = self._run_cmd(cmd, stdout=False, status_bar=False)

        while out.returncode != 0 and not out.stderr:
            time.sleep(1)
            out = self._run_cmd(cmd, stdout=False, status_bar=False)

        return self._find_status(out.stdout)

    @staticmethod
    def tail_lines(lines: list, max_stdout_lines: int = 20) -> list:
        """Keeps only the last `max_lines` from the given list of lines."""
        return lines[-max_stdout_lines:]

    def _get_create_schtasks_cmd(self) -> str:
        return fr'schtasks /create /tn "{self.task_name}" /tr "cmd.exe /c \"C:\Users\{self.user}\script.bat >> C:\Users\{self.user}\log.txt 2>&1\"" /sc onstart /rl highest'

    def _get_run_task_cmd(self) -> str:
        return f'schtasks /run /tn "{self.task_name}"'

    def _run_cmd(self, cmd: str, status_bar: bool = False, stdout: bool = True) -> CompletedProcess:
        return self.file.run_cmd(command=cmd, status_bar=status_bar, stdout=stdout, shell='cmd.exe')

    @staticmethod
    def _find_status(stdout: str) -> str:
        match = re.search(r'Status:\s+(.*?)\n', stdout)
        return match.group(1).strip() if match else ''

    def create_schtasks(self) -> None:
        print(f"[green]|INFO| Create task: {self.task_name}")
        cmd = self._get_create_schtasks_cmd()
        out = self._run_cmd(cmd, status_bar=False, stdout=True)
        while out.returncode != 0 and not out.stderr:
            time.sleep(1)
            out = self._run_cmd(cmd, status_bar=False, stdout=True)

    def run_schtasks(self):
        print(f"[green]|INFO| Run task: {self.task_name}")
        cmd = self._get_run_task_cmd()
        out = self._run_cmd(cmd, status_bar=False, stdout=True)
        while out.returncode != 0 and not out.stderr or 'SUCCESS' not in out.stdout.upper():
            time.sleep(1)
            out = self._run_cmd(cmd, status_bar=False, stdout=True)


    @staticmethod
    def _read_lines(file_path, mode='r') -> list:
        with open(file_path, mode) as file:
            return file.readlines()
