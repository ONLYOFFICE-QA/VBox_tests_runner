# -*- coding: utf-8 -*-
"""
VBox Tests Runner - Automated testing framework for VirtualBox environments.

This module provides invoke tasks for running automated tests on VirtualBox VMs,
including desktop tests, builder tests, and scheduled test execution.

Usage examples:
    # Run desktop tests manually:
    invoke desktop-test --version="9.0.4" --telegram

    # Run builder tests manually:
    invoke builder-test --version="9.0.4" --connect-portal

    # Start scheduled test runner (runs every 30 minutes between 2 AM and 3 PM):
    invoke scheduled-tests

    # Start scheduled test runner with custom schedule:
    invoke scheduled-tests --start-hour=1 --end-hour=16 --interval-minutes=60

    # Check package availability:
    invoke check-package --version="9.0.4" --name="desktop"

    # Get latest version:
    invoke get-versions --version-base="9.0.4" --name="builder"
"""
from os import getcwd, system
from os.path import isfile, join
from typing import Optional, Union, List
import ast

from elevate import elevate
from host_tools import Process, Service
from host_tools.utils import Dir
from invoke import task
from rich import print
from rich.prompt import Prompt
from vboxwrapper import Vbox, VirtualMachine

import tests.multiprocessing as multiprocess
from frameworks import PackageURLChecker, VmManager, TestScheduler
from frameworks.DepTests import DocBuilder
from tests import (
    BuilderReportSender,
    BuilderTestData,
    BuilderTests,
    DesktopReport,
    DesktopTest,
    DesktopTestData,
)


@task
def scheduled_tests(
    c,
    start_hour: int = None,
    end_hour: int = None,
    interval_minutes: int = None,
    base_version: str = None,
    max_builds: int = None,
):
    """
    Run scheduled version checking and testing every 30 minutes between 2 AM and 3 PM.

    This task sets up a scheduler that:
    - Checks for new versions every 30 minutes
    - Only runs between 2 AM and 3 PM
    - Automatically runs builder and desktop tests for new versions
    - Sends results to report portal

    :param c: Context (invoke requirement)
    :param start_hour: Start hour for checking (default: 2 AM)
    :param end_hour: End hour for checking (default: 3 PM)
    :param interval_minutes: Check interval in minutes (default: 30)
    """
    scheduler = TestScheduler()
    scheduler.start_scheduled_tests(
        start_hour=start_hour,
        end_hour=end_hour,
        interval_minutes=interval_minutes,
        base_version=base_version,
        max_builds=max_builds,
    )


@task
def tested_versions_status(c):
    """
    Show the status of tested versions and scheduler configuration.

    :param c: Context (invoke requirement)
    """
    scheduler = TestScheduler()
    status = scheduler.get_tested_versions_status()
    print(status)


@task
def clear_tested_versions(c, confirm: bool = False):
    """
    Clear the cache of tested versions.

    :param c: Context (invoke requirement)
    :param confirm: Skip confirmation prompt if True
    """
    if not confirm:
        response = Prompt.ask(
            "[red]Are you sure you want to clear all tested versions cache? "
            "This will cause all versions to be retested on next schedule run.[/] (yes/no)",
            default="no",
        )
        if response.lower() not in ["yes", "y"]:
            print("[yellow]Operation cancelled[/]")
            return

    scheduler = TestScheduler()
    if scheduler.clear_tested_versions():
        print("[green]|SUCCESS| Tested versions cache cleared[/]")


