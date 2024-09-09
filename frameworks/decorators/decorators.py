# -*- coding: utf-8 -*-
from functools import wraps
from multiprocessing import Process
from time import perf_counter, sleep

from rich import print


def singleton(class_):
    __instances = {}

    @wraps(class_)
    def getinstance(*args, **kwargs):
        if class_ not in __instances:
            __instances[class_] = class_(*args, **kwargs)
        return __instances[class_]

    return getinstance

def vm_data_created(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):

        if self.vm.data is None:
            return print("[red]|ERROR| Vm data has not been created, start the vm machine")

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


def highlighter(color: str = 'green'):
    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            print(f'[{color}]-' * 90)
            result = func(*args, **kwargs)
            print(f'[{color}]-' * 90)
            return result

        return inner

    return wrapper


def async_processing(target):
    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            process = Process(target=target)
            process.start()
            result = func(*args, **kwargs)
            process.terminate()
            return result

        return inner

    return wrapper


def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = perf_counter()
        result = func(*args, **kwargs)
        print(f"[green]|INFO| Time existing the function `{func.__name__}`: {(perf_counter() - start_time):.02f}")
        return result

    return wrapper


def memoize(func):
    __cache = {}

    @wraps(func)
    def wrapper(*args, **kwargs):
        key = (args, tuple(kwargs.items()))
        if key not in __cache:
            __cache[key] = func(*args, **kwargs)
        return __cache[key]

    return wrapper
