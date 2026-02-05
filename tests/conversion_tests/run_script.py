# -*- coding: utf-8 -*-
from os.path import basename, splitext
from tempfile import gettempdir
from typing import Optional

from host_tools import File

from .conversion_paths import ConversionPaths
from .conversion_test_data import ConversionTestData


class RunScript:

    def __init__(self, test_data: ConversionTestData, paths: ConversionPaths):
        self.data = test_data
        self._path = paths
        self.is_ps1 = self._path.remote.run_script_name.endswith('.ps1')
        self.is_bat = self._path.remote.run_script_name.endswith('.bat')
        self.is_windows = self.is_bat or self.is_ps1

    def generate(self) -> str:
        commands = [
            self.get_shebang(),
            self.get_update_command(self._path.remote.x2ttesting_dir, branch="master"),
            self.get_update_command(self._path.remote.fonts_dir, branch="master"),
            self.get_run_script_cmd(self._path.remote.x2ttesting_dir),
        ]

        script_content = [line.strip() for line in filter(None, commands)]
        return ' && '.join(script_content) if self.is_bat else '\n'.join(script_content)

    def get_update_command(self, dir_path: str, branch: str = None) -> str:
        branch = f" && git checkout {branch}" if branch else ""
        return f"{self.get_change_dir_command(dir_path)}{branch} && git pull"

    def get_shebang(self) -> str:
        if self.is_windows:
            return ''
        return '#!/bin/bash'

    def get_run_script_cmd(self, dir_path: str) -> str:
        return f"cd {dir_path} && uv run {self.data.config.get('run_script_cmd').format(version=self.data.version)}"

    def get_change_dir_command(self, dir_path: str) -> str:
        return f"cd {dir_path}"

    def create(self) -> str:
        save_path = self.get_save_path()
        File.write(save_path, self.generate(), newline='')
        return save_path

    def get_save_path(self) -> str:
        return File.unique_name(gettempdir(), extension=splitext(self._path.remote.run_script_name)[1])
