# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Optional
from host_tools import File
from vboxwrapper import VirtualMachine
from rich import print
from ..s3 import S3Vbox



class VmUpdater:
    """
    Updater for VM operations.

    Handles updating VM operations.
    """

    def __init__(self, vm_name: str, s3: S3Vbox):
        """
        Initialize VmUpdater.
        """
        self.s3 = s3
        self.vm = VirtualMachine(vm_name)
        self.download_dir = Path(self.s3.config.download_dir)
        self.s3_object_key = f"{self.vm.name}.zip"
        self.__current_snapshot_uuid = None
        self.__archive_path = None
        self.__archive_snapshot_uuid = None
        self.__vm_dir = None

    @property
    def vm_dir(self) -> Path:
        """
        Get VM directory for VM.
        """
        if self.__vm_dir is None:
            self.__vm_dir = Path(self.vm.get_parameter('CfgFile')).parent
        return self.__vm_dir

    @property
    def current_snapshot_uuid(self) -> Optional[str]:
        """
        Get current snapshot UUID for VM.
        """
        if self.__current_snapshot_uuid is None:
            self.__current_snapshot_uuid = self.vm.snapshot.get_current_snapshot_info().get('uuid')
        return self.__current_snapshot_uuid

    @property
    def archive_path(self) -> Path:
        """
        Get archive path for VM.
        """
        if self.__archive_path is None:
            self.__archive_path = self.download_dir.joinpath(self.s3_object_key)
        return self.__archive_path

    @property
    def archive_snapshot_uuid(self) -> Optional[str]:
        """
        Get archive snapshot UUID for VM.
        """
        if self.__archive_snapshot_uuid is None:
            self.__archive_snapshot_uuid = File.get_archive_comment(str(self.archive_path))
        return self.__archive_snapshot_uuid

    def prepare_vm_for_update(self) -> None:
        """
        Prepare VM for update on S3 by stopping, restoring snapshot and compressing.

        :param vm_name: Name of the virtual machine
        :return: Path to created archive if successful, None otherwise
        """
        if self.vm.power_status():
            self.vm.stop()
        self.vm.snapshot.restore()
        print(f"[green]|INFO| Prepared {self.vm.name} current snapshot uuid {self.current_snapshot_uuid} for update on S3|[/green]")

    def compress(self, progress_bar: bool = False) -> None:
        """
        Compress VM directory to archive.

        :param vm_name: Name of the virtual machine
        :return: Path to created archive if successful, None otherwise
        """
        if not self.archive_path.is_file() or self.archive_snapshot_uuid != self.current_snapshot_uuid:
            archive_path = str(self.archive_path)
            File.delete(archive_path, stdout=False, stderr=False)
            File.compress(str(self.vm_dir), archive_path, progress_bar=progress_bar, comment=self.current_snapshot_uuid)
        else:
            print(f"[magenta]|INFO| Snapshot UUID already exists for {self.vm.name} in host {self.archive_path}[/magenta]")
