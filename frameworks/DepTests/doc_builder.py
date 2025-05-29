# -*- coding: utf-8 -*-
from host_tools.utils import File, Git
from frameworks.VersionHandler import VersionHandler

from .dep_test import DepTests


class DocBuilder(DepTests):
    document_builder_samples_repo = 'git@git.onlyoffice.com:ONLYOFFICE/document-builder-samples.git'

    def __init__(self, version: str):
        super().__init__()
        self.version = VersionHandler(version=version)

    def get(self, dep_test_branch: str = None, builder_samples_branch: str = None) -> None:
        self.clone_dep_tests(branch=dep_test_branch)
        self.clone_builder_samples(branch=builder_samples_branch)
        self.configure()

    def clone_builder_samples(self, branch: str) -> None:
        Git.clone(self.document_builder_samples_repo, branch=branch, path=self.local_path.document_builder_samples)

    def configure(self):
        data = File.read_json(self.local_path.docbuilder_config)
        data['branch'] = self._get_branch()
        data['build'] = self._get_build()
        File.write_json(self.local_path.docbuilder_config, data=data, indent=2)

    def _get_branch(self):
        if "99.99.99" in str(self.version):
            return 'develop'

        if self.version.minor != "0":
            return f'hotfix/v{self.version.without_build}'

        return f"release/v{self.version.without_build}"

    def _get_build(self) -> str:
        if self.version.build:

            return f"{self.version.build}"

        return 'latest'
