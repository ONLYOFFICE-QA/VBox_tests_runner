# -*- coding: utf-8 -*-
from os.path import splitext
from host_tools import File
from tempfile import gettempdir

from .test_data import TestData
from .paths import Paths


class RunScript:

    def __init__(self, test_data: TestData, paths: Paths):
        self.data = test_data
        self._path = paths
        self.is_ps1 = self._path.remote.run_script_name.endswith('.ps1')
        self.is_bat = self._path.remote.run_script_name.endswith('.bat')
        self.is_windows = self.is_bat or self.is_ps1

    def generate(self) -> str:
        commands = [
            self.get_shebang(),
            self.clone_desktop_testing_repo(),
            self.get_change_dir_command(self._path.remote.desktop_testing_path),
            self.get_create_venv_command(),
            self.get_activate_venv_cmd(),
            self.get_install_requirements_command(),
            self.generate_run_test_cmd()
        ]
        script_content = [line.strip() for line in filter(None, commands)]
        return ' && '.join(script_content) if self.is_bat else '\n'.join(script_content)

    @staticmethod
    def get_change_dir_command(dir_path: str) ->str:
        return f"cd {dir_path}"

    def get_create_venv_command(self) -> str:
        return f"{self.get_python()} -m venv venv"

    def get_install_requirements_command(self) -> str:
        return f"{self.get_python()} {self._path.remote.python_requirements}"

    def get_shebang(self) -> str:
        if self.is_windows:
            return ''
        return '#!/bin/bash'

    def get_python(self) -> str:
        if self.is_windows:
            return 'python.exe'
        return 'python3'

    def get_activate_venv_cmd(self) -> str:
        if self.is_bat:
            return ''

        if self.is_ps1:
            return './venv/Scripts/activate'

        return 'source ./venv/bin/activate'

    def clone_desktop_testing_repo(self) -> str:
        branch = f"{('-b ' + self.data.branch) if self.data.branch else ''}".strip()
        return f"git clone {branch} {self.data.desktop_testing_url} {self._path.remote.desktop_testing_path}"

    def generate_run_test_cmd(self) -> str:
        options = [
            "invoke open-test -d",
            f"-v {self.data.version}",
            f"-u {self.data.update_from}" if self.data.update_from else '',
            "-t" if self.data.telegram else '',
            f"-c {self.data.custom_config_mode}" if self.data.custom_config_mode else '',
            f"-l {self._path.remote.lic_file}" if self.data.custom_config_mode else '',
            f"--snap" if self.data.snap else ''
        ]
        return ' '.join(filter(None, options))

    def get_save_path(self) -> str:
        return File.unique_name(gettempdir(), extension=splitext(self._path.remote.run_script_name)[1])

    def create(self) -> str:
        save_path = self.get_save_path()
        File.write(save_path, self.generate(), newline='')
        return save_path
