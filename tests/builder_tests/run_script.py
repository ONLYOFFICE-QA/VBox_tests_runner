# -*- coding: utf-8 -*-
from os.path import basename, splitext
from tempfile import gettempdir
from typing import Optional

from host_tools import File

from posixpath import join

from .builder_paths import BuilderPaths
from .builder_test_data import BuilderTestData


class RunScript:
    build_tools_repo: str = "https://github.com/ONLYOFFICE/build_tools.git"
    office_js_api: str = "https://github.com/ONLYOFFICE/office-js-api.git"

    def __init__(self, test_data: BuilderTestData, paths: BuilderPaths):
        self.data = test_data
        self._path = paths
        self.is_ps1 = self._path.remote.run_script_name.endswith('.ps1')
        self.is_bat = self._path.remote.run_script_name.endswith('.bat')
        self.is_windows = self.is_bat or self.is_ps1

    def generate(self) -> str:
        commands = [
            self.get_shebang(),
            self.unpack_dep_test(),
            self.clone_build_tools_repo(),
            self.clone_office_js_api_repo(),
            self.get_change_dir_command(self._path.remote.docbuilder_path),
            self.set_license(),
            self.run_update(),
            *[self._generate_run_script_cmd(script, params) for script, params in self._path.remote.tests_scripts.items()]
        ]

        script_content = [line.strip() for line in filter(None, commands)]
        return ' && '.join(script_content) if self.is_bat else '\n'.join(script_content)

    def set_license(self) -> str:
        if self.is_windows:
            return f"$env:ONLYOFFICE_BUILDER_LICENSE = '{self._path.remote.lic_file}'"
        return f"export ONLYOFFICE_BUILDER_LICENSE={self._path.remote.lic_file}"

    def unpack_dep_test(self) -> str:
        if self.is_windows:
            return (
                f"Expand-Archive -Path "
                f"{self._path.remote.dep_test_archive} -DestinationPath {self._path.remote.dep_test_path} -Force"
            )
        return f"unzip {self._path.remote.dep_test_archive} -d {self._path.remote.dep_test_path}"

    @staticmethod
    def get_change_dir_command(dir_path: str) ->str:
        return f"cd {dir_path}"

    def get_shebang(self) -> str:
        if self.is_windows:
            return ''
        return '#!/bin/bash'

    def get_python(self) -> str:
        if self.is_windows:
            return 'python.exe'
        return 'python3'

    def clone_build_tools_repo(self) -> str:
        branch = f"{('-b ' + self.data.build_tools_branch + ' ') if self.data.build_tools_branch else ''}"
        return (
            f"git clone {branch}{self.build_tools_repo} "
            f"{join(self._path.remote.script_dir, splitext(basename(self.build_tools_repo))[0])}"
        )

    def clone_office_js_api_repo(self) -> str:
        branch = f"{('-b ' + self.data.office_js_api_branch + ' ') if self.data.office_js_api_branch else ''}"
        return (
            f"git clone {branch}{self.office_js_api} "
            f"{join(self._path.remote.script_dir, splitext(basename(self.office_js_api))[0])}"
        )

    def get_save_path(self) -> str:
        return File.unique_name(gettempdir(), extension=splitext(self._path.remote.run_script_name)[1])

    def create(self) -> str:
        save_path = self.get_save_path()
        File.write(save_path, self.generate(), newline='')
        return save_path

    def run_update(self) -> str:
        """Generate command to run update script."""
        return self._generate_run_script_cmd(self._path.remote.update_script)

    def _generate_run_script_cmd(self, script_path: str, params: Optional[list[str]] = None) -> str:
        return ' '.join(filter(None, [self.get_python(), script_path, *(params or [])]))
