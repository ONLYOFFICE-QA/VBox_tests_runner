# -*- coding: utf-8 -*-
from .config import Config
from ..s3 import S3Vbox


class VmManager:

    def __init__(self):
        self.config = Config()
        self.testing_hosts = self.config.get_all_hosts()

    def download_vm_images(self, cores: int = None, download_dir: str = None):
        S3Vbox(cores=cores).download(download_dir=download_dir, download_files=self._get_s3_object_keys())

    def _get_s3_object_keys(self) -> list:
        return [f"{name}.zip" for name in self.testing_hosts]
