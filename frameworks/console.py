# -*- coding: utf-8 -*-
from rich.console import Console

class MyConsole:
    """
    Wrapper class for Rich Console with common functionality.

    Provides easy access to Rich console features like printing and status indicators.
    """

    def __init__(self):
        """
        Initialize MyConsole with Rich Console instance and shortcuts.
        """
        self.console = Console()
        self.print = self.console.print
        self.status = self.console.status
