# -*- coding: utf-8 -*-
from frameworks.test_data.paths import RemotePaths

from .puppeteer_local_paths import PuppeteerLocalPaths


class PuppeteerRemotePaths(RemotePaths):
    """
    VM-side paths of the Dep.Tests/puppeteer desktop tests.
    """

    def __init__(self, user_name: str, os_info: dict):
        super().__init__(user_name=user_name, os_info=os_info)
        self.dep_test_path: str = self._join_path(self.script_dir, 'Dep.Tests')
        self.dep_test_archive: str = self._join_path(self.script_dir, 'Dep.Tests.zip')
        self.puppeteer_path: str = self._join_path(self.dep_test_path, 'puppeteer')
        self.engine_path: str = self._join_path(self.puppeteer_path, 'engine')
        self.venv_path: str = self._join_path(self.script_dir, 'venv')
        self.formats_file: str = self._join_path(self.puppeteer_path, PuppeteerLocalPaths.formats_file_name)
        self.out_dir: str = self._join_path(self.puppeteer_path, 'out')
        # out/ is packed into one file in a folder of its own: the host downloads that folder, which keeps the
        # tree of out/ intact and takes one copy instead of one per file
        self.out_archive_dir: str = self._join_path(self.script_dir, 'out_archive')
        self.out_archive: str = self._join_path(self.out_archive_dir, PuppeteerLocalPaths.out_archive_name)
