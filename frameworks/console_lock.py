# -*- coding: utf-8 -*-
"""
Shared threading lock for thread-safe console output.

This module provides a single global lock to synchronize
console output across multiple threads and modules.
"""
import threading
from rich import print as rprint

# Global lock for thread-safe console output across all modules
console_lock = threading.Lock()

def print(msg: str) -> None:
    """
    Print message with console lock.
    """
    with console_lock:
        rprint(msg)
