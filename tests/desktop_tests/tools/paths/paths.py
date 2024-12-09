# -*- coding: utf-8 -*-
from .local_paths import LocalPaths
from .remote_paths import RemotePaths


class Paths:

    def __init__(self, os_type: str, remote_user_name: str = None):
        self.local = LocalPaths()
        if remote_user_name:
            self.remote = RemotePaths(user_name=remote_user_name, windows=('windows' in os_type.lower()))
