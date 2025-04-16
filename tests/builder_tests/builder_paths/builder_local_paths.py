# -*- coding: utf-8 -*-
from os.path import join
from tempfile import gettempdir

from host_tools import File

from frameworks.test_data.paths import LocalPaths


class BuilderLocalPaths(LocalPaths):
    """
    Defines paths specific to the builder testing process. Inherits common paths from LocalPaths.

    Attributes:
        dep_test (str): Name of the Dep.Tests directory (used as a reference name).
        dep_test_path (str): Full path to the Dep.Tests folder in the system's temporary directory.
        docbuilder_path (str): Full path to the 'docbuilder' directory inside Dep.Tests.
        dep_test_archive (str): Path to the zip archive of Dep.Tests created in the temp directory.
        docbuilder_config (str): Path to the config.json file inside the docbuilder directory.
        document_builder_samples (str): Path to the 'document-builder-samples' directory inside docbuilder.
        builder_report_dir (str): Path to the directory where builder-related test reports will be saved.
    """
    dep_test: str = 'Dep.Tests'
    dep_test_path: str = join(File.unique_name(gettempdir()), dep_test)
    docbuilder_path: str = join(dep_test_path, 'docbuilder')
    dep_test_archive: str = join(LocalPaths.tmp_dir, f"{dep_test}.zip")
    docbuilder_config: str = join(docbuilder_path, 'config.json')
    document_builder_samples: str = join(docbuilder_path, "document-builder-samples")
    builder_report_dir = join(LocalPaths.reports_dir, 'Builder_tests')