@task
def desktop_test(
    c,
    version: Optional[str] = None,
    update_from_version: Optional[str] = None,
    name: Optional[str | List[str]] = None,
    processes: Optional[int] = None,
    telegram: bool = False,
    detailed_telegram: bool = False,
    connect_portal: bool = False,
    custom_config: bool = False,
    headless: bool = False,
    snap: bool = False,
    appimage: bool = False,
    flatpak: bool = False,
    only_portal: bool = False,
    open_retries: Optional[int] = None,
    retest: bool = False,
):
    """
    Run desktop tests and send reports.

    :param c: Context (invoke requirement)
    :param version: Version string to test
    :param update_from_version: Version to update from
    :param name: VM name (optional)
    :param processes: Number of parallel processes
    :param telegram: Send results to Telegram
    :param detailed_telegram: Send detailed results to Telegram
    :param connect_portal: Send results to report portal
    :param custom_config: Use custom configuration file
    :param headless: Run in headless mode
    :param snap: Test snap package
    :param appimage: Test AppImage package
    :param flatpak: Test Flatpak package
    :param open_retries: Number of retries for opening application
    :param retest: Retest failed VMs
    :param only_portal: Only send to portal, do not run tests
    """
    num_processes = int(processes) if processes else 1
    names = _parse_names(name)

    data = DesktopTestData(
        version=version or Prompt.ask("[red]Please enter version"),
        update_from=update_from_version,
        telegram=detailed_telegram,
        config_path=join(
            getcwd(),
            "custom_config.json" if custom_config else "desktop_tests_config.json",
        ),
        custom_config_mode=custom_config,
        snap=snap,
        appimage=appimage,
        flatpak=flatpak,
        open_retries=open_retries or 0,
        retest=retest,
    )

    report = DesktopReport(report_path=data.full_report_path)

    if not only_portal:
        if (
            (num_processes > 1 and not names and len(data.vm_names) > 1)
            or (num_processes > 1 and isinstance(names, list) and len(names) > 1)
            ):
            data.status_bar = False
            if isinstance(names, list):
                print(1)
                data.vm_names = names
            multiprocess.run(DesktopTest, data, num_processes, 10, headless)
        else:
            data.status_bar = True
            for vm in Vbox().check_vm_names(names if isinstance(names, list) else [names] if names else data.vm_names):
                DesktopTest(vm, data).run(headless=headless)

        report.get_full(data.version)

    if only_portal and not isfile(data.full_report_path):
        raise FileNotFoundError(f"Report file {data.full_report_path} not found")

    report.send_to_tg(data=data) if not name and not only_portal and telegram else None
    (
        report.send_to_report_portal(data.portal_project_name, data.package_name)
        if connect_portal or only_portal
        else None
    )

    error_vms = report.get_error_vm_list()
    if len(error_vms) > 0:
        print(f"[red]|ERROR| Tests for the following VMs have errors: {error_vms}")
    else:
        print("[green]All tests passed![/]")


@task
def builder_test(
    c,
    version: Optional[str] = None,
    processes: Optional[int] = None,
    name: Optional[str] = None,
    headless: bool = False,
    connect_portal: bool = False,
    telegram: bool = False,
    only_portal: bool = False,
):
    """
    Run builder tests and send reports.

    :param c: Context (invoke requirement)
    :param version: Version string
    :param processes: Number of parallel processes
    :param name: VM name (optional)
    :param headless: Run in headless mode
    :param connect_portal: Send results to report portal
    :param telegram: Send results to Telegram
    :param only_portal: Only send to portal, do not run tests
    """
    num_processes = int(processes) if processes else 1
    data = BuilderTestData(
        version=version or Prompt.ask("[red]Please enter version"),
        config_path=join(getcwd(), "builder_tests_config.json"),
    )
    report_path = data.full_report_path

    if not only_portal:
        builder = DocBuilder(version=data.version)
        builder.get(
            dep_test_branch=data.dep_test_branch,
            builder_samples_branch=data.document_builder_samples_branch,
        )
        builder.compress_dep_tests(delete=False)
        Dir.delete(builder.local_path.dep_test_path)

        vms = Vbox().check_vm_names([name] if name else data.vm_names)
        if num_processes > 1 and not name and len(vms) > 1:
            data.status_bar = False
            multiprocess.run(BuilderTests, data, num_processes, 10, headless)
        else:
            data.status_bar = True
            for vm in vms:
                BuilderTests(vm, data).run(headless=headless)

    data.report.get_full()

    if only_portal and not isfile(report_path):
        raise FileNotFoundError(f"Report file {report_path} not found")

    report_sender = BuilderReportSender(test_data=data)

    if telegram and not only_portal:
        report_sender.to_telegram()

    if connect_portal or only_portal:
        report_sender.to_report_portal(project_name=data.portal_project_name)


@task
def run_vm(c, name: str = "", headless=False):
    """
    Run a virtual machine and wait for it to be ready.

    :param c: Context (invoke requirement)
    :param name: VM name
    :param headless: Run in headless mode
    """
    vm = VirtualMachine(Vbox().check_vm_names(name))
    vm.run(headless=headless)
    vm.network.wait_up(status_bar=True)
    vm.wait_logged_user(status_bar=True)
    return print(
        f"[green]ip: [red]{vm.network.get_ip()}[/]\nuser: [red]{vm.get_logged_user()}[/]"
    )


@task
def stop_vm(c, name: Optional[str] = None, group_name: Optional[str] = None):
    """
    Stop a virtual machine or a group of virtual machines.

    :param c: Context (invoke requirement)
    :param name: VM name
    :param group_name: Group name
    """
    vms = (
        [VirtualMachine(Vbox().check_vm_names(name))]
        if name
        else [
            VirtualMachine(vm_info[1])
            for vm_info in Vbox().vm_list(group_name=group_name)
        ]
    )

    if not name:
        Prompt.ask(
            f"[red]|WARNING| All running virtual machines "
            f"{('in group ' + group_name) if group_name else ''} will be stopped. Press Enter to continue."
        )

    for vm in vms:
        if vm.power_status():
            print(f"[green]|INFO| Shutting down the virtual machine: [red]{vm.name}[/]")
            vm.stop()


