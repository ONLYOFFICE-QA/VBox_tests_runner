# -*- coding: utf-8 -*-
from .builder_tests import BuilderTests
from .builder_tests import BuilderTestData
from .builder_tests import BuilderReportSender

from .desktop_tests import DesktopTest
from .desktop_tests import DesktopTestData
from .desktop_tests import DesktopReport

from .conversion_tests import ConversionTests
from .conversion_tests import ConversionTestData

from .desktop_puppeteer_tests import DesktopPuppeteerTest
from .desktop_puppeteer_tests import PuppeteerTestData
from .desktop_puppeteer_tests import PuppeteerRepo
from .desktop_puppeteer_tests import PuppeteerReport

__all__ = [
    "BuilderTests",
    "BuilderTestData",
    "BuilderReportSender",
    "DesktopTest",
    "DesktopTestData",
    "DesktopReport",
    "ConversionTests",
    "ConversionTestData",
    "DesktopPuppeteerTest",
    "PuppeteerTestData",
    "PuppeteerRepo",
    "PuppeteerReport",
]
