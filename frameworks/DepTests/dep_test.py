# -*- coding: utf-8 -*-
import subprocess
from os.path import isfile

from host_tools import File
from host_tools.utils import Git

from frameworks.VersionHandler import VersionHandler
from tests.builder_tests.builder_paths import BuilderLocalPaths


class DepTests:
    repo = "git@git.onlyoffice.com:ONLYOFFICE-QA/Dep.Tests.git"

    def __init__(self, version: str):
        self.local_path = BuilderLocalPaths()
        self.version = VersionHandler(version=version)

    def get(self) -> None:
        self.clone_dep_tests()

    def clone_dep_tests(self, branch: str = None) -> None:
        Git.clone(repo=self.repo, branch=branch, path=self.local_path.dep_test_path)

    def compress_dep_tests(self, delete: bool = True) -> None:
        if isfile(self.local_path.dep_test_archive):
            File.delete(self.local_path.dep_test_archive, stdout=False)

        File.compress(
            self.local_path.dep_test_path,
            archive_path=self.local_path.dep_test_archive,
            delete=delete,
            progress_bar=False
        )

    @staticmethod
    def _run_cmd(cmd: str) -> int:
        return subprocess.call(cmd, shell=True)
