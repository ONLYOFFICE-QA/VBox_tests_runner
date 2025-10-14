# -*- coding: utf-8 -*-
from vboxwrapper import VirtualMachine
import concurrent.futures
from rich import print
from os.path import basename
from pathlib import Path
from host_tools import File
from typing import Any, Dict, List, Optional, Union, Callable

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

    def get_data_file(self, vm_name: str) -> Path:
        """
        Get data file for VM.
        """
        return self.get_vm_dir(vm_name).joinpath(self.config.data_file_name)

    def write_data_file(self, vm_name: str, data: Optional[str] = None) -> bool:
        """
        Write data to data file for VM.

        :param vm_name: Name of the virtual machine
        :param data: Optional data string, if not provided will fetch from S3
        :return: True if successful, False otherwise
        """
        try:
            s3_data = data or str(self.s3.get_file_data(self._get_s3_object_key(vm_name)))
            self.get_data_file(vm_name).write_text(s3_data, encoding=self.DATA_FILE_ENCODING)
            print(f"[green]Updated data file for {vm_name}[/green]")
            return True
        except Exception as e:
            print(f"[red]Failed to write data file for {vm_name}: {e}[/red]")
            return False

    def get_vm_data(self, vm_name: str) -> Optional[str]:
        """
        Get VM data from local data file.

        :param vm_name: Name of the virtual machine
        :return: VM data string if exists, None otherwise
        """
        try:
            data_file = self.get_data_file(vm_name)
            return data_file.read_text(encoding=self.DATA_FILE_ENCODING).strip() if data_file.is_file() else None
        except Exception as e:
            print(f"[red]Failed to read data file for {vm_name}: {e}[/red]")
            return None

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

    def update_vm_on_s3(self, vm_names: Union[str, List[str]], cores: Optional[int] = None) -> None:
        """
        Update VM directories and metadata on S3.

        :param vm_names: Name(s) of the virtual machine(s) to update
        :param cores: Number of CPU cores to use for parallel processing
        """
        normalized_names = self._normalize_vm_names(vm_names)
        print(f"[blue]Preparing {len(normalized_names)} VM(s) for S3 update...[/blue]")

        # Prepare VMs for upload in parallel
        for vm_name in normalized_names:
            self._prepare_vm_for_update_on_s3(vm_name)

        # Compress VMs in parallel
        upload_paths = self._execute_parallel_tasks(
            self._compress_vm,
            normalized_names,
            cores,
            "Compressing VMs..."
        )

        if upload_paths:
            print(f"[blue]Uploading {len(upload_paths)} VM(s) to S3...[/blue]")
            self.s3.upload_files(upload_paths, delete_exists=True, warning_msg=False)
            self.update_data_files(vm_names, cores)
            print("[green]S3 update completed successfully[/green]")
        else:
            print("[yellow]No VMs to upload[/yellow]")

    def update_data_files(self, vm_names: Union[str, List[str]], cores: Optional[int] = None) -> None:
        """
        Update data files for VMs in parallel.

        :param vm_names: Name(s) of virtual machines to update data files for
        :param cores: Number of CPU cores to use for parallel processing
        """
        normalized_names = self._normalize_vm_names(vm_names)

        self._execute_parallel_tasks(
            self.write_data_file,
            normalized_names,
            cores,
            f"Updating data files for {len(normalized_names)} VM(s)..."
        )

        print(f"[green]Data files updated for {len(normalized_names)} VM(s)[/green]")

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

    def _check_vm_needs_update(self, vm_name: str) -> Optional[Dict[str, Any]]:
        """
        Check if VM needs updating by comparing local and S3 data.

        :param vm_name: Name of the virtual machine
        :return: VM update data if update is needed, None otherwise
        """
        try:
            vm_data = self.get_vm_data(vm_name)
            s3_object_key = self._get_s3_object_key(vm_name)
            s3_vm_data = str(self.s3.get_file_data(s3_object_key))

            if s3_vm_data != vm_data:
                return {
                    'vm_name': vm_name,
                    'vm_dir': self.get_vm_dir(vm_name),
                    's3_object_key': s3_object_key,
                    's3_vm_data': s3_vm_data,
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
            s3_vm_data = vm_data['s3_vm_data']

            print(f"[blue]Unpacking {vm_name}...[/blue]")
            File.delete(str(vm_dir), stdout=False, stderr=False)
            File.unpacking(download_path, str(vm_dir), stdout=False)
            self._fix_unpacking_duplication(vm_dir)
            self.write_data_file(vm_name, s3_vm_data)
            print(f"[green]Installed {vm_name}[/green]")
            return True
        except Exception as e:
            print(f"[red]Error unpacking VM {vm_data.get('vm_name', 'unknown')}: {e}[/red]")
            return False


    def get_vm_dir(self, vm_name: str) -> Path:
        """
        Get VM directory with caching.

        :param vm_name: Name of the virtual machine
        :return: Path to VM directory
        """
        if vm_name not in self._vm_dirs_cache:
            self._vm_dirs_cache[vm_name] = Path(VirtualMachine(vm_name).get_parameter('CfgFile')).parent
        return self._vm_dirs_cache[vm_name]


    def _prepare_vm_for_update_on_s3(self, vm_name: str) -> Optional[bool]:
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
            return True
        except Exception as e:
            print(f"[red]Failed to prepare VM {vm_name} for S3 upload: {e}[/red]")
            return None

    def _compress_vm(self, vm_name: str, progress_bar: bool = False) -> Optional[str]:
        """
        Compress VM directory to archive.

        :param vm_name: Name of the virtual machine
        :return: Path to created archive if successful, None otherwise
        """
        try:
            archive_path = str(self.download_dir.joinpath(self._get_s3_object_key(vm_name)))
            File.delete(archive_path, stdout=False, stderr=False)
            File.compress(str(self.get_vm_dir(vm_name)), archive_path, progress_bar=progress_bar)
            return archive_path
        except Exception as e:
            print(f"[red]Failed to compress VM {vm_name}: {e}[/red]")
            return None

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

    def _execute_parallel_tasks(
        self,
        task_func: Callable,
        items: List[Any],
        cores: Optional[int] = None,
        description: Optional[str] = None
        ) -> List[Any]:
        """
        Execute tasks in parallel and collect results.

        :param task_func: Function to execute for each item
        :param items: List of items to process
        :param cores: Number of CPU cores to use
        :param description: Optional description for logging
        :return: List of successful results
        """
        if not items:
            return []

        if description:
            print(f"[blue]{description}[/blue]")

        with concurrent.futures.ThreadPoolExecutor(max_workers=cores or self.s3.cores) as executor:
            futures = [executor.submit(task_func, item) for item in items]
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
