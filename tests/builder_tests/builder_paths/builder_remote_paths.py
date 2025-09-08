# -*- coding: utf-8 -*-
from os.path import basename
from typing import Optional

from frameworks.test_data.paths import RemotePaths


class BuilderRemotePaths(RemotePaths):

    def __init__(self, user_name: str, os_info: dict):
        super().__init__(user_name=user_name, os_info=os_info)
        self.dep_test_path = self._join_path(self.script_dir, 'Dep.Test')
        self.docbuilder_path: str = self._join_path(self.dep_test_path, 'docbuilder')
        self.docbuilder_docs_path: str = self._join_path(self.dep_test_path, 'docbuilder-docs')
        self.dep_test_archive: str = self._join_path(self.script_dir, f"{basename(self.dep_test_path)}.zip")

        self.update_script: str = self._join_path(self.docbuilder_path, 'update.py')
        self.lic_file = self._join_path(self.docbuilder_path, '.license', 'license.xml')
        self.builder_report_dir = self._join_path(self.docbuilder_path, 'reports')

        # tests with params if needed {script_path: params}
        self.tests_scripts: dict[str, Optional[str]] = {
            self._join_path(self.docbuilder_path, 'check-framework.py'): None,
            self._join_path(self.docbuilder_path, 'check-docs.py'): None,
            self._join_path(self.docbuilder_path, 'check-tests.py'): None
        }