@task
def vm_list(c, group_name: Optional[str] = None):
    """
    List virtual machines or virtual machines in a group.

    :param c: Context (invoke requirement)
    :param group_name: Group name (optional)
    """
    vm_names = Vbox().vm_list(group_name)
    print(vm_names)
    return vm_names


@task
def out_info(c, name: str = "", full: bool = False):
    """
    Output information about a virtual machine.

    :param c: Context (invoke requirement)
    :param name: VM name (optional)
    :param full: Output full information if True
    """
    print(VirtualMachine(Vbox().check_vm_names(name)).get_info(machine_readable=full))


@task
def group_list(c):
    """
    List all VM groups.

    :param c: Context (invoke requirement)
    """
    group_names = list(filter(None, Vbox().get_group_list()))
    print(group_names)
    return group_names


@task
def reset_vbox(c, soft: bool = False):
    """
    Restart all VirtualBox processes and services.

    :param c: Context (invoke requirement)
    """
    processes = [
        "VBoxSDS.exe",
        "VBoxSVC.exe",
        "VBoxHeadless.exe",
        "VirtualBox.exe",
        "VBoxManage.exe",
        "VirtualBoxVM",
    ]

    Process.terminate(processes)
    if not soft:
        elevate(show_console=False)

        for process in processes:
            system(f"taskkill /F /IM {process}")

        for service in ["VBoxSDS", "vboxdrv"]:
            Service.restart(service)
        Service.start("VBoxSDS")


@task
def reset_last_snapshot(c, group_name: Optional[str] = None):
    """
    Restore the last snapshot for all VMs in a group.

    :param c: Context (invoke requirement)
    :param group_name: Group name
    """
    if not group_name:
        raise ValueError("Needed specified group name")

    if group_name not in group_list(c):
        raise ValueError(f"Can't found group name: {group_name}")

    for vm_name in vm_list(c, group_name=group_name):
        VirtualMachine(vm_id=vm_name[0]).snapshot.restore()


@task
def download_os(c, cores: Optional[int] = None, all_vm: bool = False):
    """
    Download VM images.

    :param c: Context (invoke requirement)
    :param cores: Number of CPU cores to use (optional)
    :param all_vm: Download all VM images (optional)
    """
    VmManager().download_vm_images(cores=cores, all_vm=all_vm)


@task
def check_package(c, version: str, name: Optional[str] = None):
    """
    Check package URLs for a given version and category.

    :param c: Context (invoke requirement)
    :param version: Version string
    :param name: Category name (optional)
    """
    PackageURLChecker().run(
        versions=version, categories=[name] if name else None, stdout=True
    )


@task
def get_versions(
    c,
    version_base: str,
    name: Optional[str] = None,
    max_builds: int = 200
):
    """
    Get the latest available version and check its package.

    :param c: Context (invoke requirement)
    :param version_base: Base version string
    :param name: Category name (optional)
    :param max_builds: Maximum number of builds to check
    """
    checker = PackageURLChecker()
    checker.check_versions(base_version=version_base, max_builds=max_builds)
    last_version = checker.get_report(base_version=version_base).get_last_exists_version(category=name)
    check_package(c, version=last_version, name=name)
    return last_version


@task
def update_vm_on_host(c, names: Union[str, List[str]] = None, cores: Optional[int] = None):
    """
    Update VM on host.
    :param c: Context (invoke requirement)
    :param names: VM names
    :param cores: Number of CPU cores to use
    """
    updated_vm = VmManager().update_vm_on_host(vm_names=_parse_names(names), cores=cores)
    if updated_vm:
        reset_vbox(c, soft=True)


@task
def update_vm_on_s3(c, names: Union[str, List[str]] = None, cores: Optional[int] = None, ignore_date: bool = False):
    """
    Update VM on S3.

    :param c: Context (invoke requirement)
    :param vm_names: VM names
    :param cores: Number of CPU cores to use
    :param ignore_date: Ignore date comparison
    """
    # # Parse names if it's a string representation of a list
    # if isinstance(names, str) and names.startswith('[') and names.endswith(']'):
    VmManager().update_vm_on_s3(vm_names=_parse_names(names), cores=cores, ignore_date=ignore_date)


def _parse_names(names: str) -> Optional[List[str]]:
    """
    Parse names if it's a string representation of a list.
    :param names: Names string
    :return: List of names
    """
    if isinstance(names, str) and names.startswith('[') and names.endswith(']'):
        try:
            return ast.literal_eval(names)
        except (ValueError, SyntaxError):
            raise ValueError(f"Invalid names: {names}")
    return names

if __name__ == "__main__":
    print(_parse_names('["PopOs22", "Fedora38", "CentOs7"]'))
