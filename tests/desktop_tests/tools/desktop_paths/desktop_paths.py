# -*- coding: utf-8 -*-
from frameworks.test_data.paths.paths import Paths

from .desktop_local_paths import DesktopLocalPaths
from .desktop_remote_paths import DesktopRemotePaths


class DesktopPaths(Paths):

    def __init__(self, os_type: str, remote_user_name: str = None):
        self.local = DesktopLocalPaths()
        if remote_user_name:
            self.remote = DesktopRemotePaths(user_name=remote_user_name, os_type=os_type)
