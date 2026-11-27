# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from os.path import isfile, join
from typing import Dict, List, Optional, Union

from host_tools import File, HostInfo

from frameworks.VersionHandler import VersionHandler
from frameworks.test_data import TestData

from .puppeteer_paths import PuppeteerLocalPaths


@dataclass
class PuppeteerTestData(TestData):
    """
    Settings of a Dep.Tests/puppeteer run on the Desktop Editors app (``run.py --host native``).

    :param version: Desktop Editors build to test, e.g. ``10.0.3.15``; ``run.py`` downloads it on the VM
    :param config_path: Path to ``desktop_puppeteer_tests_config.json``
    :param suite: Suite of ``test-suites/native/`` to run; overrides the config
    :param test_path: Test file or folder relative to ``puppeteer/tests``; replaces the suite when set
    :param telegram: Send the report to Telegram
    """
    version: Union[str, VersionHandler]
    config_path: str
    suite: Optional[str] = None
    test_path: Optional[str] = None
    telegram: bool = False

    min_version: str = field(default='10.0.3.15', init=False)
    """Oldest build the native host accepts (MIN_APP_VERSION in engine/script/js/native/nativeTester.js)."""

    title: str = field(init=False)
    report_dir: str = field(init=False)
    full_report_path: str = field(init=False)

    def __post_init__(self):
        super().__post_init__()
        self._status_bar = True
        self._config: Optional[Dict] = None
        self._vm_names: Optional[List[str]] = None

        if not isinstance(self.version, VersionHandler):
            self.version = VersionHandler(version=self.version)
        if not self.version.build:
            raise ValueError(f"Desktop build number is required, e.g. 10.0.3.15, got: {self.version}")
        if self.version < VersionHandler(self.min_version):
            raise ValueError(
                f"The native host of Dep.Tests/puppeteer runs Desktop Editors {self.min_version} and later "
                f"(the first build that saves where the tests ask), got: {self.version}"
            )

        self.title = self.config.get('title', 'ONLYOFFICE')
        self.suite = self.suite or self.config.get('suite') or 'daily'
        self.report_dir = join(PuppeteerLocalPaths.report_dir, str(self.version))
        self.full_report_path = join(self.report_dir, f"{self.version}_{self.title}_puppeteer_report.csv")

    @property
    def status_bar(self) -> bool:
        return self._status_bar

    @status_bar.setter
    def status_bar(self, value: bool):
        self._status_bar = value

    @property
    def config(self) -> dict:
        if self._config is None:
            if not isfile(self.config_path):
                raise FileNotFoundError(f"[red]|ERROR| Configuration file not found: {self.config_path}")
            self._config = File.read_json(self.config_path)
        return self._config

    @property
    def vm_names(self) -> List[str]:
        if self._vm_names is None:
            self._vm_names = self.config.get('hosts_arm64', []) if HostInfo().is_arm else self.config.get('hosts', [])
        return self._vm_names

    @vm_names.setter
    def vm_names(self, value: List[str]):
        if not isinstance(value, list):
            raise ValueError("vm_names must be a list")
        self._vm_names = value

    @property
    def dep_test_repo(self) -> str:
        return self.config.get('dep_test_repo') or 'git@git.onlyoffice.com:ONLYOFFICE-QA/Dep.Tests.git'

    @property
    def dep_test_branch(self) -> Optional[str]:
        return self.config.get('dep_test_branch') or None

    @property
    def pp_files_repo(self) -> str:
        return self.config.get('pp_files_repo') or 'git@github.com:ONLYOFFICE-data/pp-files.git'

    @property
    def pp_files_branch(self) -> Optional[str]:
        return self.config.get('pp_files_branch') or None

    @property
    def document_formats_repo(self) -> str:
        return self.config.get('document_formats_repo') or 'https://github.com/ONLYOFFICE/document-formats.git'

    @property
    def document_formats_branch(self) -> Optional[str]:
        return self.config.get('document_formats_branch') or None

    @property
    def run_options(self) -> List[str]:
        """Extra ``run.py`` options from the config, e.g. ``["--rerun-failed"]``."""
        return list(self.config.get('run_options', []))

    @property
    def config_params(self) -> List[str]:
        """Extra ``run.py --config_params`` values from the config, e.g. ``["testOptions.lang=en-US"]``."""
        return list(self.config.get('config_params', []))
