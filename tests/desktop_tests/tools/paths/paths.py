# -*- coding: utf-8 -*-
from host_tools import singleton

from .local_paths import LocalPaths
from .remote_paths import RemotePaths


@singleton
class Paths:

    def __init__(self):
        self.local = LocalPaths()
        self.remote = RemotePaths()
