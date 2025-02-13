# -*- coding: utf-8 -*-
from os import getcwd
from rich import print
from typing import Dict, Optional, Union, List

from dataclasses import dataclass, field
from os.path import join, isfile
from host_tools import File

from .paths import LocalPaths

@dataclass
class TestData:
    version: str
    config_path: str
    status_bar: bool = True
    telegram: bool = False
    custom_config_mode: Union[bool, str] = False
    update_from: Optional[str] = None
    snap: bool = False
    appimage: bool = False
    flatpak: bool = False

    config: Dict = field(init=False)
    desktop_testing_url: str = field(init=False)
    branch: str = field(init=False)
    vm_names: List[str] = field(init=False)
    title: str = field(init=False)
    report_dir: str = field(init=False)
    full_report_path: str = field(init=False)
    local_paths: LocalPaths = field(init=False)

    def __post_init__(self):
        self.config = self._read_config()
        self.desktop_testing_url = self.config['desktop_script']
        self.branch = self.config['branch']
        self.vm_names = self.config.get('hosts', [])
        self.title = self.config.get('title', 'Undefined_title')
        self.report_dir = self._get_report_dir()
        self.full_report_path = join(self.report_dir, f"{self.version}_{self.title}_desktop_tests_report.csv")
        self.local_paths = LocalPaths()
        self._check_package_options()

    @property
    def tg_token(self) -> str:
        return self._read_file(self.token_file).strip()

    @property
    def token_file(self) -> str:
        return self._get_file_path('token_file', 'token')

    @property
    def tg_chat_id(self) -> str:
        return self._read_file(self.chat_id_file).strip()

    @property
    def chat_id_file(self) -> str:
        return self._get_file_path('chat_id_file', 'chat')

    def _read_config(self) -> Dict:
        if not isfile(self.config_path):
            raise FileNotFoundError(f"[red]|ERROR| Configuration file not found: {self.config_path}")
        return File.read_json(self.config_path)

    @staticmethod
    def _read_file(file_path: str) -> str:
        if not isfile(file_path):
            raise FileNotFoundError(f"[red]|ERROR| File not found: {file_path}")
        return File.read(file_path)

    def _get_file_path(self, config_key: str, default_filename: str) -> str:
        filename = self.config.get(config_key, '').strip()
        if filename:
            file_path = join(self.local_paths.tg_dir, filename)
            if isfile(file_path):
                return file_path
            print(
                f"[red]|WARNING| {config_key.replace('_', ' ').capitalize()} "
                f"from config file not exists: {file_path}"
            )
        return join(self.local_paths.tg_dir, default_filename)

    def _get_report_dir(self) -> str:
        dir_name = (
            f"{self.version}"
            f"{'_snap' if self.snap else ''}"
            f"{'_appimage' if self.appimage else ''}"
            f"{'_flatpak' if self.flatpak else ''}"
        )
        return join(getcwd(), 'reports', self.title, dir_name)

    def _check_package_options(self):
        if sum([self.snap, self.appimage, self.flatpak]) > 1:
            raise ValueError("Only one option from snap, appimage, flatpak should be enabled..")
