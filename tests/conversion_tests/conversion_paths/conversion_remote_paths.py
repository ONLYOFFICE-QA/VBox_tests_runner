# -*- coding: utf-8 -*-
from frameworks.test_data.paths import RemotePaths


class ConversionRemotePaths(RemotePaths):

    def __init__(self, user_name: str, os_info: dict):
        super().__init__(user_name=user_name, os_info=os_info)
        self.x2ttesting_dir = self._join_path(self.home_dir, 'scripts', 'opencv_documents_comparer')
        self.assets_dir = self._join_path(self.x2ttesting_dir, 'assets')
        self.fonts_dir = self._join_path(self.assets_dir, 'fonts')
        self.opencv_dir = self._join_path(self.assets_dir, 'opencv')
