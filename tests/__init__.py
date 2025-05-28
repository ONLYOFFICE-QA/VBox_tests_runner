# -*- coding: utf-8 -*-
from .builder_tests import BuilderTests
from .builder_tests import BuilderTestData
from .builder_tests import BuilderReportSender

from .desktop_tests import DesktopTest
from .desktop_tests import DesktopTestData
from .desktop_tests import DesktopReport

__all__ = [
    "BuilderTests",
    "BuilderTestData",
    "BuilderReportSender",
    "DesktopTest",
    "DesktopTestData",
    "DesktopReport"
]
