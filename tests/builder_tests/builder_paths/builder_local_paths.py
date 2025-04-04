# -*- coding: utf-8 -*-
from pathlib import Path

from frameworks.paths import LocalPaths


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
    dep_test_path: Path = LocalPaths.tmp_dir / dep_test
    docbuilder_path: Path = dep_test_path / 'docbuilder'
    dep_test_archive: Path = LocalPaths.tmp_dir / f"{dep_test}.zip"
    docbuilder_config: Path = docbuilder_path / 'config.json'
    document_builder_samples: Path = docbuilder_path / "document-builder-samples"
    lic_file: Path = LocalPaths.project_dir / 'license.xml'
