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
    DEP_TEST_PATH: Path = LocalPaths.TMP_DIR / 'Dep.Tests'
    DOCBUILDER_PATH: Path = DEP_TEST_PATH / 'docbuilder'
    DOCBUILDER_CONFIG: Path = DOCBUILDER_PATH / 'config.json'
    DOCUMENT_BUILDER_SAMPLES: Path = DOCBUILDER_PATH / "document-builder-samples"
    LIC_FILE: Path = LocalPaths.PROJECT_DIR / 'license.xml'
