# -*- coding: utf-8 -*-
import time
from os import makedirs
from os.path import join
from subprocess import CompletedProcess
from typing import Optional

from vboxwrapper import FileUtils, VirtualMachine
from rich import print
from rich.console import Console

from frameworks.diagnostics import diagnostics
from frameworks.test_data import Paths
from frameworks.test_data.paths import LocalPaths


class VboxUtilsWindows:
    _cmd = "cmd.exe"
    _powershell = "powershell.exe"
    # A full conversion run returns tens of megabytes of log. Only the last lines are shown, the
    # whole log is written to a file instead.
    _log_console_lines = 300

    def __init__(
            self,
            vm: VirtualMachine,
            user_name: str,
            password: str,
            paths: Paths,
    ):
        self.file = FileUtils(vm_id=vm, username=user_name, password=password)
        self.paths = paths
        self.shell = self._get_shell()

    def upload_test_files(self, upload_files: list[(str, str)]):
        for local, remote in upload_files:
            self._upload(local, remote)

    def create_test_dirs(self, test_dirs: list, try_num: int = 10, interval: int = 1):
        for test_dir in test_dirs:
            self._create_dir(test_dir, try_num=try_num, interval=interval)

    def run_script_on_vm(self, status_bar: bool, try_num: int = 10, interval: int = 3):
        diag = diagnostics()
        server_info = f"{self.file.vm.name}|{self.file.vm.network.get_ip()}"
        line = f"{'-' * 90}"
        print(f"[bold cyan]{line}\n|INFO|{server_info}| Waiting for execution script on VM\n{line}")

        attempt = 0
        while try_num > 0:
            attempt += 1
            with diag.phase(f"guest_script_attempt_{attempt}"):
                out = self._run_cmd(self._get_run_script_cmd(), status_bar=status_bar, stdout=status_bar)

            if out.returncode == 0 or not self._is_retryable_error(out.stderr):
                break

            print(f"[bold yellow]|WARNING|{self.file.vm.name}| Guest session not ready, retrying in {interval}s...")
            time.sleep(interval)
            try_num -= 1

        diag.log_tail(f"guest script log of {self.file.vm.name}", out.stdout)
        with diag.phase("print_guest_script_log"):
            self._show_script_log(out)

    def _show_script_log(self, out: CompletedProcess) -> None:
        """
        Save the log of the script and show its last lines.

        Only the last lines reach the console: rendering the whole log of a full conversion run
        with rich takes hours and gigabytes of memory, which looks like a hang although the test
        itself has already finished.
        :param out: Result of the script run on the guest.
        """
        line = f"{'-' * 90}"
        log_path = self._save_script_log(out.stdout)
        lines = (out.stdout or '').splitlines()
        shown = lines[-self._log_console_lines:]
        counter = f" (last {len(shown)} of {len(lines)} lines)" if len(shown) < len(lines) else ""

        print(f"[cyan]{line}\n|INFO|{self.file.vm.name}|Script execution log{counter}:\n{line}")
        # Markup and highlighting are off because the log is plain text of the guest, and soft wrap
        # skips the line wrapping of rich, which is what makes a long log take hours to render.
        Console(soft_wrap=True).print('\n'.join(shown), markup=False, highlight=False)

        footer = f"[cyan]{line}\n Exit Code: {out.returncode}"
        if log_path:
            footer += f"\n Full log: {log_path}"
        print(f"{footer}\n{line}")

    def _save_script_log(self, stdout: str) -> str | None:
        """
        Write the whole log of the script to a file next to the reports.
        :param stdout: Output collected from the guest.
        :return: Path of the log file, None when it could not be written.
        """
        try:
            directory = join(LocalPaths.reports_dir, 'guest_logs')
            makedirs(directory, exist_ok=True)
            log_path = join(
                directory,
                f"{self.file.vm.name}_{time.strftime('%Y%m%d_%H%M%S')}.log"
            )
            with open(log_path, 'w', encoding='utf-8', errors='replace') as log_file:
                log_file.write(stdout or '')
            return log_path
        except OSError as error:
            print(f"[bold yellow]|WARNING|{self.file.vm.name}| Unable to save the script log: {error}")
            return None

    def download_report(self, path_from: str, path_to: str) -> bool:
        out = self.file.copy_from(path_from, path_to)
        return out.returncode == 0

    def _upload(self, local_path: str, remote_path: str, try_num: int = 10, interval: int = 3) -> None:
        print(f"[green]|INFO|{self.file.vm.name}| Upload file [cyan]{local_path}[/] to [cyan]{remote_path}[/]")
        while try_num > 0:
            out = self.file.copy_to(local_path=local_path, remote_path=remote_path)

            if out.returncode == 0:
                break

            if not self._is_retryable_error(out.stderr):
                break

            print(f"[bold yellow]|WARNING|{self.file.vm.name}| Upload failed, retrying in {interval}s...")
            time.sleep(interval)
            try_num -= 1

    def _create_dir(self, path: str, try_num: int = 10, interval: int = 1) -> None:
        _path = path.replace('/', '\\') if self.shell == self._cmd else path
        print(f"[green]|INFO|{self.file.vm.name}| Creating directory: [cyan]{_path}[/]")
        while try_num > 0:
            out = self.file.create_dir(_path)

            if out.returncode == 0:
                break

            stderr = (out.stderr or '').lower()
            if 'already exists' in stderr or 'exist' in stderr:
                break

            if not self._is_retryable_error(out.stderr):
                break

            print(f"[bold yellow]|WARNING|{self.file.vm.name}| Create dir failed, retrying in {interval}s...")
            time.sleep(interval)
            try_num -= 1

    @staticmethod
    def _is_retryable_error(stderr: str) -> bool:
        if not stderr:
            return False
        retryable_patterns = [
            'File copy failed',
            'Guest Additions are not installed or not ready',
            'VERR_DUPLICATE',
            'not able to logon',
            'VERR_ACCESS_DENIED',
            'VERR_TIMEOUT',
            'VERR_PERMISSION_DENIED',
        ]
        return any(pattern.lower() in stderr.lower() for pattern in retryable_patterns)

    def _get_shell(self) -> Optional[str]:
        if self.paths.remote.run_script_name.endswith(".bat"):
            return self._cmd

        if self.paths.remote.run_script_name.endswith(".ps1"):
            return self._powershell

        return None

    def _get_run_script_cmd(self):
        if self.paths.remote.run_script_name.endswith(".bat"):
            return self.paths.remote.script_path

        if self.paths.remote.run_script_name.endswith(".ps1"):
            script_path = self.paths.remote.script_path.replace("'", "''")
            return (
                "Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; "
                f"& '{script_path}'"
            )

        if self.paths.remote.run_script_name.endswith(".sh"):
            return f"chmod +x {self.paths.remote.script_path} && {self.paths.remote.script_path}"

        if self.paths.remote.run_script_name.endswith(".py"):
            python_executable = "python3"
            if 'windows' in self.file.vm.os_type.lower():
                python_executable = "python.exe"
            return f"{python_executable} {self.paths.remote.script_path}"

        raise ValueError("Unsupported script type.")

    def _run_cmd(
            self,
            cmd: str,
            status_bar: bool = False,
            stdout: bool = True,
            stderr: bool = True
    ) -> CompletedProcess:
        return self.file.run_cmd(command=cmd, status_bar=status_bar, stdout=stdout, stderr=stderr, shell=self.shell)
