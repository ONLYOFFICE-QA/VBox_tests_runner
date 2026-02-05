# -*- coding: utf-8 -*-
from frameworks.test_data.paths.paths import Paths

from .conversion_local_paths import ConversionLocalPaths
from .conversion_remote_paths import ConversionRemotePaths


class ConversionPaths(Paths):

    def __init__(self, os_info: dict, remote_user_name: str = None):
        self.__local = None
        self.__remote = None
        self.__os_info = os_info
        self.__remote_user_name = remote_user_name

    @property
    def local(self) -> ConversionLocalPaths:
        if self.__local is None:
            self.__local = ConversionLocalPaths()

        return self.__local

    @property
    def remote(self) -> ConversionRemotePaths:
        if self.__remote is None:
            if self.__remote_user_name:
                self.__remote = ConversionRemotePaths(user_name=self.__remote_user_name, os_info=self.__os_info)

        return self.__remote
