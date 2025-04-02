# -*- coding: utf-8 -*-
from .builder_local_paths import BuilderLocalPaths
from .builder_remote_paths import BuilderRemotePaths


class BuilderPaths:

    def __init__(self, os_type: str, remote_user_name: str = None):
        self.local = BuilderLocalPaths()
        if remote_user_name:
            self.remote = BuilderRemotePaths(user_name=remote_user_name, os_type=os_type)
