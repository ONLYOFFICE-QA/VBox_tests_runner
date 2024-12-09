# -*- coding: utf-8 -*-
from posixpath import join
from host_tools import File
from tempfile import gettempdir

from .paths import Paths


class RunScript:
    def __init__(
            self,
            version: str,
            old_version: str,
            telegram: bool,
            custom_config_path: str,
            desktop_testing_url: str,
            branch: str,
            paths: Paths,
            windows: bool
    ):
        self.windows = windows
        self.version = version
        self.old_version = old_version
        self.telegram = telegram
        self.custom_config = custom_config_path
        self.save_path = self.get_save_path()
        self._path = paths
        self.lic_file = self._path.remote.lic_file
        self.desktop_testing_url = desktop_testing_url
        self.branch = branch

    def generate(self) -> str:
        return f'''\
        {'#!/bin/bash' if not self.windows else ''}
        cd {self._path.remote.script_dir}
        {self.clone_desktop_testing_repo()}
        cd {self._path.remote.desktop_testing_path}
        {self.get_python()} -m venv venv
        {self.get_activate_env_script()}
        {self.get_python()} ./install_requirements.py
        {self.generate_run_test_cmd()}
        '''.strip()

    def get_python(self) -> str:
        if self.windows:
            return 'python.exe'
        return 'python3'

    def get_activate_env_script(self) -> str:
        if self.windows:
            return './venv/Scripts/activate'
        return 'source ./venv/bin/activate'

    def clone_desktop_testing_repo(self) -> str:
        branch = f"{'-b ' if self.branch else ''}{self.branch if self.branch else ''}".strip()
        return f"git clone {branch} {self.desktop_testing_url} {self._path.remote.desktop_testing_path}"

    def generate_run_test_cmd(self) -> str:
        return (
            f"invoke open-test -d -v {self.version} "
            f"{' -u ' + self.old_version if self.old_version else ''} "
            f"{' -t' if self.telegram else ''} "
            f"{(' -c ' + self.custom_config) if self.custom_config else ''} "
            f"{(' -l ' + self.lic_file) if self.custom_config else ''}"
        )

    def get_save_path(self) -> str:
        return join(gettempdir(), 'script.ps1' if self.windows else 'script.sh')

    def create(self) -> str:
        File.write(self.save_path, '\n'.join(line.strip() for line in self.generate().split('\n')), newline='')
        return self.save_path
