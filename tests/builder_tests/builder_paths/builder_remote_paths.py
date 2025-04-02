# -*- coding: utf-8 -*-
from frameworks.paths import RemotePaths


class BuilderRemotePaths(RemotePaths):

    def __init__(self, user_name: str, os_type: str):
        super().__init__(user_name=user_name, os_type=os_type)
        self.dep_test_path = self._join_path(self.script_dir, 'Dep.Test')
        self.docbuilder_path: str = self._join_path(self.dep_test_path, 'docbuilder')
        self.lic_file = self._join_path(self.script_dir, 'license.xml')
