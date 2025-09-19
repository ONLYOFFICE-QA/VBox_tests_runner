# -*- coding: utf-8 -*-
from .config import Config
from ..s3 import S3Vbox


class VmManager:
    """
    Manager for VM image downloads and configuration.

    Handles downloading VM images from S3 storage and managing
    virtual machine configurations for testing environments.
    """

    def __init__(self):
        """
        Initialize VmManager with configuration and testing hosts.
        """
        self.config = Config()
        self.testing_hosts = self.config.get_all_hosts()

    def download_vm_images(self, cores: int = None, download_dir: str = None):
        """
        Download VM images from S3 storage.

        :param cores: Number of CPU cores to use for download
        :param download_dir: Directory to download images to
        """
        S3Vbox(cores=cores).download(download_dir=download_dir, download_files=self._get_s3_object_keys())

    def _get_s3_object_keys(self) -> list:
        """
        Get S3 object keys for VM images.

        :return: List of S3 object keys for VM ZIP files
        """
        return [f"{name}.zip" for name in self.testing_hosts]
