# -*- coding: utf-8 -*-
from os.path import splitext
from tempfile import gettempdir
from typing import Optional

from host_tools import File

from .builder_paths import BuilderPaths
from .builder_test_data import BuilderTestData


class RunScript:
    """
    Builds the run script that is executed on the remote VM (or host) to run builder tests.

    The script unpacks pre-packed archives (Dep.Tests, build_tools, office-js-api) that were
    cloned and compressed on the host, sets the builder license environment variable and
    runs the configured docbuilder test scripts.
    """

    def __init__(self, test_data: BuilderTestData, paths: BuilderPaths):
        """
        Initialize script generator with test data and resolved paths.

        :param test_data: Builder test data (config and branches)
        :param paths: Local and remote paths used for archives, scripts and reports
        """
        self.data = test_data
        self._path = paths
        self.is_ps1 = self._path.remote.run_script_name.endswith('.ps1')
        self.is_bat = self._path.remote.run_script_name.endswith('.bat')
        self.is_windows = self.is_bat or self.is_ps1

    def generate(self) -> str:
        """
        Build the full script body as a single string.

        Commands are joined by ``&&`` for ``.bat`` and by newlines for shell/PowerShell scripts.

        :return: The generated script content
        """
        commands = [
            self.get_shebang(),
            self.unpack_dep_test(),
            self.unpack_build_tools(),
            self.unpack_office_js_api(),
            self.get_change_dir_command(self._path.remote.docbuilder_path),
            self.set_license(),
            self.run_update(),
            *[self._generate_run_script_cmd(script, params) for script, params in self._path.remote.tests_scripts.items()]
        ]

        script_content = [line.strip() for line in filter(None, commands)]
        return ' && '.join(script_content) if self.is_bat else '\n'.join(script_content)

    def set_license(self) -> str:
        """
        Generate the platform-specific command that exports the builder license path.

        :return: Shell or PowerShell command setting ``ONLYOFFICE_BUILDER_LICENSE``
        """
        if self.is_windows:
            return f"$env:ONLYOFFICE_BUILDER_LICENSE = '{self._path.remote.lic_file}'"
        return f"export ONLYOFFICE_BUILDER_LICENSE={self._path.remote.lic_file}"

    def unpack_dep_test(self) -> str:
        """
        Generate the command that unpacks the Dep.Tests archive on the target machine.

        :return: Unpack command for the Dep.Tests archive
        """
        return self.get_unpack_command(self._path.remote.dep_test_archive, self._path.remote.dep_test_path)

    def unpack_build_tools(self) -> str:
        """
        Generate the command that unpacks the build_tools archive on the target machine.

        The archive is produced on the host (no git clone is performed on the VM).

        :return: Unpack command for the build_tools archive
        """
        return self.get_unpack_command(self._path.remote.build_tools_archive, self._path.remote.build_tools_path)

    def unpack_office_js_api(self) -> str:
        """
        Generate the command that unpacks the office-js-api archive on the target machine.

        The archive is produced on the host (no git clone is performed on the VM).

        :return: Unpack command for the office-js-api archive
        """
        return self.get_unpack_command(self._path.remote.office_js_api_archive, self._path.remote.office_js_api_path)

    def get_unpack_command(self, archive: str, destination: str) -> str:
        """
        Build a platform-specific archive unpack command.

        :param archive: Path to the zip archive on the target machine
        :param destination: Directory where the archive must be extracted
        :return: ``Expand-Archive`` command on Windows, ``unzip`` command otherwise
        """
        if self.is_windows:
            return f"Expand-Archive -Path {archive} -DestinationPath {destination} -Force"
        return f"unzip {archive} -d {destination}"

    @staticmethod
    def get_change_dir_command(dir_path: str) ->str:
        """
        Build a ``cd`` command that works for all supported shells.

        :param dir_path: Target directory
        :return: Change-directory command
        """
        return f"cd {dir_path}"

    def get_shebang(self) -> str:
        """
        Return the shebang line for shell scripts.

        :return: ``#!/bin/bash`` for shell scripts, empty string for Windows scripts
        """
        if self.is_windows:
            return ''
        return '#!/bin/bash'

    def get_python(self) -> str:
        """
        Return the Python interpreter executable name for the target platform.

        :return: ``python.exe`` on Windows, ``python3`` otherwise
        """
        if self.is_windows:
            return 'python.exe'
        return 'python3'

    def get_save_path(self) -> str:
        """
        Generate a unique temporary path with the proper script extension.

        :return: Absolute path inside the system temp directory
        """
        return File.unique_name(gettempdir(), extension=splitext(self._path.remote.run_script_name)[1])

    def create(self) -> str:
        """
        Generate the script and write it to a unique temporary file.

        :return: Path to the created script file
        """
        save_path = self.get_save_path()
        File.write(save_path, self.generate(), newline='')
        return save_path

    def run_update(self) -> str:
        """
        Generate the command that runs the docbuilder ``update.py`` script.

        :return: Command line that invokes the update script
        """
        return self._generate_run_script_cmd(self._path.remote.update_script)

    def _generate_run_script_cmd(self, script_path: str, params: Optional[list[str]] = None) -> str:
        """
        Build a ``python <script> [params...]`` command.

        :param script_path: Path to the python script on the target machine
        :param params: Optional list of CLI arguments to append
        :return: Full command line as a single string
        """
        return ' '.join(filter(None, [self.get_python(), script_path, *(params or [])]))
