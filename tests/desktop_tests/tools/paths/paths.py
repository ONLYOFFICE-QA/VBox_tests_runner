# -*- coding: utf-8 -*-
from .local_paths import LocalPaths
from .linux_remote_paths import LinuxRemotePaths


class Paths:

    def __init__(self, remote_user_name: str = None):
        self.local = LocalPaths()
        if remote_user_name:
            self.remote = LinuxRemotePaths(user_name=remote_user_name)
