# -*- coding: utf-8 -*-
from frameworks.test_data.paths import RemotePaths


class DesktopRemotePaths(RemotePaths):

    def __init__(self, user_name: str, os_type: str):
        super().__init__(user_name=user_name, os_type=os_type)
        self.desktop_testing_path = self._join_path(self.script_dir, 'desktop_testing')
        self.python_requirements = self._join_path(self.desktop_testing_path, "install_requirements.py")
        self.report_dir = self._join_path(self.desktop_testing_path, 'reports')
        self.custom_config_path = self._join_path(self.script_dir, 'custom_config.json')
        self.lic_file = self._join_path(self.script_dir, 'test_lic.lickey')
