# -*- coding: utf-8 -*-
from typing import Optional
from frameworks.test_data.paths.paths import Paths

from .builder_local_paths import BuilderLocalPaths
from .builder_remote_paths import BuilderRemotePaths


class BuilderPaths(Paths):

    def __init__(self, os_info: dict, remote_user_name: str = None, remote_script_dir: Optional[str] = None):
        self.__local = None
        self.__remote = None
        self.__os_info = os_info
        self.__remote_user_name = remote_user_name
        self.__remote_script_dir = remote_script_dir

    @property
    def local(self) -> BuilderLocalPaths:
        if self.__local is None:
            self.__local = BuilderLocalPaths()

        return self.__local

    @property
    def remote(self) -> BuilderRemotePaths:
        if self.__remote is None:
            if self.__remote_user_name:
                self.__remote = BuilderRemotePaths(user_name=self.__remote_user_name, os_info=self.__os_info, script_dir=self.__remote_script_dir)

        return self.__remote
