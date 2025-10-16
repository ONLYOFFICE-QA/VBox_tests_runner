# -*- coding: utf-8 -*-
from datetime import datetime
from pathlib import Path
import re
from typing import Optional
import zipfile
from host_tools import File
from vboxwrapper import VirtualMachine
from ..s3 import S3Vbox
from ..console import MyConsole

console = MyConsole().console
print = console.print

class VmUpdater:
    """
    Updater for VM operations.

    Handles updating VM operations.
    """
    current_snapshot_uuid_key = 'current_snapshot_uuid'
    current_snapshot_date_key = 'current_snapshot_date'
    zip_extension = '.zip'
    datetime_format = "%Y-%m-%dT%H:%M:%SZ"

    def __init__(self, vm_name: str, s3: S3Vbox, ignore_date: bool = False):
        """
        Initialize VmUpdater.
        """
        self.s3 = s3
        self.ignore_date = ignore_date
        self.vm = VirtualMachine(vm_name)
        self.download_dir = Path(self.s3.config.download_dir)
        self.s3_object_key = f"{self.vm.name}{self.zip_extension}"
        self.__current_snapshot_info = None
        self.__archive_path = None
        self.__archive_snapshot_uuid = None
        self.__archive_snapshot_date = None
        self.__vm_dir = None
        self.__archive_comment = None
        self.__uploaded = False
        self.__downloaded = False

    @property
    def downloaded(self) -> bool:
        """
        Get downloaded status for VM.
        """
        return self.__downloaded

    @property
    def uploaded(self) -> bool:
        """
        Get uploaded status for VM.
        """
        return self.__uploaded

    @property
    def vm_dir(self) -> Path:
        """
        Get VM directory for VM.
        """
        if self.__vm_dir is None:
            self.__vm_dir = Path(self.vm.get_parameter('CfgFile')).parent
        return self.__vm_dir

    @property
    def s3_snapshot_metadata(self) -> Optional[dict]:
        """
        Get snapshot metadata for VM on S3.
        """
        return self.s3.get_file_metadata(self.s3_object_key) or {}

    @property
    def current_snapshot_info(self) -> dict:
        """
        Get current snapshot info for VM.
        """
        if self.__current_snapshot_info is None:
            self.__current_snapshot_info = self.vm.snapshot.get_current_snapshot_info()
        return self.__current_snapshot_info

    @property
    def current_snapshot_uuid(self) -> Optional[str]:
        """
        Get current snapshot UUID for VM.
        """
        return self.current_snapshot_info.get('uuid')

    @property
    def current_snapshot_date(self) -> Optional[str]:
        """
        Get current snapshot date for VM.
        """
        return self.current_snapshot_info.get('created')

    @property
    def archive_path(self) -> Path:
        """
        Get archive path for VM.
        """
        if self.__archive_path is None:
            self.__archive_path = self.download_dir.joinpath(self.s3_object_key)
        return self.__archive_path

    @property
    def archive_comment(self) -> Optional[str]:
        """
        Get archive comment for VM.
        """
        if self.__archive_comment is None:
            try:
                self.__archive_comment = File.get_archive_comment(str(self.archive_path))
            except (FileNotFoundError, zipfile.BadZipFile):
                self.__archive_comment = None
        return self.__archive_comment

    @property
    def archive_snapshot_uuid(self) -> Optional[str]:
        """
        Get archive snapshot UUID for VM.
        """
        if self.__archive_snapshot_uuid is None:
            comment = self.archive_comment
            if comment:
                match = re.search(rf"{self.current_snapshot_uuid_key}: (?P<uuid>[^\n]+)", comment)
                if match:
                    self.__archive_snapshot_uuid = match.group('uuid')
        return self.__archive_snapshot_uuid

    @property
    def archive_snapshot_date(self) -> Optional[str]:
        """
        Get archive snapshot date for VM.
        """
        if self.__archive_snapshot_date is None:
            comment = self.archive_comment
            if comment:
                match = re.search(rf"{self.current_snapshot_date_key}: (?P<date>[^\n]+)", comment)
                if match:
                    self.__archive_snapshot_date = match.group('date')
        return self.__archive_snapshot_date

    def prepare_vm_for_update(self) -> None:
        """
        Prepare VM for update on S3 by stopping, restoring snapshot and compressing.

        :param vm_name: Name of the virtual machine
        :return: Path to created archive if successful, None otherwise
        """
        if self.vm.power_status():
            self.vm.stop()
        self.vm.snapshot.restore()
        self._log(f"Prepared current snapshot uuid [cyan]{self.current_snapshot_uuid}[/cyan] for update on S3")

    def compress(self, progress_bar: bool = False) -> None:
        """
        Compress VM directory to archive.

        :param vm_name: Name of the virtual machine
        :return: Path to created archive if successful, None otherwise
        """
        if not self.archive_path.is_file() or self.is_needs_compress():
            self._log(f"Compressing VM to archive [magenta]{self.archive_path}[/magenta]", color='cyan')
            archive_path = str(self.archive_path)
            File.delete(archive_path, stdout=False, stderr=False)
            File.compress(str(self.vm_dir), archive_path, progress_bar=progress_bar, comment=self.get_comment_for_archive())
            self._log(f"Compressed VM to archive [cyan]{self.archive_path}[/cyan]")
        else:
            self._log(f"Snapshot UUID already exists in host [cyan]{self.archive_path}[/cyan]", color='magenta')

    def get_comment_for_archive(self) -> str:
        """
        Get comment for archive.
        """
        return (
            f"{self.current_snapshot_uuid_key}: {self.current_snapshot_uuid}\n"
            f"{self.current_snapshot_date_key}: {self.current_snapshot_date}"
        )

    def is_needs_compress(self) -> bool:
        """
        Check if VM needs compress by comparing snapshot UUIDs.
        """
        return self.archive_snapshot_uuid != self.current_snapshot_uuid

    def is_needs_update(self) -> bool:
        """
        Check if VM needs update on S3 or update on host by comparing snapshot UUIDs.
        """
        s3_metadata = self.s3_snapshot_metadata
        s3_snapshot_date = self._datetime(s3_metadata.get(self.current_snapshot_date_key))
        s3_snapshot_uuid = s3_metadata.get(self.current_snapshot_uuid_key)
        current_snapshot_date = self._datetime(self.current_snapshot_date)

        if not self.ignore_date and s3_snapshot_date and current_snapshot_date:
            isDateDiff = s3_snapshot_date > current_snapshot_date
            return isDateDiff

        isUuidDiff = s3_snapshot_uuid != self.current_snapshot_uuid
        return isUuidDiff



    def upload(self) -> None:
        """
        Upload VM archive to S3.
        """
        if self.archive_path.is_file():
            if self.is_needs_update():
                msg = self.s3.upload_file(
                    str(self.archive_path),
                    self.s3_object_key,
                    metadata={
                        self.current_snapshot_uuid_key: self.current_snapshot_uuid,
                        self.current_snapshot_date_key: self.current_snapshot_date,
                    },
                    delete_exists=True,
                    warning_msg=False
                )
                self._log(msg, color='green')
                self.__uploaded = True
            else:
                self._log(f"Snapshot UUID already exists in S3 [cyan]{self.s3_object_key}[/cyan]", color='magenta')

    def download(self) -> None:
        """
        Download VM archive from S3.
        """
        if self.is_needs_update():
            self.s3.download_file(self.s3_object_key, str(self.archive_path))
            self.__downloaded = True
        else:
            self._log(f"Snapshot UUID already updated on host [cyan]{self.s3_object_key}[/cyan]", color='magenta')

    def unpack(self) -> None:
        """
        Unpack VM archive.
        """
        if self.archive_path.is_file():
            self._log(f"Unpacking VM [cyan]{self.vm.name}[/cyan] from [cyan]{self.archive_path}[/cyan]", color='blue')
            File.delete(str(self.vm_dir), stdout=False, stderr=False)
            File.unpacking(str(self.archive_path), str(self.vm_dir), stdout=False)
            self._fix_unpacking_duplication()
            self._log(f"Unpacked VM [cyan]{self.vm.name}[/cyan] to [cyan]{self.vm_dir}[/cyan]", color='green')
        else:
            self._log(f"Archive not found [cyan]{self.archive_path}[/cyan]", color='red')

    def _log(self, msg: str, color: str = 'green', level: str = 'INFO') -> None:
        """
        Print info message.
        """
        print(f"[{color}]{level}|[cyan]{self.vm.name}[/cyan]| {msg}[/]")

    def _fix_unpacking_duplication(self) -> None:
        """
        Fix directory duplication after unpacking.

        If archive contains a folder with the same name as the VM directory,
        move its contents to the parent directory and remove the empty folder.

        :param vm_dir: Target VM directory path
        """
        duplicated_dir = self.vm_dir / self.vm_dir.name

        if duplicated_dir.exists() and duplicated_dir.is_dir():
            self._log(f"Found duplicated directory: {duplicated_dir}", color='yellow')

            for item in duplicated_dir.iterdir():
                destination = self.vm_dir / item.name
                if destination.exists():
                    self._log(f"Removing existing: {destination}", color='yellow')
                    File.delete(str(destination), stdout=False)

                self._log(f"Moving: {item} -> {destination}", color='green')
                File.move(str(item), str(destination), stdout=False)

            File.delete(str(duplicated_dir), stdout=False)
            self._log("Fixed duplication: items moved and empty directory removed", color='green')

    def _datetime(self, date_string: Optional[str]) -> Optional[datetime]:
        """
        Get datetime from string.
        """
        if not date_string:
            return None
        return datetime.strptime(date_string, self.datetime_format)
