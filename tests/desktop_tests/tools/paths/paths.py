# -*- coding: utf-8 -*-
from .local_paths import LocalPaths
from .remote_paths import RemotePaths


class Paths:

    def __init__(self, user_name: str):
        self.local = LocalPaths()
        self.remote = RemotePaths(user_name=user_name)
