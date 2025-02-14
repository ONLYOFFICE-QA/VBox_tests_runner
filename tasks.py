# -*- coding: utf-8 -*-
from os import getcwd, system
from os.path import join

from invoke import task
from rich.prompt import Prompt
from rich import print

from VBoxWrapper import VirtualMachine, Vbox
from tests.desktop_tests import DesktopTest, DesktopReport, TestData
import tests.desktop_tests.multiprocessing as multiprocess
from host_tools import Process, Service
from elevate import elevate


@task
def desktop_test(
        c,
        version: str = None,
        update_from_version: str = None,
        name: str = None,
        processes: int = None,
        detailed_telegram: bool = False,
        custom_config: bool = False,
        headless: bool = False,
        snap: bool = False,
        appimage: bool = False,
        flatpak: bool = False
):
    num_processes = int(processes) if processes else 1

    data = TestData(
        version=version if version else Prompt.ask('[red]Please enter version'),
        update_from=update_from_version,
        telegram=detailed_telegram,
        config_path=join(getcwd(), 'custom_config.json') if custom_config else join(getcwd(), 'config.json'),
        custom_config_mode=custom_config,
        snap=snap,
        appimage=appimage,
        flatpak=flatpak
    )

    if num_processes > 1 and not name:
        data.status_bar = False
        multiprocess.run(data, num_processes, 10, headless)
    else:
        for vm in Vbox().check_vm_names([name] if name else data.vm_names):
            DesktopTest(vm, data).run(headless=headless)

    report = DesktopReport(report_path=data.full_report_path)
    report.get_full(data.version)
    report.send_to_tg(data=data) if not name else ...


@task
def run_vm(c, name: str = '', headless=False):
    vm = VirtualMachine(Vbox().check_vm_names(name))
    vm.run(headless=headless)
    vm.network.wait_up(status_bar=True)
    vm.wait_logged_user(status_bar=True)
    return print(f"[green]ip: [red]{vm.network.get_ip()}[/]\nuser: [red]{vm.get_logged_user()}[/]")


@task
def stop_vm(c, name: str = None, group_name: str = None):
    if name:
        vm = VirtualMachine(Vbox().check_vm_names(name))
        vm.stop() if vm.power_status() else ...
    else:
        Prompt.ask(
            f"[red]|WARNING| All running virtual machines "
            f"{('in group ' + group_name) if group_name else ''} will be stopped. Press Enter to continue."
        )
        vms_list = Vbox().vm_list(group_name=group_name)
        for vm_info in vms_list:
            virtualmachine = VirtualMachine(vm_info[1])
            if virtualmachine.power_status():
                print(f"[green]|INFO| Shutting down the virtual machine: [red]{vm_info[0]}[/]")
                virtualmachine.stop()


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
        "VirtualBoxVM",
        "VBoxManage.exe",
        "VirtualBox.exe",
        "VBoxHeadless.exe",
        "VBoxSVC.exe",
        "VBoxSDS.exe"
    ]

    Process.terminate(processes)
    elevate(show_console=False)


    for process in processes:
        system(f"taskkill /F /IM {process}")

    Service.restart("VBoxSDS")
    Service.restart("vboxdrv")
    Service.start("VBoxSDS")


@task
def reset_last_snapshot(c, group_name: str = None):
    if not group_name:
        raise ValueError("Needed specified group name")

    if group_name not in group_list(c):
        raise ValueError(f"Can't found group name: {group_name}")

    for vm_name in vm_list(c, group_name=group_name):
        VirtualMachine(vm_id=vm_name[0]).snapshot.restore()
