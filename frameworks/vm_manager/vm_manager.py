# -*- coding: utf-8 -*-
from rich.console import Console
from vboxwrapper import VirtualMachine
import concurrent.futures
from os.path import basename
from pathlib import Path
from host_tools import File
from typing import Any, Dict, List, Optional, Union, Callable

from .vm_updater import VmUpdater
from .config import Config
from ..s3 import S3Vbox
from ..console import print

class VmManager:
    """
    Manager for VM image downloads and configuration.

    Handles downloading VM images from S3 storage and managing
    virtual machine configurations for testing environments.
    """
    # Constants
    DATA_FILE_ENCODING = 'utf-8'
    ZIP_EXTENSION = '.zip'

    def __init__(self):
        """
        Initialize VmManager with configuration and testing hosts.
        """
        self.console = Console()
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
        cores: Optional[int] = None
        ) -> None:
        """
        Update VM directories and metadata on S3.

        :param vm_names: Name(s) of the virtual machine(s) to update
        :param cores: Number of CPU cores to use for parallel processing
        """
        normalized_names = self._normalize_vm_names(vm_names or self.testing_hosts)
        print(f"[blue]Preparing {len(normalized_names)} VM(s) for S3 update...[/blue]")

        vm_updaters = self._get_vm_updaters(normalized_names)

        for vm_updater in vm_updaters:
            vm_updater.prepare_vm_for_update()

        if all(not vm_updater.is_needs_upload() for vm_updater in vm_updaters):
            return print("[green]All VMs are up to date on S3.[/green]")

        if any(vm_updater.is_needs_compress() for vm_updater in vm_updaters):
            self._execute_parallel_methods(
                vm_updaters,
                'compress',
                cores=cores,
                description="Compressing VMs..."
            )

        self._execute_parallel_methods(
                vm_updaters,
                'upload',
                cores=cores,
                description="Uploading VMs to S3...",
            )
        if all(vm_updater.uploaded for vm_updater in vm_updaters):
            print("[green]VMs updated successfully on S3[/green]")
        else:
            for vm_updater in vm_updaters:
                if not vm_updater.uploaded:
                    print(f"[cyan]|INFO| No {vm_updater.vm.name} uploaded on S3[/cyan]")

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

        # Step 1: Check which VMs need updating
        vms_to_update = self._execute_parallel_tasks(
            self._check_vm_needs_update,
            normalized_names,
            cores,
            f"Checking update requirements for {len(normalized_names)} VM(s)..."
        )

        if not vms_to_update:
            return print("[green]All VMs are up to date.[/green]")

        print(f"[yellow]Found {len(vms_to_update)} VM(s) that need updating.[/yellow]")

        # Step 2: Download required files
        downloaded_vms = self._execute_parallel_tasks(
            self._download_vm,
            vms_to_update,
            cores,
            "Downloading VM files..."
        )

        # Step 3: Unpack and install VMs
        self._execute_parallel_tasks(
            self._unpack_vm,
            downloaded_vms,
            cores,
            "Unpacking and installing VMs..."
        )

        print(f"[green]Successfully updated {len(vms_to_update)} VM(s).[/green]")

    def _get_vm_updaters(self, vm_names: List[str]) -> List[VmUpdater]:
        """
        Get VM updaters for list of VM names.
        """
        return [VmUpdater(vm_name, self.s3) for vm_name in vm_names]

    def _download_vm(self, vm_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Download VM file from S3.

        :param vm_data: VM data dictionary with download information
        :return: VM data if download successful, None otherwise
        """
        if not vm_data:
            return None

        try:
            vm_name = vm_data['vm_name']
            download_path = vm_data['download_path']
            s3_object_key = vm_data['s3_object_key']

            File.delete(download_path, stdout=False)
            print(f"[blue]Downloading {vm_name}...[/blue]")
            result = self.s3.download_file(s3_object_key, download_path)
            if result:
                print(f"[green]Downloaded {vm_name} successfully[/green]")
            return vm_data
        except Exception as e:
            print(f"[red]Error downloading VM {vm_data.get('vm_name', 'unknown')}: {e}[/red]")
            return None

    def _unpack_vm(self, vm_data: Dict[str, Any]) -> bool:
        """
        Unpack and install VM from downloaded archive.

        :param vm_data: VM data dictionary with installation information
        :return: True if successful, False otherwise
        """
        if not vm_data:
            return False

        try:
            vm_name = vm_data['vm_name']
            vm_dir = vm_data['vm_dir']
            download_path = vm_data['download_path']

            print(f"[blue]Unpacking {vm_name}...[/blue]")
            File.delete(str(vm_dir), stdout=False, stderr=False)
            File.unpacking(download_path, str(vm_dir), stdout=False)
            self._fix_unpacking_duplication(vm_dir)
            print(f"[green]Installed {vm_name}[/green]")
            return True
        except Exception as e:
            print(f"[red]Error unpacking VM {vm_data.get('vm_name', 'unknown')}: {e}[/red]")
            return False

    def _prepare_vm_for_update_on_s3(self, vm_name: str) -> Optional[str]:
        """
        Prepare VM for update on S3 by stopping, restoring snapshot and compressing.

        :param vm_name: Name of the virtual machine
        :return: Path to created archive if successful, None otherwise
        """
        try:
            print(f"[blue]Preparing {vm_name} for S3 upload...[/blue]")
            vm = VirtualMachine(vm_name)
            if vm.power_status():
                vm.stop()
            vm.snapshot.restore()
            return self.get_snapshot_uuid(vm)
        except Exception as e:
            print(f"[red]Failed to prepare VM {vm_name} for S3 upload: {e}[/red]")
            return None

    def _compress_vm(self, vm_name: str, progress_bar: bool = False, snapshot_uuids_info: Optional[dict] = None) -> Optional[dict]:
        """
        Compress VM directory to archive.

        :param vm_name: Name of the virtual machine
        :return: Path to created archive if successful, None otherwise
        """
        try:
            snapshot_uuid = snapshot_uuids_info.get(vm_name)
            archive_path = self.get_archive_path(vm_name)
            if not archive_path.is_file() or self.get_archive_snapshot_uuid(vm_name) != snapshot_uuid:
                archive_path = str(archive_path)
                File.delete(archive_path, stdout=False, stderr=False)
                File.compress(str(self.get_vm_dir(vm_name)), archive_path, progress_bar=progress_bar, comment=snapshot_uuid)
            else:
                print(f"[magenta]|INFO| Snapshot UUID already exists for {vm_name} in host {archive_path}[/magenta]")
            return {
                'archive_path': str(archive_path),
                'vm_name': vm_name,
                'current_snapshot_uuid': snapshot_uuid
            }
        except Exception as e:
            print(f"[red]Failed to compress VM {vm_name}: {e}[/red]")
            return None

    def _prepare_upload_file(self, vm_updaters: List[VmUpdater]) -> list[str]:
        """
        Prepare archive for upload.
        """
        paths = []
        for vm_updater in vm_updaters:
            if vm_updater.archive_path.is_file():
                s3_metadata = self.s3.get_file_metadata(vm_updater.s3_object_key)
                if s3_metadata.get('current_snapshot_uuid', 'NotFound') != vm_updater.current_snapshot_uuid:
                    paths.append(vm_updater.archive_path)
                else:
                    print(f"[magenta]|INFO| Snapshot UUID already exists for {vm_updater.vm.name}[/magenta]")
        return paths

    def _prepare_upload_metadata(
        self,
        vm_updaters: List[VmUpdater]
        ) -> Dict[str, Dict[str, str]]:
        """
        Prepare metadata for S3 upload with snapshot UUIDs.

        :param upload_paths: List of paths to archives for upload
        :return: Metadata dictionary mapping file basename to snapshot UUID
        """
        return {
            basename(vm_updater.archive_path): {
                'current_snapshot_uuid': vm_updater.current_snapshot_uuid
            }
            for vm_updater in vm_updaters
        }

    def _get_s3_object_keys(self) -> List[str]:
        """
        Get S3 object keys for all configured VM images.

        :return: List of S3 object keys for VM ZIP files
        """
        return [self._get_s3_object_key(name) for name in self.testing_hosts]

    def _get_s3_object_key(self, vm_name: str) -> str:
        """
        Get S3 object key for VM image.

        :param vm_name: Name of the virtual machine
        :return: S3 object key for the VM archive
        """
        return f"{vm_name}{self.ZIP_EXTENSION}"

    def _fix_unpacking_duplication(self, vm_dir: Path) -> None:
        """
        Fix directory duplication after unpacking.

        If archive contains a folder with the same name as the VM directory,
        move its contents to the parent directory and remove the empty folder.

        :param vm_dir: Target VM directory path
        """
        duplicated_dir = vm_dir / vm_dir.name

        if duplicated_dir.exists() and duplicated_dir.is_dir():
            print(f"[yellow]Found duplicated directory: {duplicated_dir}[/yellow]")

            for item in duplicated_dir.iterdir():
                destination = vm_dir / item.name
                if destination.exists():
                    print(f"[yellow]Removing existing: {destination}[/yellow]")
                    File.delete(str(destination), stdout=False)

                print(f"[green]Moving: {item} -> {destination}[/green]")
                File.move(str(item), str(destination), stdout=False)

            File.delete(str(duplicated_dir), stdout=False)
            print(f"[green]Fixed duplication: items moved and empty directory removed[/green]")

    def _execute_parallel_methods(
        self,
        objects: List[object],
        method: str,
        cores: Optional[int] = None,
        description: Optional[str] = None,
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

        if description:
            print(f'[cyan]{description}[/cyan]')

        with self.console.status(f'[cyan]{description or ""}[/cyan]') as status:
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

    def _normalize_vm_names(self, vm_names: Union[str, List[str]]) -> List[str]:
        """
        Normalize VM names to a list format.

        :param vm_names: Single VM name or list of VM names
        :return: List of VM names
        """
        return vm_names if isinstance(vm_names, list) else [vm_names]
