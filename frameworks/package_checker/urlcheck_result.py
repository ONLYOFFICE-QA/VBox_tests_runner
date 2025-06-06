# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Optional


@dataclass
class URLCheckResult:
    version: str
    category: str
    name: str
    url: str
    exists: Optional[bool]
    status_code: Optional[int] = None
    error: Optional[str] = None