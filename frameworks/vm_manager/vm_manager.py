# -*- coding: utf-8 -*-
from vboxwrapper import VirtualMachine
import concurrent.futures
from os.path import basename
from pathlib import Path
from host_tools import File
from typing import Any, Dict, List, Optional, Union, Callable

from .vm_updater import VmUpdater
from .config import Config
from ..s3 import S3Vbox
from ..console import MyConsole

console = MyConsole().console
print = console.print

class VmManager:
    """
    Manager for VM image downloads and configuration.

    Handles downloading VM images from S3 storage and managing
    virtual machine configurations for testing environments.
    """
    # Constants
    SEPARATOR_LINE = f"|{'-' * 100}|"

    def __init__(self):
        """
        Initialize VmManager with configuration and testing hosts.
        """
        self.config = Config()
        self.testing_hosts = self.config.get_all_hosts()
        self.s3 = S3Vbox()
        self.download_dir = Path(self.s3.config.download_dir)
        self._vm_dirs_cache: Dict[str, Path] = {}

    def download_vm_images(self, cores: Optional[int] = None, download_dir: Optional[str] = None, all_vm: bool = False) -> bool:
        """
        Download VM images from S3 storage.

        :param cores: Number of CPU cores to use for download
        :param download_dir: Directory to download images to
        :return: True if successful, False otherwise
        """
        try:
            s3 = S3Vbox(cores=cores) if cores else self.s3
            s3.download(download_dir=download_dir, download_files=self._get_s3_object_keys() if not all_vm else None)
            print("[green]VM images download completed[/green]")
            return True
        except Exception as e:
            print(f"[red]Failed to download VM images: {e}[/red]")
            return False

    def update_vm_on_s3(
        self,
        vm_names: Union[str, List[str]] = None,
        cores: Optional[int] = None,
        ignore_date: bool = False
        ) -> None:
        """
        Update VM directories and metadata on S3.

        :param vm_names: Name(s) of the virtual machine(s) to update
        :param ignore_date: Ignore date comparison when checking if VM needs update
        :param cores: Number of CPU cores to use for parallel processing
        """
        normalized_names = self._normalize_vm_names(vm_names or self.testing_hosts)
        vm_updaters = self._get_vm_updaters(normalized_names, ignore_date=ignore_date)
        vm_to_update = [vm_updater for vm_updater in vm_updaters if vm_updater.is_needs_update_on_s3()]

        if not vm_to_update:
            return print("[green]All VMs are up to date on S3.[/green]")

        vm_to_compress = [vm_updater for vm_updater in vm_to_update if vm_updater.is_needs_compress()]
        if vm_to_compress:
            self._prepare_vm_for_compression(vm_to_compress)
            self._execute_parallel_methods(vm_to_compress, 'compress', cores=cores, description="Compressing VMs...")

        self._execute_parallel_methods(vm_to_update, 'upload', cores=cores, description="Uploading VMs to S3...")
        self._print_s3_update_results(vm_to_update, vm_updaters)

    def update_vm_on_host(
        self,
        vm_names: Optional[Union[str, List[str]]] = None,
        cores: Optional[int] = None
        ) -> None:
        """
        Update VM directories and metadata on host in parallel if needed.

        :param vm_names: Name(s) of the virtual machine(s) to update, defaults to all testing hosts
        :param cores: Number of CPU cores to use for parallel processing
        """
        normalized_names = self._normalize_vm_names(vm_names or self.testing_hosts)

        vm_updaters = self._get_vm_updaters(normalized_names)
        vm_to_update = [vm_updater for vm_updater in vm_updaters if vm_updater.is_needs_update_on_host()]

        if not vm_to_update:
            return print("[green]All VMs are up to date on host.[/green]")

        print(f"[yellow]Found {len(vm_to_update)} VM(s) that need updating.[/yellow]")
        self._execute_parallel_methods(vm_to_update, 'download', cores=cores, description="Downloading VM files...")
        self._execute_parallel_methods(vm_to_update, 'unpack', cores=cores, description="Unpacking VMs...")
        print(f"[green]Successfully updated {len(vm_to_update)} VM(s).[/green]")

    def _prepare_vm_for_compression(self, vm_updaters: List[VmUpdater]) -> None:
        """
        Prepare VM for compression.
        """
        print(f"[blue]Preparing {len(vm_updaters)} VM(s) for compression...[/blue]")
        for vm_updater in vm_updaters:
            vm_updater.prepare_vm_for_update()

    def _get_vm_updaters(self, vm_names: List[str], ignore_date: bool = False) -> List[VmUpdater]:
        """
        Get VM updaters for list of VM names.
        """
        return [VmUpdater(vm_name, self.s3, ignore_date=ignore_date) for vm_name in vm_names]

    def _get_s3_object_keys(self) -> List[str]:
        """
        Get S3 object keys for all configured VM images.

        :return: List of S3 object keys for VM ZIP files
        """
        vm_updaters = self._get_vm_updaters(self.testing_hosts)
        return [vm_updater.s3_object_key for vm_updater in vm_updaters]

    def _normalize_vm_names(self, vm_names: Union[str, List[str]]) -> List[str]:
        """
        Normalize VM names to a list format.

        :param vm_names: Single VM name or list of VM names
        :return: List of VM names
        """
        return vm_names if isinstance(vm_names, list) else [vm_names]

    def _print_s3_update_results(
        self,
        vm_updaters_to_update: List[VmUpdater],
        all_vm_updaters: List[VmUpdater]
    ) -> None:
        """
        Print results of S3 update operation.

        :param vm_updaters_to_update: List of VM updaters that were attempted to update
        :param all_vm_updaters: List of all VM updaters including already updated ones
        """
        # Collect results
        successfully_updated = [vm for vm in vm_updaters_to_update if vm.uploaded]
        failed_uploads = [vm for vm in vm_updaters_to_update if not vm.uploaded]

        # Print results
        if not failed_uploads:
            print("[green]|INFO| All VMs updated successfully on S3[/green]")
        else:
            self._print_info_block(
                title=f"Failed uploads: {len(failed_uploads)}",
                items=[vm.vm.name for vm in failed_uploads],
                color="red",
                message_suffix="not uploaded to S3"
            )

        # Print successfully updated VMs
        if successfully_updated:
            self._print_info_block(
                title=f"Successfully updated VMs: {len(successfully_updated)}",
                items=[vm.vm.name for vm in successfully_updated],
                color="green"
            )

        # Print already updated VMs (those that were not in update list)
        already_updated = [vm for vm in all_vm_updaters if vm not in vm_updaters_to_update]
        if already_updated:
            self._print_info_block(
                title=f"Already updated VMs: {len(already_updated)}",
                items=[vm.vm.name for vm in already_updated],
                color="green"
            )

    def _print_info_block(
        self,
        title: str,
        items: List[str],
        color: str = "green",
        message_suffix: str = ""
    ) -> None:
        """
        Print information block with separator lines.

        :param title: Block title
        :param items: List of items to print
        :param color: Color for the output (green, red, etc.)
        :param message_suffix: Additional message suffix for each item
        """
        print(f"[red]{self.SEPARATOR_LINE}[/red]")
        print(f"[{color}]|INFO| {title}[/{color}]")
        for item in items:
            suffix = f" {message_suffix}" if message_suffix else ""
            print(f"[{color}]|INFO| {item}{suffix}[/{color}]")
        print(f"[red]{self.SEPARATOR_LINE}[/red]")

    def _execute_parallel_methods(
        self,
        objects: List[object],
        method: str,
        cores: Optional[int] = None,
        description: Optional[str] = "Processing...",
        method_args: Optional[tuple] = None,
        method_kwargs: Optional[dict] = None
        ) -> List[Any]:
        """
        Execute method in parallel for list of objects and collect results.

        :param objects: List of objects to execute method on
        :param method: Name of the method to execute for each object
        :param cores: Number of CPU cores to use
        :param description: Optional description for logging
        :param method_kwargs: Optional keyword arguments to pass to the method
        :return: List of successful results
        """
        if not objects:
            return []

        with console.status(f'[cyan]{description}[/cyan]') as status:
            with concurrent.futures.ThreadPoolExecutor(max_workers=cores or self.s3.cores) as executor:
                futures = [executor.submit(getattr(obj, method), *(method_args or ()), **(method_kwargs or {})) for obj in objects]
                status.update(self._process_result(futures))

    def _process_result(self, futures: list) -> Any | None:
        """
        Processes the results of futures and handles any exceptions.

        :param future: A Future object from concurrent execution.
        :return: The result of the first successful future, or None if an error occurs.
        """
        for future in concurrent.futures.as_completed(futures):
            try:
                return future.result()
            except Exception as e:
                print(f'[bold red] Exception occurred: {e}')
                return None
        return None
