# -*- coding: utf-8 -*-
from os import getcwd, system
from os.path import join, isfile
from host_tools import Process, Service
from elevate import elevate
from host_tools.utils import Dir
from invoke import task
from rich.prompt import Prompt
from rich import print
from vboxwrapper import VirtualMachine, Vbox

from frameworks import DocBuilder, VmManager, PackageURLChecker
from tests import *

import tests.multiprocessing as multiprocess


@task
def desktop_test(
        c,
        version: str = None,
        update_from_version: str = None,
        name: str = None,
        processes: int = None,
        telegram: bool = False,
        detailed_telegram: bool = False,
        connect_portal: bool = False,
        custom_config: bool = False,
        headless: bool = False,
        snap: bool = False,
        appimage: bool = False,
        flatpak: bool = False,
        open_retries: int = None,
        retest: bool = False,
        only_portal: bool = False
):
    num_processes = int(processes) if processes else 1

    data = DesktopTestData(
        version=version or Prompt.ask('[red]Please enter version'),
        update_from=update_from_version,
        telegram=detailed_telegram,
        config_path=join(getcwd(), 'custom_config.json' if custom_config else 'desktop_tests_config.json'),
        custom_config_mode=custom_config,
        snap=snap,
        appimage=appimage,
        flatpak=flatpak,
        open_retries=open_retries,
        retest=retest
    )

    report = DesktopReport(report_path=data.full_report_path)

    if not only_portal:
        if num_processes > 1 and not name and len(data.vm_names) > 1:
            data.status_bar = False
            multiprocess.run(DesktopTest, data, num_processes, 10, headless)
        else:
            data.status_bar = True
            for vm in Vbox().check_vm_names([name] if name else data.vm_names):
                DesktopTest(vm, data).run(headless=headless)

        report.get_full(data.version)

    if only_portal and not isfile(data.full_report_path):
        raise FileNotFoundError(f"Report file {data.full_report_path} not found")

    report.send_to_tg(data=data) if not name and not only_portal and telegram else None
    report.send_to_report_portal(data.portal_project_name, data.package_name) if connect_portal or only_portal else None

    error_vms = report.get_error_vm_list()
    if len(error_vms) > 0:
        print(f"[red]|ERROR| Tests for the following VMs have errors: {error_vms}")
    else:
        print("[green]All tests passed![/]")

@task
def builder_test(
        c,
        version: str = None,
        processes: int = None,
        name: str = None,
        headless: bool = False,
        connect_portal: bool = False,
        telegram: bool = False,
        only_portal: bool = False
):
    num_processes = int(processes) if processes else 1
    data = BuilderTestData(
        version=version or Prompt.ask('[red]Please enter version'),
        config_path=join(getcwd(), "builder_tests_config.json")
    )
    if not only_portal:
        builder = DocBuilder(version=data.version)
        builder.get(dep_test_branch=data.dep_test_branch, builder_samples_branch=data.document_builder_samples_branch)
        builder.compress_dep_tests(delete=False)
        Dir.delete(builder.local_path.dep_test_path)

        if num_processes > 1 and not name and len(data.vm_names) > 1:
            data.status_bar = False
            multiprocess.run(BuilderTests, data, num_processes, 10, headless)
        else:
            data.status_bar = True
            for vm in Vbox().check_vm_names([name] if name else data.vm_names):
                BuilderTests(vm, data).run(headless=headless)

        data.report.get_full()

    if only_portal and not isfile(data.full_report_path):
        raise FileNotFoundError(f"Report file {data.full_report_path} not found")

    report_sender = BuilderReportSender(report_path=data.report.path)
    report_sender.to_telegram() if telegram and not only_portal else None
    report_sender.to_report_portal(project_name=data.portal_project_name) if connect_portal or only_portal else None


@task
def run_vm(c, name: str = '', headless=False):
    vm = VirtualMachine(Vbox().check_vm_names(name))
    vm.run(headless=headless)
    vm.network.wait_up(status_bar=True)
    vm.wait_logged_user(status_bar=True)
    return print(f"[green]ip: [red]{vm.network.get_ip()}[/]\nuser: [red]{vm.get_logged_user()}[/]")


@task
def stop_vm(c, name: str = None, group_name: str = None):
    vms = [VirtualMachine(Vbox().check_vm_names(name))] if name else [VirtualMachine(vm_info[1]) for vm_info in Vbox().vm_list(group_name=group_name)]

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
def vm_list(c, group_name: str = None):
    vm_names = Vbox().vm_list(group_name)
    print(vm_names)
    return vm_names


@task
def out_info(c, name: str = '', full: bool = False):
    print(VirtualMachine(Vbox().check_vm_names(name)).get_info(machine_readable=full))


@task
def group_list(c):
    group_names = list(filter(None, Vbox().get_group_list()))
    print(group_names)
    return group_names

@task
def reset_vbox(c):
    processes = [
        "VBoxSDS.exe",
        "VBoxSVC.exe",
        "VBoxHeadless.exe",
        "VirtualBox.exe",
        "VBoxManage.exe",
        "VirtualBoxVM"
    ]

    Process.terminate(processes)

    elevate(show_console=False)

    for process in processes:
        system(f"taskkill /F /IM {process}")

    for service in ["VBoxSDS", "vboxdrv"]:
        Service.restart(service)
    Service.start("VBoxSDS")

@task
def reset_last_snapshot(c, group_name: str = None):
    if not group_name:
        raise ValueError("Needed specified group name")

    if group_name not in group_list(c):
        raise ValueError(f"Can't found group name: {group_name}")

    for vm_name in vm_list(c, group_name=group_name):
        VirtualMachine(vm_id=vm_name[0]).snapshot.restore()

@task
def download_os(c, cores: int = None):
    VmManager().download_vm_images(cores=cores)

@task
def check_package(c, version: str, name: str = None):
    PackageURLChecker(version=version).run(categories=[name] if name else None, stdout=True)
