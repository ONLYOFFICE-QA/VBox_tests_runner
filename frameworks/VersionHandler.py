# -*- coding: utf-8 -*-
from re import sub
from typing import Optional


class VersionHandler:
    """
    Class for handling version numbers like “00.00.00.00”.

    Provides functionality to parse version numbers and extract major, minor and build components.

    Attributes:
        _version_pattern (str): Regular expression pattern to match version numbers.
        Version (str): Version number string.
    """

    def __init__(self, version: str):
        """
        Initializes the VersionHandler object.
        :param version: Version number string.
        """
        self._version_pattern = r'(\d+).(\d+).(\d+).(\d+)'
        self.len_version = self._get_len_version(version)
        self.version = version

    @property
    def version(self) -> str:
        """
        Getter for the version number.
        :return: Version number string.
        """
        return self.__version

    @version.setter
    def version(self, value: str) -> None:
        """
        Setter for the version number.
        Validates the format of the version number.
        :param value: Version number string..
        """
        if self.len_version == 4 or self.len_version == 3:
            self.__version = value
        else:
            raise ValueError(
                "[red]|WARNING| Version is entered incorrectly. "
                "The version must be in the format 'x.x.x.x' or 'x.x.x'"
            )

    @property
    def major(self) -> str:
        """
        Extracts the major version component from the version number.
        :return: Major version string.
        """
        return sub(self._version_pattern, r'\1.\2', self.version)

    @property
    def minor(self) -> str:
        """
        Extracts the minor version component from the version number.
        :return: Minor version string.
        """
        return sub(self._version_pattern, r'\3', self.version)

    @property
    def build(self) -> Optional[int]:
        """
        Extracts the build number component from the version number.
        :return: Build number integer.
        """
        if self.len_version == 4:
            return int(sub(self._version_pattern, r'\4', self.version))
        return None

    @property
    def without_build(self) -> str:
        """
        Extracts the version number without the build component.
        :return: Version number string without the build component.
        """
        return f"{self.major}.{self.minor}"

    @staticmethod
    def _get_len_version(version) -> int:
        return len([int(i) for i in version.split('.') if i])
