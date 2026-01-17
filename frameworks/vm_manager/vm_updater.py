# -*- coding: utf-8 -*-
from datetime import datetime
from os.path import isfile
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
    snapshot_uuid_key = 'current_snapshot_uuid'
    snapshot_date_key = 'current_snapshot_date'
    zip_extension = '.zip'
    datetime_format = "%Y-%m-%dT%H:%M:%SZ"
    vm_uuid_key = 'uuid'
    vm_date_key = 'created'
    required_snapshot_params = [vm_uuid_key, vm_date_key]

    def __init__(self, vm_name: str, s3: S3Vbox, ignore_date: bool = False):
        """
        Initialize VmUpdater.
        :param vm_name: Name of the virtual machine
        :param s3: S3Vbox object
        :param ignore_date: Ignore date comparison when checking if VM needs update
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
        self.__s3_object_metadata = None
        self.__vm_dir = None
        self.__archive_comment = None
        self.__uploaded = False
        self.__downloaded = False
        self.__vm_config_path = None

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
        if self.__vm_dir is None or not self.__vm_dir.is_dir():
            self.update_vm_dir()
        return self.__vm_dir

    def update_vm_dir(self) -> None:
        """
        Update VM directory for VM.
        """
        self.update_vm_config_path()
        self.__vm_dir = Path(self.vm_config_path).parent if self.vm_config_path else Path(self.vm.info.default_vm_dir) / self.vm.name

    @property
    def vm_config_path(self) -> Optional[str]:
        """
        Get VM configuration path for VM.
        """
        if self.__vm_config_path is None:
            self.update_vm_config_path()
        return self.__vm_config_path

    def update_vm_config_path(self) -> None:
        """
        Update VM configuration path by refreshing from VM info.
        """
        self.__vm_config_path = self.vm.info.config_path

    @property
    def s3_object_metadata(self) -> dict:
        """
        Get metadata for s3 object.
        """
        if self.__s3_object_metadata is None:
            self.update_s3_object_metadata()
        return self.__s3_object_metadata

    @property
    def s3_object_snapshot_date(self) -> Optional[str]:
        """
        Get snapshot date for s3 object from metadata.
        """
        return self.s3_object_metadata.get(self.snapshot_date_key)

    @property
    def s3_object_snapshot_uuid(self) -> Optional[str]:
        """
        Get snapshot UUID for s3 object from metadata.
        """
        return self.s3_object_metadata.get(self.snapshot_uuid_key)

    def update_s3_object_metadata(self) -> None:
        """
        Update metadata for s3 object.
        """
        self.__s3_object_metadata = self.s3.get_file_metadata(self.s3_object_key) or {}

    @property
    def current_snapshot_info(self) -> dict:
        """
        Get current snapshot info for VM.
        """
        if self.__current_snapshot_info is None:
            info = self.vm.snapshot.get_current_snapshot_info()
            # Validate that required fields are present and not empty
            for param in self.required_snapshot_params:
                if not info.get(param):
                    raise ValueError(f"Snapshot info for VM '{self.vm.name}' is missing '{param}' field or it is empty")
            self.__current_snapshot_info = info
        return self.__current_snapshot_info

    @property
    def current_snapshot_uuid(self) -> Optional[str]:
        """
        Get current snapshot UUID for VM.
        """
        return self.current_snapshot_info.get(self.vm_uuid_key)

    @property
    def current_snapshot_date(self) -> Optional[str]:
        """
        Get current snapshot date for VM.
        """
        return self.current_snapshot_info.get(self.vm_date_key)

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
            self.update_archive_comment()
        return self.__archive_comment

    def update_archive_comment(self) -> None:
        """
        Update archive comment for VM.
        """
        try:
            self.__archive_comment = File.get_archive_comment(str(self.archive_path))
        except (FileNotFoundError, zipfile.BadZipFile):
            self.__archive_comment = None

    @property
    def archive_snapshot_uuid(self) -> Optional[str]:
        """
        Get archive snapshot UUID for VM.
        """
        if self.__archive_snapshot_uuid is None:
            if self.archive_comment:
                match = re.search(rf"{self.snapshot_uuid_key}: (?P<uuid>[^\n]+)", self.archive_comment)
                if match:
                    group = match.group('uuid')
                    self.__archive_snapshot_uuid = group.strip() if group else None
        return self.__archive_snapshot_uuid

    @property
    def archive_snapshot_date(self) -> Optional[str]:
        """
        Get archive snapshot date for VM.
        """
        if self.__archive_snapshot_date is None:
            if self.archive_comment:
                match = re.search(rf"{self.snapshot_date_key}: (?P<date>[^\n]+)", self.archive_comment)
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
            File.compress(str(self.vm_dir), archive_path, progress_bar=progress_bar, comment=self._get_comment_for_archive())
            self._log(f"Compressed VM to archive [cyan]{self.archive_path}[/cyan]")
            self.update_archive_comment()
        else:
            self._log(f"Snapshot UUID already exists in host [cyan]{self.archive_path}[/cyan]", color='magenta')

    def is_needs_compress(self) -> bool:
        """
        Check if VM needs compress by comparing snapshot UUIDs.
        """
        return self.archive_snapshot_uuid != self.current_snapshot_uuid

    def is_needs_update_on_s3(self) -> bool:
        """
        Check if VM needs update on S3 by comparing snapshot UUIDs and dates.
        """
        return self._check_update_needed(on_s3=True)

    def is_needs_update_on_host(self) -> bool:
        """
        Check if VM needs update on host by comparing snapshot UUIDs and dates.
        """
        if not self.vm_config_path or not isfile(self.vm_config_path):
            self._log(f"VM configuration file not found on path: [cyan]{self.vm_config_path}[/cyan]", color='red')
            return True
        return self._check_update_needed(on_s3=False)

    def upload(self) -> None:
        """
        Upload VM archive to S3.
        """
        if self.archive_path.is_file() and self.is_needs_update_on_s3():
            msg = self.s3.upload_file(
                str(self.archive_path),
                self.s3_object_key,
                metadata=self._get_metadata(),
                delete_exists=True,
                warning_msg=False
            )
            self._log(msg, color='green')
            self.__uploaded = True
            self.update_s3_object_metadata()
        else:
            self._log(f"Snapshot UUID already exists in S3 [cyan]{self.s3_object_key}[/cyan]", color='magenta')

    def download(self) -> None:
        """
        Download VM archive from S3.
        """
        if not self.s3.is_exists_object(str(self.archive_path), self.s3_object_key):
            self.s3.download_file(self.s3_object_key, str(self.archive_path))
            self.__downloaded = True
        else:
            self._log(f"Archive [cyan]{self.archive_path}[/cyan] already exists in host", color='magenta')

    def unpack(self) -> None:
        """
        Unpack VM archive.
        """
        if self.archive_path.is_file() and self.is_needs_update_on_host():
            self._log(f"Unpacking VM [cyan]{self.vm.name}[/cyan] from [cyan]{self.archive_path}[/cyan] to [cyan]{self.vm_dir}[/cyan]", color='blue')
            File.delete(str(self.vm_dir), stdout=False, stderr=False)
            File.unpacking(str(self.archive_path), str(self.vm_dir), stdout=False)
            self._fix_unpacking_duplication()
            self._register_vm()
            self._move_to_group_dir()
            self._remove_useless_dvd_images()
            self._log(f"Unpacked VM [cyan]{self.vm.name}[/cyan] to [cyan]{self.vm_dir}[/cyan]", color='green')
        else:
            self._log(f"Archive not found or already updated on host [cyan]{self.archive_path}[/cyan]", color='magenta')

    def _register_vm(self) -> None:
        """
        Register VM in VirtualBox.
        """
        if not self.vm.is_registered():
            vbox_file = self._find_vbox_file()
            if vbox_file:
                self.vm.register(str(vbox_file))
            else:
                self._log(f"VBox file not found on path: [cyan]{self.vm_dir}[/cyan]", color='red')

    def _move_to_group_dir(self) -> None:
        """
        Move VM to group directory and move remaining files from old directory.
        """
        group_name = self.vm.get_group_name()
        if group_name and not group_name in str(self.vm_dir):
            group_dir = Path(self.vm.info.default_vm_dir) / group_name
            group_dir.mkdir(parents=True, exist_ok=True)
            self.vm.move_to(str(group_dir), move_remaining_files=True, delete_old_directory=True)
            self.update_vm_dir()

    def _remove_useless_dvd_images(self) -> None:
        """
        Remove useless DVD images from VM. If there are no DVD images, do nothing.
        """
        images = self.vm.storage.get_dvd_images
        if images:
            self._log(f"Removing useless DVD images [cyan]{', '.join(images)}[/cyan] from VM [cyan]{self.vm.name}[/cyan]", color='yellow')
            self.vm.storage.remove_dvd_images()

    def _log(self, msg: str, color: str = 'green', level: str = 'INFO') -> None:
        """
        Print info message.
        """
        print(f"[{color}]{level}|[cyan]{self.vm.name}[/cyan]| {msg}[/]")

    def _check_update_needed(self, on_s3: bool) -> bool:
        """
        Check if update is needed by comparing snapshot UUIDs and dates.
        :param on_s3: If True check if update is needed on S3 missing metadata, return True;
        if False, check if update is needed on host missing metadata, return False;
        :return: True if update is needed, False otherwise
        """
        if not (self.s3_object_snapshot_date or self.s3_object_snapshot_uuid):
            self._log(
                f"Snapshot UUIDs or dates for VM on s3 '{self.vm.name}' are not present. Needs update on image on s3",
                color='bold red',
                level='ERROR'
            )
            return on_s3

        is_date_diff = self._compare_dates(s3_date_older=on_s3)
        is_uuid_diff = self._uuids_is_diff()

        if is_date_diff and not is_uuid_diff:
            self._log_date_uuid_mismatch()
            return on_s3

        if self.ignore_date:
            return is_uuid_diff
        return is_date_diff and is_uuid_diff

    def _uuids_is_diff(self) -> bool:
        """
        Check if VM needs update by comparing snapshot UUIDs.
        """
        return self.s3_object_snapshot_uuid != self.current_snapshot_uuid

    def _log_date_uuid_mismatch(self) -> None:
        """
        Log error when snapshot date differs but UUID is the same.
        """
        self._log(
            f"Snapshot date is older than current date on host [cyan]{self.vm.name}[/cyan] but UUID is the same. "
            f"Needs update on image on s3",
            color='bold red',
            level='ERROR'
        )

    def _get_metadata(self) -> dict:
        """
        Get metadata for s3 object.
        """
        return {
            self.snapshot_uuid_key: self.current_snapshot_uuid,
            self.snapshot_date_key: self.current_snapshot_date,
        }

    def _get_comment_for_archive(self) -> str:
        """
        Get comment for archive.
        """
        metadata = self._get_metadata()
        return "\n".join(f"{key}: {value}" for key, value in metadata.items())

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

    def _compare_dates(self, s3_date_older: bool) -> bool:
        """
        Compare snapshot dates between S3 and current VM.
        :param s3_date: Date string from S3 object metadata
        :param current_date: Date string from current VM snapshot
        :param s3_date_older: If True, check if s3_date is older than current_date; if False, check if newer
        :return: True if dates match the comparison criteria, False otherwise
        """
        s3_datetime = self._datetime(self.s3_object_snapshot_date)
        current_datetime = self._datetime(self.current_snapshot_date)

        if s3_datetime and current_datetime:
            return s3_datetime < current_datetime if s3_date_older else s3_datetime > current_datetime
        return False

    def _find_vbox_file(self) -> Optional[Path]:
        """
        Find .vbox configuration file in VM directory.
        """
        if self.vm_dir and self.vm_dir.is_dir():
            return next(self.vm_dir.glob('*.vbox'), None)
        return None

    def _datetime(self, date_string: Optional[str]) -> Optional[datetime]:
        """
        Get datetime from string.
        :param date_string: Date string to convert to datetime
        :return: Datetime object if successful, None otherwise
        :raises ValueError: If date string is not in the correct format
        """
        if not date_string:
            return None

        try:
            return datetime.strptime(date_string, self.datetime_format)
        except ValueError:
            raise ValueError(
                f"Snapshot date for VM '{self.vm.name}' has invalid format. "
                f"Expected format: {self.datetime_format}, got: {date_string}"
            )
