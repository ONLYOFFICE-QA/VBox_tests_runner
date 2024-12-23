# -*- coding: utf-8 -*-
from posixpath import join
from host_tools import File
from tempfile import gettempdir

from .test_data import TestData
from .paths import Paths


class RunScript:

    def __init__(self, test_data: TestData, paths: Paths, os_type: str):
        self.data = test_data
        self.os_type = os_type.lower() if os_type else ''
        self._path = paths

    def generate(self) -> str:
        return f'''\
        {self.get_shebang()}
        cd {self._path.remote.script_dir}
        {self.clone_desktop_testing_repo()}
        cd {self._path.remote.desktop_testing_path}
        {self.get_python()} -m venv venv
        {self.get_activate_env_cmd()}
        {self.get_python()} ./install_requirements.py
        {self.generate_run_test_cmd()}
        '''.strip()

    def get_shebang(self) -> str:
        if 'windows' in self.os_type:
            return ''
        return '#!/bin/bash'

    def get_python(self) -> str:
        if 'windows' in self.os_type:
            return 'python.exe'
        return 'python3'

    def get_activate_env_cmd(self) -> str:
        if 'windows' in self.os_type:
            return 'call ./venv/Scripts/activate'
        return 'source ./venv/bin/activate'

    def clone_desktop_testing_repo(self) -> str:
        branch = f"{('-b ' + self.data.branch) if self.data.branch else ''}".strip()
        return f"git clone {branch} {self.data.desktop_testing_url} {self._path.remote.desktop_testing_path}"

    def generate_run_test_cmd(self) -> str:
        return (
            f"invoke open-test -d -v {self.data.version} "
            f"{(' -u ' + self.data.update_from) if self.data.update_from else ''} "
            f"{' -t' if self.data.telegram else ''} "
            f"{(' -c ' + self.data.custom_config_mode) if self.data.custom_config_mode else ''} "
            f"{(' -l ' + self._path.remote.lic_file) if self.data.custom_config_mode else ''}"
        )

    def get_save_path(self) -> str:
        return join(gettempdir(), self._path.remote.run_script_name)

    def create(self) -> str:
        save_path = self.get_save_path()
        File.write(save_path, '\n'.join(line.strip() for line in self.generate().split('\n')), newline='')
        return save_path
