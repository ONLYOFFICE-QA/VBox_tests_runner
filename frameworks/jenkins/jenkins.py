"""Jenkins API helpers."""
from .auth import Auth
from .request_sender import JenkinsRequestSender
from frameworks.VersionHandler import VersionHandler

class Jenkins:

    def __init__(self, id: str = None, token: str = None):
        self.request_sender = JenkinsRequestSender(id=id, token=token)
        self.job_path = self.request_sender.config.JOB_PATH

    def get_last_completed_build_info(self, version: str) -> dict:
        _version = VersionHandler(version)
        job_path = f"{self.job_path}/{_version.get_branch()}%2Fv{_version.without_build}/lastCompletedBuild/api/json"
        return self.request_sender.get(job_path).json()

    def get_last_completed_build_number(self, version: str) -> int:
        return self.get_last_completed_build_info(version).get("number")
