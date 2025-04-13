# -*- coding: utf-8 -*-
from frameworks.test_data.paths.paths import Paths

from .desktop_local_paths import DesktopLocalPaths
from .desktop_remote_paths import DesktopRemotePaths


class DesktopPaths(Paths):

    def __init__(self, os_type: str, remote_user_name: str = None):
        self.__local = None
        self.__remote = None
        self.__os_type = os_type
        self.__remote_user_name = remote_user_name

    @property
    def local(self) -> DesktopLocalPaths:
        if self.__local is None:
            self.__local = DesktopLocalPaths()

        return self.__local

    @property
    def remote(self) -> DesktopRemotePaths:
        if self.__remote is None:
            if self.__remote_user_name:
                self.__remote = DesktopRemotePaths(user_name=self.__remote_user_name, os_type=self.__os_type)

        return self.__remote
