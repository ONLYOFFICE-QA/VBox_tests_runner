# -*- coding: utf-8 -*-
from functools import wraps
from time import sleep

from vboxwrapper import VirtualMachinException
from rich import print


def class_cache(class_):
    """
    Decorator that caches class instances to implement singleton pattern.

    :param class_: The class to be cached
    :return: Wrapper function that returns cached instances
    """
    __instances = {}

    @wraps(class_)
    def wrapper(*args, **kwargs):
        key = (class_, args, frozenset(kwargs.items()))
        if key not in __instances:
            __instances[key] = class_(*args, **kwargs)
        return __instances[key]

    return wrapper

def vm_data_created(method):
    """
    Decorator to ensure VM data is created before calling the decorated method.

    :param method: The method to be decorated
    :return: Wrapped method that checks for VM data existence
    :raises VirtualMachinException: If VM data has not been created
    """
    @wraps(method)
    def wrapper(self, *args, **kwargs):

        if self.vm.data is None:
            raise VirtualMachinException("Vm data has not been created, Please start the VM before creating data.")

        return method(self, *args, **kwargs)

    return wrapper

def vm_is_turn_on(method):
    """
    Decorator to ensure VM is powered on before calling the decorated method.

    :param method: The method to be decorated
    :return: Wrapped method that checks VM power status
    :raises VirtualMachinException: If virtual machine is not turned on
    """
    @wraps(method)
    def wrapper(self, *args, **kwargs):

        if not self.vm.power_status():
            raise VirtualMachinException("Virtual machine is not turned on. Please start the VM before creating data.")

        return method(self, *args, **kwargs)

    return wrapper

def retry(
        max_attempts: int = 3,
        interval: int | float = 0,
        stdout: bool = True,
        exception: bool = True,
        exception_type: object | tuple = None
):
    """
    Decorator to retry function execution on exception with configurable parameters.

    :param max_attempts: Maximum number of retry attempts
    :param interval: Interval between retry attempts in seconds
    :param stdout: Whether to print exception messages to stdout
    :param exception: Whether to raise exception after max attempts
    :param exception_type: Specific exception type(s) to catch
    :return: Decorated function with retry logic
    """
    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            for i in range(max_attempts):
                try:
                    result = func(*args, **kwargs)
                except exception_type if exception_type else Exception as e:
                    print(f"[cyan] |INFO| Exception when '{func.__name__}'. Try: {i + 1} of {max_attempts}.")
                    print(f"[red]|WARNING| Error: {e}[/]") if stdout else ...
                    sleep(interval)
                else:
                    return result
            print(f"[bold red]|ERROR| The function: '{func.__name__}' failed in {max_attempts} attempts.")
            if exception:
                raise

        return inner

    return wrapper
