"""Jenkins HTTP request sender."""
from urllib.parse import urljoin
import requests

from .auth import Auth
from .config import Config


class JenkinsRequestSender:
    """
    Sends HTTP requests to Jenkins.

    :param auth: Jenkins auth instance.
    """
    def __init__(self, id: str = None, token: str = None):
        self.config = Config()
        self.auth = Auth(id=id, token=token)
        self.base_url = self.config.JENKINS_URL

    def get(self, job_path: str) -> requests.Response:
        """
        Send GET request with Jenkins auth.

        :param job_path: Target job path.
        """
        return requests.get(urljoin(self.base_url, job_path), auth=(self.auth.id, self.auth.token))
