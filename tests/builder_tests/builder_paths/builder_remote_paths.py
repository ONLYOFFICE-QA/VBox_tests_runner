# -*- coding: utf-8 -*-
from os.path import basename

from frameworks.test_data.paths import RemotePaths


class BuilderRemotePaths(RemotePaths):

    def __init__(self, user_name: str, os_type: str):
        super().__init__(user_name=user_name, os_type=os_type)
        self.dep_test_path = self._join_path(self.script_dir, 'Dep.Test')
        self.docbuilder_path: str = self._join_path(self.dep_test_path, 'docbuilder')
        self.dep_test_archive: str = self._join_path(self.script_dir, f"{basename(self.dep_test_path)}.zip")
        self.docbuilder_main_script: str = self._join_path(self.docbuilder_path, 'check.py')
        self.lic_file = self._join_path(self.script_dir, 'license.xml')
        self.builder_report_dir = self._join_path(self.docbuilder_path, 'out')
