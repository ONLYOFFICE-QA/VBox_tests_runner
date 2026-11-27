# -*- coding: utf-8 -*-
from typing import Optional

from frameworks.test_data.paths.paths import Paths

from .puppeteer_local_paths import PuppeteerLocalPaths
from .puppeteer_remote_paths import PuppeteerRemotePaths


class PuppeteerPaths(Paths):

    def __init__(self, os_info: dict, remote_user_name: Optional[str] = None):
        self.__local = None
        self.__remote = None
        self.__os_info = os_info
        self.__remote_user_name = remote_user_name

    @property
    def local(self) -> PuppeteerLocalPaths:
        if self.__local is None:
            self.__local = PuppeteerLocalPaths()

        return self.__local

    @property
    def remote(self) -> Optional[PuppeteerRemotePaths]:
        if self.__remote is None:
            if self.__remote_user_name:
                self.__remote = PuppeteerRemotePaths(user_name=self.__remote_user_name, os_info=self.__os_info)

        return self.__remote
