# -*- coding: utf-8 -*-
from dataclasses import dataclass


@dataclass
class TestData:
    version: str

    def __post_init__(self):
        ...
