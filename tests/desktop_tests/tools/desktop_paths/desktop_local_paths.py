# -*- coding: utf-8 -*-
from pathlib import Path
from frameworks.paths import LocalPaths


class DesktopLocalPaths(LocalPaths):
    lic_file: Path = LocalPaths.project_dir / 'test_lic.lickey'
