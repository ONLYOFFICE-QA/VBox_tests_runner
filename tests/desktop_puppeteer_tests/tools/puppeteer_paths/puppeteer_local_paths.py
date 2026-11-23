# -*- coding: utf-8 -*-
from os.path import join

from frameworks.test_data.paths import LocalPaths


class PuppeteerLocalPaths(LocalPaths):
    """
    Host-side paths of the Dep.Tests/puppeteer desktop tests.

    Attributes:
        archive_dirs: Top-level folders of Dep.Tests sent to the VMs: ``puppeteer`` and ``tools``
            (run.py imports ``tools/report_portal`` and ``tools/safe_import`` from the Dep.Tests root).
        dep_test_archive: Zip of ``archive_dirs`` uploaded to every VM.
        formats_file_name: The format registry ``run.py --host native`` reads from disk, put into ``puppeteer``.
        out_archive_name: Zip of ``puppeteer/out`` made on the VM and downloaded by the host.
        report_dir: Root of the local reports of these tests.
    """
    archive_dirs: tuple = ('puppeteer', 'tools')
    dep_test_archive: str = join(LocalPaths.tmp_dir, 'Dep.Tests_puppeteer.zip')
    formats_file_name: str = 'onlyoffice-docs-formats.json'
    out_archive_name: str = 'out.zip'

    report_dir: str = join(LocalPaths.reports_dir, 'Desktop_puppeteer_tests')
