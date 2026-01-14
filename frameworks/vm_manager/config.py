# -*- coding: utf-8 -*-
import os
from os.path import join

from host_tools import HostInfo, File


class Config:
    """
    Configuration manager for test environments.

    Manages test configuration files and extracts host information
    for both builder and desktop testing environments.
    """
    test_configs: list = [
        join(os.getcwd(), "builder_tests_config.json"),
        join(os.getcwd(), "desktop_tests_config.json")
    ]

    def get_all_hosts(self) -> list:
        """
        Get all unique hosts from test configurations.

        Filters hosts based on architecture compatibility:
        - On Mac: only ARM64 hosts
        - On other platforms: only non-ARM64 hosts

        :return: List of filtered host names
        """
        hosts = { host for config in self.test_configs for host in self._get_hosts(config) }
        return [host for host in hosts]

    @staticmethod
    def _get_hosts(config_path: str) -> list:
        """
        Extract hosts list from configuration file.

        :param config_path: Path to JSON configuration file
        :return: List of host names from the configuration
        """
        return File.read_json(config_path)['hosts_arm64' if HostInfo().is_arm else 'hosts']
