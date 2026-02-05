# -*- coding: utf-8 -*-
from os.path import join
from tempfile import gettempdir

from host_tools import HostInfo

from frameworks.test_data.paths import LocalPaths


class ConversionLocalPaths(LocalPaths):
    """
    Defines paths specific to the conversion testing process. Inherits common paths from LocalPaths.
    """
    host = HostInfo()
    x2ttesting_dir = join('C:\\' if host.is_windows else LocalPaths.home_dir, 'scripts', 'opencv_documents_comparer')
    assets_dir = join(x2ttesting_dir, 'assets')
    fonts_dir = join(assets_dir, 'fonts')
