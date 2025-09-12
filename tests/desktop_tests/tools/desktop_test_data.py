# -*- coding: utf-8 -*-
from os import getcwd
from typing import Optional, Union, List

from dataclasses import dataclass, field
from os.path import join

from frameworks.VersionHandler import VersionHandler
from tests.common import BaseTestData

from .desktop_paths import DesktopLocalPaths
from .desktop_report import DesktopReport


@dataclass
class DesktopTestData(BaseTestData):
    status_bar: bool = True
    telegram: bool = False
    custom_config_mode: Union[bool, str] = False
    update_from: Optional[str] = None
    snap: bool = False
    appimage: bool = False
    flatpak: bool = False
    open_retries: int = None
    retest: bool = False

    # Computed fields
    desktop_testing_url: str = field(init=False)
    branch: str = field(init=False)
    title: str = field(init=False)
    report_dir: str = field(init=False)
    full_report_path: str = field(init=False)
    local_paths: DesktopLocalPaths = field(init=False)

    def __post_init__(self):
        super().__post_init__()

        if not isinstance(self.version, VersionHandler):
            self.version = VersionHandler(version=self.version)

        # Access config
        config = self.config
        self.desktop_testing_url = config['desktop_script']
        self.branch = config['branch']
        self.title = config.get('title', 'Undefined_title')
        self.portal_project_name = config.get('report_portal', {}).get('project_name')
        self.report_dir = self._get_report_dir()
        self.full_report_path = join(self.report_dir, f"{self.version}_{self.title}_desktop_tests_report.csv")
        self.local_paths = DesktopLocalPaths()
        self._check_package_options()

    @property
    def vm_names(self) -> List[str]:
        if self.retest:
            return DesktopReport(self.full_report_path).get_error_vm_list()
        return self.config.get('hosts', [])

    @property
    def package_name(self) -> str:
        if self.snap:
            return "Snap Packages"

        if self.appimage:
            return "AppImages"

        if self.flatpak:
            return "FlatPak"

        return "Default Packages"

    def _check_package_options(self):
        if sum([self.snap, self.appimage, self.flatpak]) > 1:
            raise ValueError("Only one option from snap, appimage, flatpak should be enabled..")

    def _get_report_dir(self) -> str:
        dir_name = (
            f"{self.version}"
            f"{'_snap' if self.snap else ''}"
            f"{'_appimage' if self.appimage else ''}"
            f"{'_flatpak' if self.flatpak else ''}"
        )
        return join(getcwd(), 'reports', f"{self.title}_desktop_tests", dir_name)
