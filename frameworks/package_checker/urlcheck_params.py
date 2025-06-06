# -*- coding: utf-8 -*-
from dataclasses import dataclass


@dataclass
class URLCheckParams:
    version: str
    category: str
    name: str
    url: str
