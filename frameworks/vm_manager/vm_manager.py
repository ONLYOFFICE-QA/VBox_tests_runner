# -*- coding: utf-8 -*-
from vboxwrapper import VirtualMachine
from rich import print
from os.path import basename
from pathlib import Path
from .config import Config
from ..s3 import S3Vbox
from host_tools import File


class VmManager:
    """
    Manager for VM image downloads and configuration.

    Handles downloading VM images from S3 storage and managing
    virtual machine configurations for testing environments.
    """
    vm_dirs = {}

    def __init__(self):
        """
        Initialize VmManager with configuration and testing hosts.
        """
        self.config = Config()
        self.testing_hosts = self.config.get_all_hosts()
        self.s3 = S3Vbox()
        self.download_dir = Path(self.s3.config.download_dir)

    def get_data_file(self, vm_name: str) -> Path:
        """
        Get data file for VM.
        """
        return self.get_vm_dir(vm_name).joinpath(self.config.data_file_name)

    def write_data_file(self, vm_name: str, data: str) -> None:
        """
        Write data to data file for VM.
        """
        self.get_data_file(vm_name).write_text(str(data), encoding='utf-8')

    def get_vm_data(self, vm_name: str) -> dict:
        """
        Get VM data from S3 storage.
        """
        data_file =  self.get_data_file(vm_name)
        return data_file.read_text().strip() if data_file.is_file() else None

    def download_vm_images(self, cores: int = None, download_dir: str = None):
        """
        Download VM images from S3 storage.

        :param cores: Number of CPU cores to use for download
        :param download_dir: Directory to download images to
        """
        s3 = S3Vbox(cores=cores) if cores else self.s3
        s3.download(download_dir=download_dir, download_files=self._get_s3_object_keys())

    def update_vm(self, vm_name: str):
        """
        Update VM directories and metadata if needed.

        :param vm_name: Name of the virtual machine to update
        :return: True if VM was updated, False if no update was needed
        """
        vm_dir = self.get_vm_dir(vm_name)
        vm_data = self.get_vm_data(vm_name)
        s3_object_key = self._get_s3_object_key(vm_name)
        s3_vm_data = str(self.s3.get_file_data(s3_object_key))

        if s3_vm_data != vm_data:
            download_path = str(self.download_dir.joinpath(basename(s3_object_key)))
            File.delete(download_path, stdout=False)
            print(self.s3.download_file(s3_object_key, download_path))
            File.delete(str(vm_dir), stdout=False, stderr=False)
            File.unpacking(download_path, str(vm_dir), stdout=False)
            self._fix_unpacking_duplication(vm_dir)
            self.write_data_file(vm_name, s3_vm_data)


    def get_vm_dir(self, vm_name: str) -> Path:
        """
        Get VM directory.
        """
        if vm_name not in self.vm_dirs:
            # self.vm_dirs[vm_name] = Path(r"D:\test\Alt10") # TODO: remove this
            self.vm_dirs[vm_name] = Path(VirtualMachine(vm_name).get_parameter('CfgFile')).parent
        return self.vm_dirs[vm_name]

    def _get_s3_object_keys(self) -> list:
        """
        Get S3 object keys for VM images.

        :return: List of S3 object keys for VM ZIP files
        """
        return [self._get_s3_object_key(name) for name in self.testing_hosts]

    def _get_s3_object_key(self, vm_name: str) -> str:
        """
        Get S3 object key for VM image.
        """
        return f"{vm_name}.zip"

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
