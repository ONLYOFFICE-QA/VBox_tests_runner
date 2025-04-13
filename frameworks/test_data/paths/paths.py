# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod


class Paths(ABC):

    @property
    @abstractmethod
    def local(self): ...

    @property
    @abstractmethod
    def remote(self): ...
