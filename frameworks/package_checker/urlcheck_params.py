# -*- coding: utf-8 -*-
from dataclasses import dataclass


@dataclass
class URLCheckParams:
    version: str
    build: int
    category: str
    name: str
    url: str
