# -*- coding: utf-8 -*-
from os.path import join
from pathlib import Path
from frameworks.paths import LocalPaths


class DesktopLocalPaths(LocalPaths):
    lic_file: str = join(LocalPaths.project_dir, 'test_lic.lickey')
