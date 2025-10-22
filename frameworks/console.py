# -*- coding: utf-8 -*-
import threading
from rich import print as rprint
from rich.console import Console
from host_tools import singleton


"""
Shared threading lock for thread-safe console output.

This module provides a single global lock to synchronize
console output across multiple threads and modules.
"""
# Global lock for thread-safe console output across all modules
console_lock = threading.Lock()

def print(msg: str) -> None:
    """
    Print message with console lock.
    """
    with console_lock:
        rprint(msg)

@singleton
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
