# -*- coding: utf-8 -*-
from os.path import basename, splitext
from tempfile import gettempdir

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
            self.generate_run_framework_cmd(),
            self.generate_run_docs_cmd()
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
        return (
            f"git clone {self.build_tools_repo} "
            f"{join(self._path.remote.script_dir, splitext(basename(self.build_tools_repo))[0])}"
        )

    def clone_office_js_api_repo(self) -> str:
        return (
            f"git clone {self.office_js_api} "
            f"{join(self._path.remote.script_dir, splitext(basename(self.office_js_api))[0])}"
        )

    def generate_run_framework_cmd(self) -> str:
        options = [
                f"{self.get_python()}",
                f"{self._path.remote.docbuilder_main_script}"
            ]

        return ' '.join(filter(None, options))

    def run_update(self) -> str:
        options = [
            f"{self.get_python()}",
            f"{self._path.remote.update_script}"
        ]
        return ' '.join(filter(None, options))

    def generate_run_docs_cmd(self) -> str:
        options = [
            f"{self.get_python()}",
            f"{self._path.remote.docbuilder_docs_main_script}"
        ]

        return ' '.join(filter(None, options))

    def get_save_path(self) -> str:
        return File.unique_name(gettempdir(), extension=splitext(self._path.remote.run_script_name)[1])

    def create(self) -> str:
        save_path = self.get_save_path()
        File.write(save_path, self.generate(), newline='')
        return save_path
