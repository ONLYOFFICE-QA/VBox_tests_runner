# -*- coding: utf-8 -*-
from vboxwrapper import VirtualMachine
import concurrent.futures
from rich import print
from os.path import basename
from pathlib import Path
from host_tools import File
from typing import Any, Dict, List, Optional, Union, Callable

from .vm_updater import VmUpdater
from .config import Config
from ..s3 import S3Vbox


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

        snapshot_uuids_info = {}
        vm_updaters = [VmUpdater(vm_name, self.s3) for vm_name in normalized_names]

        for vm_updater in vm_updaters:
            vm_updater.prepare_vm_for_update()

        self._execute_parallel_vm_updaters(
            vm_updaters,
            'compress',
            cores=cores,
            description="Compressing VMs...",
            method_kwargs={'progress_bar': True}
        )

        upload_paths = self._prepare_upload_file(vm_updaters)
        if upload_paths:
            print(f"[blue]Uploading {len(upload_paths)} VM(s) to S3...[/blue]")
            self.s3.upload_files(upload_paths, delete_exists=True, warning_msg=False, metadata=self._prepare_upload_metadata(vm_updaters))
        else:
            print("[yellow]No VMs to upload[/yellow]")

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

    def get_s3_snapshot_uuid(self, vm_name: str) -> str:
        """
        Get snapshot UUID for VM from S3.
        """
        return self.s3.get_file_metadata(self._get_s3_object_key(vm_name)).get('current_snapshot_uuid', 'NotFound')

    def get_archive_snapshot_uuid(self, vm_name: str) -> str:
        """
        Get snapshot UUID for VM from archive.
        """
        return File.get_archive_comment(str(self.get_archive_path(vm_name)))

    def get_archive_path(self, vm_name: str) -> Path:
        """
        Get archive path for VM.
        """
        return self.download_dir.joinpath(basename(self._get_s3_object_key(vm_name)))

    def get_snapshot_uuid(self, vm: str | VirtualMachine) -> str:
        """
        Get snapshot UUID for VM from snapshot info or current snapshot info.
        """
        if isinstance(vm, str):
            vm = VirtualMachine(vm)
        return vm.snapshot.get_current_snapshot_info().get('uuid')

    def get_vm_dir(self, vm_name: str) -> Path:
        """
        Get VM directory with caching.

        :param vm_name: Name of the virtual machine
        :return: Path to VM directory
        """
        if vm_name not in self._vm_dirs_cache:
            self._vm_dirs_cache[vm_name] = Path(VirtualMachine(vm_name).get_parameter('CfgFile')).parent
        return self._vm_dirs_cache[vm_name]

    def _check_vm_needs_update(self, vm_name: str) -> Optional[Dict[str, Any]]:
        """
        Check if VM needs updating by comparing local and S3 data.

        :param vm_name: Name of the virtual machine
        :return: VM update data if update is needed, None otherwise
        """
        try:
            host_snapshot_uuid = VirtualMachine(vm_name).snapshot.get_current_snapshot_info().get('uuid')
            s3_object_key = self._get_s3_object_key(vm_name)
            s3_snapshot_uuid = self.s3.get_file_metadata(s3_object_key).get('current_snapshot_uuid', 'NotFound')

            if s3_snapshot_uuid != host_snapshot_uuid:
                return {
                    'vm_name': vm_name,
                    'vm_dir': self.get_vm_dir(vm_name),
                    's3_object_key': s3_object_key,
                    's3_snapshot_uuid': s3_snapshot_uuid,
                    'host_snapshot_uuid': host_snapshot_uuid,
                    'download_path': str(self.download_dir.joinpath(basename(s3_object_key)))
                }
            return None
        except Exception as e:
            print(f"[red]Error checking VM {vm_name}: {e}[/red]")
            return None

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

    def _execute_parallel_vm_updaters(
        self,
        vm_updaters: List[VmUpdater],
        method: Callable,
        cores: Optional[int] = None,
        description: Optional[str] = None,
        method_kwargs: Optional[dict] = None
        ) -> List[Any]:
        """
        Execute tasks in parallel and collect results.

        :param vm_updaters: List of VmUpdater objects
        :param method: Method to execute for each VmUpdater
        :param cores: Number of CPU cores to use
        :param description: Optional description for logging
        :return: List of successful results
        """
        if not vm_updaters:
            return []

        if description:
            print(f"[blue]{description}[/blue]")

        with concurrent.futures.ThreadPoolExecutor(max_workers=cores or self.s3.cores) as executor:
            futures = [executor.submit(getattr(vm_updater, method), **(method_kwargs or {})) for vm_updater in vm_updaters]
            return self._process_results(futures)

    def _process_results(self, futures: List[concurrent.futures.Future]) -> List[Any]:
        """
        Process futures results and handle exceptions.

        :param futures: List of Future objects from concurrent executions
        :return: List of results from successful futures
        """
        results = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if result is not None:
                    results.append(result)
            except Exception as e:
                print(f'[bold red]Exception occurred: {e}[/bold red]')

        return results

    def _normalize_vm_names(self, vm_names: Union[str, List[str]]) -> List[str]:
        """
        Normalize VM names to a list format.

        :param vm_names: Single VM name or list of VM names
        :return: List of VM names
        """
        return vm_names if isinstance(vm_names, list) else [vm_names]
