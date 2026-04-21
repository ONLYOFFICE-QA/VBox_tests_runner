# -*- coding: utf-8 -*-
from os.path import isfile

from host_tools.utils import File, Git
from frameworks.VersionHandler import VersionHandler

from .dep_test import DepTests


class DocBuilder(DepTests):
    document_builder_samples_repo: str = 'git@git.onlyoffice.com:ONLYOFFICE/document-builder-samples.git'
    build_tools_repo: str = "git@git.onlyoffice.com:ONLYOFFICE/build_tools.git"
    office_js_api_repo: str = "git@git.onlyoffice.com:ONLYOFFICE/office-js-api.git"

    def __init__(self, version: str):
        super().__init__()
        self.version = VersionHandler(version=version)

    def get(
        self,
        dep_test_branch: str = None,
        builder_samples_branch: str = None,
        build_tools_branch: str = None,
        office_js_api_branch: str = None,
    ) -> None:
        """
        Clone all repositories required for builder tests and prepare config.

        :param dep_test_branch: Branch of the Dep.Tests repository
        :param builder_samples_branch: Branch of the document-builder-samples repository
        :param build_tools_branch: Branch of the build_tools repository
        :param office_js_api_branch: Branch of the office-js-api repository
        """
        self.clone_dep_tests(branch=dep_test_branch)
        self.clone_builder_samples(branch=builder_samples_branch)
        self.clone_build_tools(branch=build_tools_branch)
        self.clone_office_js_api(branch=office_js_api_branch)
        self.configure()

    def clone_builder_samples(self, branch: str = None) -> None:
        """
        Clone document-builder-samples repository.

        :param branch: Git branch to clone
        """
        Git.clone(self.document_builder_samples_repo, branch=branch, path=self.local_path.document_builder_samples)

    def clone_build_tools(self, branch: str = None) -> None:
        """
        Clone build_tools repository.

        :param branch: Git branch to clone
        """
        Git.clone(self.build_tools_repo, branch=branch, path=self.local_path.build_tools_path)

    def clone_office_js_api(self, branch: str = None) -> None:
        """
        Clone office-js-api repository.

        :param branch: Git branch to clone
        """
        Git.clone(self.office_js_api_repo, branch=branch, path=self.local_path.office_js_api_path)

    def compress_build_tools(self, delete: bool = True) -> None:
        """
        Compress the cloned build_tools directory into a zip archive.

        :param delete: Delete source directory after compression
        """
        self._compress(self.local_path.build_tools_path, self.local_path.build_tools_archive, delete=delete)

    def compress_office_js_api(self, delete: bool = True) -> None:
        """
        Compress the cloned office-js-api directory into a zip archive.

        :param delete: Delete source directory after compression
        """
        self._compress(self.local_path.office_js_api_path, self.local_path.office_js_api_archive, delete=delete)

    @staticmethod
    def _compress(src_dir: str, archive_path: str, delete: bool) -> None:
        """
        Pack ``src_dir`` into ``archive_path`` removing previous archive if present.

        :param src_dir: Source directory to compress
        :param archive_path: Destination archive path
        :param delete: Delete source directory after compression
        """
        print(f"[blue]|INFO| Compressing {src_dir} to {archive_path}")
        if isfile(archive_path):
            File.delete(archive_path, stdout=False)

        File.compress(src_dir, archive_path=archive_path, delete=delete, progress_bar=False)

    def configure(self):
        data = File.read_json(self.local_path.docbuilder_config)
        data['branch'] = self._get_branch()
        data['build'] = self._get_build()
        File.write_json(self.local_path.docbuilder_config, data=data, indent=2)

    def _get_branch(self):
        branch = self.version.get_branch()
        if branch in ['hotfix', 'release']:
            return f'{branch}/v{self.version.without_build}'
        return branch

    def _get_build(self) -> str:
        if self.version.build:
            return f"{self.version.build}"
        return 'latest'
