# -*- coding: utf-8 -*-
from os import getcwd
from rich import print
from typing import Dict, Optional, Union, List

from dataclasses import dataclass, field
from os.path import join, isfile
from host_tools import File

from frameworks.TestData import TestData
from .desktop_report import DesktopReport

from .desktop_paths import DesktopLocalPaths

@dataclass
class DesktopTestData(TestData):
    version: str
    config_path: str
    status_bar: bool = True
    telegram: bool = False
    custom_config_mode: Union[bool, str] = False
    update_from: Optional[str] = None
    snap: bool = False
    appimage: bool = False
    flatpak: bool = False
    open_retries: int = None
    retest: bool = False

    config: Dict = field(init=False)
    desktop_testing_url: str = field(init=False)
    branch: str = field(init=False)
    vm_names: List[str] = field(init=False)
    title: str = field(init=False)
    report_dir: str = field(init=False)
    full_report_path: str = field(init=False)
    local_paths: DesktopLocalPaths = field(init=False)

    def __post_init__(self):
        self.__config = None
        self.desktop_testing_url = self.config['desktop_script']
        self.branch = self.config['branch']
        self.title = self.config.get('title', 'Undefined_title')
        self.report_dir = self._get_report_dir()
        self.full_report_path = join(self.report_dir, f"{self.version}_{self.title}_desktop_tests_report.csv")
        self.report = DesktopReport(report_path=self.full_report_path)
        self.vm_names = self._get_vm_names()
        self.local_paths = DesktopLocalPaths()
        self._check_package_options()

    @property
    def config(self) -> dict:
        if self.__config is None:
            self.__config = self._read_config()

        return self.__config

    def _check_package_options(self):
        if sum([self.snap, self.appimage, self.flatpak]) > 1:
            raise ValueError("Only one option from snap, appimage, flatpak should be enabled..")

    def _get_vm_names(self) -> List[str]:
        if self.retest:
            return self.report.get_error_vm_list()
        return self.config.get('hosts', [])

    def _get_report_dir(self) -> str:
        dir_name = (
            f"{self.version}"
            f"{'_snap' if self.snap else ''}"
            f"{'_appimage' if self.appimage else ''}"
            f"{'_flatpak' if self.flatpak else ''}"
        )
        return join(getcwd(), 'reports', f"{self.title}_desktop_tests", dir_name)

    def _read_config(self) -> Dict:
        if not isfile(self.config_path):
            raise FileNotFoundError(f"[red]|ERROR| Configuration file not found: {self.config_path}")
        return File.read_json(self.config_path)
