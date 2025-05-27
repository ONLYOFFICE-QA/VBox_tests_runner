# -*- coding: utf-8 -*-
import os
from os.path import join

from host_tools import HostInfo, File


class Config:
    test_configs: list = [
        join(os.getcwd(), "builder_tests_config.json"),
        join(os.getcwd(), "desktop_tests_config.json")
    ]

    def get_all_hosts(self) -> list:
        hosts = { host for config in self.test_configs for host in self._get_hosts(config) }
        return [host for host in hosts if ('arm64' in host.lower()) == HostInfo().is_mac]

    @staticmethod
    def _get_hosts(config_path: str) -> list:
        return File.read_json(config_path)['hosts']
