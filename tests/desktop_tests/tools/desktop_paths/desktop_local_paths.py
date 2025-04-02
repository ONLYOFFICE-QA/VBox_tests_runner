# -*- coding: utf-8 -*-
from pathlib import Path
from frameworks.paths import LocalPaths


class DesktopLocalPaths(LocalPaths):
    LIC_FILE: Path = LocalPaths.PROJECT_DIR / 'test_lic.lickey'
