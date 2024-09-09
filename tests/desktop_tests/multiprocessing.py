# -*- coding: utf-8 -*-
import time
import concurrent.futures

from .tools import TestData
from tests.desktop_tests import DesktopTest


def run_test(vm_name, data, headless):
    DesktopTest(vm_name=vm_name, test_data=data, vm_cpus=4, vm_memory=3096).run(headless=headless)


def run(data: TestData, max_processes: int = 1, vm_startup_delay: int | float = 0, headless: bool = False):
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_processes) as executor:
        futures = []
        for vm_name in data.vm_names:
            futures.append(executor.submit(run_test, vm_name, data, headless))
            time.sleep(vm_startup_delay)  # Adding delay before starting the next VM

        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error occurred: {e}")
