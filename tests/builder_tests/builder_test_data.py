# -*- coding: utf-8 -*-
from dataclasses import dataclass

from frameworks.TestData import TestData


@dataclass
class BuilderTestData(TestData):
    version: str

    def __post_init__(self):
        ...
