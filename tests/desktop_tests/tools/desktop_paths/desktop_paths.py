# -*- coding: utf-8 -*-
from .desktop_local_paths import DesktopLocalPaths
from .desktop_remote_paths import DesktopRemotePaths


class DesktopPaths:

    def __init__(self, os_type: str, remote_user_name: str = None):
        super().__init__(os_type=os_type, remote_user_name=remote_user_name)
        self.local = DesktopLocalPaths()
        if remote_user_name:
            self.remote = DesktopRemotePaths(user_name=remote_user_name, os_type=os_type)
