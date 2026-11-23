# -*- coding: utf-8 -*-
import os
import shutil
import stat
import subprocess
from os.path import isfile, isdir, join
from tempfile import mkdtemp
from typing import Optional

from host_tools import File
from rich import print

from .puppeteer_paths import PuppeteerLocalPaths


class PuppeteerRepo:
    """
    Prepares Dep.Tests on the host for the puppeteer desktop tests: clones Dep.Tests, pp-files into
    ``puppeteer/files`` and document-formats into a temporary folder, keeps only the folders run.py needs
    (``puppeteer`` and ``tools``), puts the format registry into ``puppeteer`` and packs them into one archive
    uploaded to every VM (no git clone happens on the VMs).
    """

    pp_files_dir: str = join('puppeteer', 'files')

    def __init__(self, dep_test_repo: str, pp_files_repo: str, document_formats_repo: str):
        """
        :param dep_test_repo: Dep.Tests repository URL
        :param pp_files_repo: pp-files repository URL, cloned into ``puppeteer/files``
        :param document_formats_repo: document-formats repository URL
        """
        self.dep_test_repo = dep_test_repo
        self.pp_files_repo = pp_files_repo
        self.document_formats_repo = document_formats_repo
        self.local_path = PuppeteerLocalPaths()

    def prepare(
            self,
            dep_test_branch: Optional[str] = None,
            pp_files_branch: Optional[str] = None,
            document_formats_branch: Optional[str] = None,
    ) -> str:
        """
        Clone, assemble and compress Dep.Tests for the VMs.

        :param dep_test_branch: Branch of Dep.Tests, the default branch when None
        :param pp_files_branch: Branch of pp-files, the default branch when None
        :param document_formats_branch: Branch of document-formats, the default branch when None
        :return: Path to the created archive
        """
        work_dir = mkdtemp(prefix='puppeteer_')
        dep_test_path = join(work_dir, 'Dep.Tests')
        pp_files_path = join(dep_test_path, self.pp_files_dir)
        document_formats_path = join(work_dir, 'document-formats')
        try:
            self._clone(self.dep_test_repo, dep_test_path, dep_test_branch)
            self._remove_tree(pp_files_path)
            self._clone(self.pp_files_repo, pp_files_path, pp_files_branch)
            self._clone(self.document_formats_repo, document_formats_path, document_formats_branch)
            self._keep_archive_dirs(dep_test_path)
            self._copy_formats_file(document_formats_path, join(dep_test_path, 'puppeteer'))
            self._remove_git_entries(dep_test_path)
            self._compress(dep_test_path)
        finally:
            self._remove_tree(work_dir)
        return self.local_path.dep_test_archive

    def _clone(self, repo: str, path: str, branch: Optional[str]) -> None:
        print(f"[green]|INFO| Cloning [cyan]{repo}[/] {('branch ' + branch) if branch else ''} to [cyan]{path}[/]")
        self._git('clone', '--depth', '1', *(['-b', branch] if branch else []), repo, path)

    def _keep_archive_dirs(self, dep_test_path: str) -> None:
        """Remove everything at the top of the clone but ``archive_dirs`` (docbuilder, standardtester, ...)."""
        for name in self.local_path.archive_dirs:
            if not isdir(join(dep_test_path, name)):
                raise FileNotFoundError(f"[red]|ERROR| Dep.Tests has no '{name}' folder: {dep_test_path}")

        for entry in os.scandir(dep_test_path):
            if entry.name in self.local_path.archive_dirs:
                continue
            if entry.is_dir(follow_symlinks=False):
                self._remove_tree(entry.path)
            else:
                os.remove(entry.path)

    def _copy_formats_file(self, document_formats_path: str, puppeteer_path: str) -> None:
        source = join(document_formats_path, self.local_path.formats_file_name)
        if not isfile(source):
            raise FileNotFoundError(f"[red]|ERROR| Format registry not found: {source}")
        shutil.copyfile(source, join(puppeteer_path, self.local_path.formats_file_name))

    def _remove_git_entries(self, root: str) -> None:
        """Drop .git folders and submodule .git files: the VMs run from an archive, not from a checkout."""
        for current, dirs, files in os.walk(root):
            if '.git' in dirs:
                self._remove_tree(join(current, '.git'))
                dirs.remove('.git')
            if '.git' in files:
                os.remove(join(current, '.git'))

    def _compress(self, dep_test_path: str) -> None:
        if isfile(self.local_path.dep_test_archive):
            File.delete(self.local_path.dep_test_archive, stdout=False)
        print(f"[green]|INFO| Compressing {dep_test_path} to {self.local_path.dep_test_archive}")
        File.compress(dep_test_path, archive_path=self.local_path.dep_test_archive, progress_bar=False)

    @staticmethod
    def _remove_tree(path: str) -> None:
        """Remove a folder, read-only files included (git objects are read-only on Windows)."""
        def make_writable(func, failed_path, _):
            os.chmod(failed_path, stat.S_IWRITE)
            func(failed_path)

        if isdir(path):
            shutil.rmtree(path, onexc=make_writable)

    @staticmethod
    def _git(*args: str) -> None:
        subprocess.run(['git', *args], check=True)
