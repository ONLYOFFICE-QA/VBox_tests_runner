# -*- coding: utf-8 -*-
from dataclasses import dataclass
from os.path import isfile, join
from typing import Dict, List

from host_tools import File, HostInfo

from frameworks.test_data import TestData
from tests.builder_tests.builder_paths import BuilderLocalPaths

from .builder_report import BuilderReport


@dataclass
class BuilderTestData(TestData):
    version: str
    config_path: str
    __status_bar: bool | None = None
    __config = None

    def __post_init__(self):
        super().__post_init__()
        self.dep_test_branch = self.config.get('dep_test_branch')
        self.build_tools_branch = self.config.get('build_tools_branch')
        self.portal_project_name = self.config.get('report_portal').get('project_name')
        self.office_js_api_branch = self.config.get('office_js_api_branch')
        self.document_builder_samples_branch = self.config.get('document_builder_samples_branch')
        self.full_report_path = self._get_full_report_path()
        self.report = BuilderReport(self.full_report_path)

    @property
    def status_bar(self) -> bool | None:
        return self.__status_bar

    @status_bar.setter
    def status_bar(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError("status_bar must be a boolean value")
        self.__status_bar = value

    @property
    def config(self) -> dict:
        if self.__config is None:
            self.__config = self._read_config()

        return self.__config

    @property
    def vm_names(self) -> List[str]:
        if HostInfo().os == 'mac':
            return [name for name in self.config.get('hosts', []) if 'arm64' in name.lower()]
        return [name for name in self.config.get('hosts', []) if 'arm64' not in name.lower()]

    def _read_config(self) -> Dict:
        if not isfile(self.config_path):
            raise FileNotFoundError(f"[red]|ERROR| Configuration file not found: {self.config_path}")
        return File.read_json(self.config_path)

    def _get_full_report_path(self) -> str:
        return join(
            BuilderLocalPaths().builder_report_dir,
            self.version,
            f"{self.version}_full_report.csv"
        )
