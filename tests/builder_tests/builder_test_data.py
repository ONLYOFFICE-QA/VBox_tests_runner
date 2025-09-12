# -*- coding: utf-8 -*-
from dataclasses import dataclass
from os.path import join
from typing import List

from host_tools import HostInfo

from tests.common import BaseTestData
from tests.builder_tests.builder_paths import BuilderLocalPaths

from .builder_report import BuilderReport


@dataclass
class BuilderTestData(BaseTestData):
    __status_bar: bool | None = None

    def __post_init__(self):
        super().__post_init__()
        # Access config values
        config = self.config
        self.dep_test_branch = config.get('dep_test_branch')
        self.build_tools_branch = config.get('build_tools_branch')
        self.portal_project_name = config.get('report_portal', {}).get('project_name')
        self.office_js_api_branch = config.get('office_js_api_branch')
        self.document_builder_samples_branch = config.get('document_builder_samples_branch')
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
    def vm_names(self) -> List[str]:
        """Filter VM names based on architecture compatibility"""
        hosts = self.config.get('hosts', [])
        is_mac_arm = HostInfo().is_mac
        return [name for name in hosts if ('arm64' in name.lower()) == is_mac_arm]

    def _get_full_report_path(self) -> str:
        """Get full report path with optimized path construction"""
        return join(
            BuilderLocalPaths().builder_report_dir,
            self.version,
            f"{self.version}_full_report.csv"
        )
