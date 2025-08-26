# -*- coding: utf-8 -*-
import re

class VersionHandler:
    """
    Class for handling version numbers like "00.00.00.00".

    Provides functionality to parse version numbers and extract major, minor, and build components.
    """

    _version_pattern = re.compile(r'^(\d+)\.(\d+)\.(\d+)\.(\d+)$', re.ASCII)

    def __init__(self, version: str):
        """
        Initialize the VersionHandler with a version string.

        :param version: Version number string in the format 'x.x.x.x'.
        """
        self._components = self._parse_version(version)
        self.version = version

    @property
    def major(self) -> str:
        """
        Extract the major version component.

        :return: Major version as 'x.x'.
        """
        return f"{self._components[0]}.{self._components[1]}"

    @property
    def minor(self) -> int:
        """
        Extract the minor version component.

        :return: Minor version as a string.
        """
        return self._components[2]

    @property
    def build(self) -> int:
        """
        Extract the build number component.

        :return: Build number as an integer.
        """
        return self._components[3]

    @property
    def without_build(self) -> str:
        """
        Get the version string without the build component.

        :return: Version string in the format 'x.x.x'.
        """
        return f"{self.major}.{self.minor}"

    @staticmethod
    def _parse_version(version: str) -> tuple[int, ...]:
        """
        Validate and parse the version string into components.

        :param version: Version number string in the format 'x.x.x.x'.
        :return: Tuple containing the version components as integers.
        :raises ValueError: If the version string is not in the correct format.
        """
        if not isinstance(version, str) or not version.strip():
            raise ValueError(f"[red]|ERROR| Version must be a non-empty string. Version: {version}.")
        match = VersionHandler._version_pattern.fullmatch(version)
        if not match:
            raise ValueError(
                f"[red]|ERROR| Version is entered incorrectly: '{version}'. "
                f"The version must be in the format 'x.x.x.x'"
            )
        return tuple(int(part) for part in match.groups())

    def __str__(self):
        """
        Return the original version string.

        :return: The version string.
        """
        return self.version

    def __repr__(self):
        """
        Return the technical representation of the object.

        :return: A string representation suitable for debugging.
        """
        return f"VersionHandler(version='{self.version}')"

    def __eq__(self, other):
        """
        Compare two VersionHandler instances for equality.

        :param other: Another VersionHandler instance.
        :return: True if the versions are equal, otherwise False.
        """
        if isinstance(other, VersionHandler):
            return self._components == other._components
        return False

    def __lt__(self, other):
        """
        Less-than comparison for sorting.

        :param other: Another VersionHandler instance.
        :return: True if this version is less than the other.
        """
        if isinstance(other, VersionHandler):
            return self._components < other._components
        return NotImplemented

    def __le__(self, other):
        """
        Less-than-or-equal comparison.

        :param other: Another VersionHandler instance.
        :return: True if this version is less than or equal to the other.
        """
        if isinstance(other, VersionHandler):
            return self._components <= other._components
        return NotImplemented

    def __gt__(self, other):
        """
        Greater-than comparison.

        :param other: Another VersionHandler instance.
        :return: True if this version is greater than the other.
        """
        if isinstance(other, VersionHandler):
            return self._components > other._components
        return NotImplemented

    def __ge__(self, other):
        """
        Greater-than-or-equal comparison.

        :param other: Another VersionHandler instance.
        :return: True if this version is greater than or equal to the other.
        """
        if isinstance(other, VersionHandler):
            return self._components >= other._components
        return NotImplemented

    def __hash__(self):
        """
        Return a hash of the version.

        :return: Integer hash based on version components.
        """
        return hash(self._components)
