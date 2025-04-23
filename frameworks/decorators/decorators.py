# -*- coding: utf-8 -*-
from functools import wraps
from time import sleep

from vboxwrapper import VirtualMachinException
from rich import print


def class_cache(class_):
    __instances = {}

    @wraps(class_)
    def wrapper(*args, **kwargs):
        key = (class_, args, frozenset(kwargs.items()))
        if key not in __instances:
            __instances[key] = class_(*args, **kwargs)
        return __instances[key]

    return wrapper

def vm_data_created(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):

        if self.vm.data is None:
            raise VirtualMachinException("Vm data has not been created, Please start the VM before creating data.")

        return method(self, *args, **kwargs)

    return wrapper

def vm_is_turn_on(method):
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
