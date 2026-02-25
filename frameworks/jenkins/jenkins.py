"""Jenkins API helpers."""
from typing import Optional

from .request_sender import JenkinsRequestSender
from frameworks.VersionHandler import VersionHandler


class Jenkins:

    def __init__(self, id: str = None, token: str = None):
        self.request_sender = JenkinsRequestSender(id=id, token=token)
        self.job_path = self.request_sender.config.JOB_PATH

    def get_last_completed_build_info(self, version: str) -> Optional[dict]:
        """
        Get info about the last completed build from Jenkins.

        :param version: Version string in format 'x.x.x.x'
        :return: Build info dict or None if unavailable
        """
        _version = VersionHandler(version)
        job_path = f"{self.job_path}/{_version.get_branch()}%2Fv{_version.without_build}/lastCompletedBuild/api/json"
        response = self.request_sender.get(job_path)
        if not response.ok:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    def get_last_completed_build_number(self, version: str) -> Optional[int]:
        """
        Get the last completed build number from Jenkins.

        :param version: Version string in format 'x.x.x.x'
        :return: Build number or None if unavailable
        """
        info = self.get_last_completed_build_info(version)
        if info is None:
            return None
        return info.get("number")
