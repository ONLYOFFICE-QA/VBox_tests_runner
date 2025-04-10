# -*- coding: utf-8 -*-
from os.path import join
from pathlib import Path
from tempfile import gettempdir

from host_tools import File

from frameworks.test_data.paths import LocalPaths


class BuilderLocalPaths(LocalPaths):
    """
    Defines paths specific to the build process, inheriting base paths.

    Attributes:
        DEP_TEST_PATH (Path): Path to Dep.Tests in the temporary directory.
        DOCBUILDER_PATH (Path): Path to docbuilder inside Dep.Tests.
        DOCBUILDER_CONFIG (Path): Path to config.json inside docbuilder.
        DOCUMENT_BUILDER_SAMPLES (Path): Path to document-builder-samples inside docbuilder.
        LIC_FILE (Path): Path to license.xml in the project directory.
    """
    dep_test: str = 'Dep.Tests'
    dep_test_path: str = join(File.unique_name(gettempdir()), dep_test)
    docbuilder_path: str = join(dep_test_path, 'docbuilder')
    dep_test_archive: str = join(LocalPaths.tmp_dir, f"{dep_test}.zip")
    docbuilder_config: str = join(docbuilder_path, 'config.json')
    document_builder_samples: str = join(docbuilder_path, "document-builder-samples")
    lic_file: str = join(LocalPaths.project_dir, 'license.xml')
    builder_report_dir = join(LocalPaths.reports_dir, 'Builder_tests')
