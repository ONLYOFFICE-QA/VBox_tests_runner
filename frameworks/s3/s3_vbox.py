# -*- coding: utf-8 -*-
import concurrent.futures
from os import cpu_count
from os.path import basename, join, isfile, getsize, dirname
from typing import Any

from rich.console import Console

from host_tools import File
from host_tools.utils import Dir
from s3wrapper import S3Wrapper

from .config import Config
from ..console import MyConsole

console = MyConsole().console
print = console.print

class S3Vbox:
    """
    Handles uploading and downloading files to and from an S3 bucket using multithreading.
    """

    def __init__(self, cores: int = None, s3_config_path: str = None):
        """
        Initializes the S3Vbox object with optional core count.

        :param cores: Number of CPU cores to use for parallel execution. Defaults to half the available cores.
        :param s3_config_path: Optional path to a JSON config file. If not provided, a default path is used.
        """
        self.config = Config.load_from_file(path=s3_config_path)
        self.cores = cores or cpu_count() // 2
        self.s3 = S3Wrapper(bucket_name=self.config.bucket_name, region=self.config.region)
        self.console = console
        self.__s3_files = None

    @property
    def s3_files(self) -> list:
        """
        Get the list of files in the S3 bucket.
        """
        if self.__s3_files is None:
            self.update_s3_files()
        return self.__s3_files

    @property
    def s3_files_count(self) -> int:
        """
        Get the count of files in the S3 bucket.
        """
        return len(self.s3_files)

    def update_s3_files(self) -> None:
        """
        Update the list of files in the S3 bucket.
        """
        self.__s3_files = self.s3.get_files()

    def get_file_data(self, object_key: str) -> dict:
        """
        Get the data of a file in the S3 bucket.
        """
        return self.s3.get_headers(object_key).get('LastModified')

    def get_file_metadata(self, object_key: str) -> dict:
        """
        Get the metadata of a file in the S3 bucket.
        """
        metadata = self.s3.get_metadata(object_key)
        return metadata or {}

    def upload_files(self, upload_files: list | str, delete_exists: bool = False, warning_msg: bool = True, metadata: dict = None) -> None:
        """
        Upload files to S3.

        :param upload_files: File path or list of file paths to upload
        :param delete_exists: Delete existing files in S3 before uploading
        :param warning_msg: Show warning messages
        :param metadata: Dictionary of metadata to attach to uploaded files { 'file_name:': { 'key': 'value' } }
        """
        if delete_exists:
            self.delete_files_from_s3(files=upload_files, warning_msg=warning_msg)

        _upload_files = upload_files if isinstance(upload_files, list) else [upload_files]

        with self.console.status('[cyan]Uploading files...') as status:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.cores) as executor:
                futures = [
                    executor.submit(self.upload_file, upload_file, basename(upload_file), metadata.get(basename(upload_file), None))
                    for upload_file in _upload_files
                ]
                status.update(self._process_results(futures))

    def upload_from_dir(self, upload_dir: str, delete_exists: bool = False, warning_msg: bool = True, metadata: dict = None) -> None:
        """
        Uploads all .zip files from the specified directory to S3.

        :param upload_dir: The directory containing .zip files to upload.
        :param delete_exists: Whether to delete files from S3 that already exist before uploading.
        :param metadata: Dictionary of metadata to attach to uploaded files
        """
        upload_files = File.get_paths(upload_dir, extension='zip')
        self.upload_files(upload_files=upload_files, delete_exists=delete_exists, warning_msg=warning_msg, metadata=metadata)

    def download(self, download_dir: str = None, download_files: list = None) -> None:
        """
        Downloads specified files or all available files from S3 to a local directory.

        :param download_dir: The local directory to download files to. Uses default if not provided.
        :param download_files: A list of specific files to download. Downloads all if not specified.
        """
        download_dir = download_dir or self.config.download_dir

        Dir.create(download_dir, stdout=False)
        s3_files = [file for file in self.s3_files if file in download_files] if download_files else self.s3_files

        with self.console.status('[cyan]Downloading files...'):
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.cores) as executor:
                futures = [
                    executor.submit(
                        self.download_file,
                        s3_file,
                        join(download_dir, basename(s3_file)))
                    for s3_file in s3_files
                ]
                self._process_results(futures)

    def upload_file(self, upload_file: str, object_key: str, delete_exists: bool = False, warning_msg: bool = True, metadata: dict = None) -> str:
        """
        Uploads a single file to S3.

        :param upload_file: Local path of the file to upload.
        :param object_key: S3 object key under which to store the file.
        :param delete_exists: Delete existing file in S3 before uploading
        :param warning_msg: Show warning messages
        :param metadata: Dictionary of metadata to attach to the file
        :return: A success message.
        """
        if delete_exists:
            self.delete_files_from_s3(files=upload_file, warning_msg=warning_msg)

        print(f"[cyan]|INFO| Uploading file [cyan]{upload_file}[/] to [cyan]{self.config.bucket_name}/{object_key}[/]")
        self.s3.upload(file_path=upload_file, object_key=object_key, stdout=False, metadata=metadata)
        self.__s3_files = None
        return f'[green]|INFO| File [cyan]{upload_file}[/] to [cyan]{self.config.bucket_name}/{object_key}[/] uploaded'

    def download_file(self, s3_object_key: str, download_path: str) -> str:
        """
        Downloads a single file from S3.

        :param s3_object_key: S3 key of the object to download.
        :param download_path: Local path to save the downloaded file.
        :return: A success message.
        """
        if self.is_exists_object(download_path, s3_object_key):
            print(f"[cyan]|INFO| Object {s3_object_key} already exists")
            return ""

        print(f"[green]|INFO| Downloading file [cyan]{s3_object_key}[/] to [cyan]{download_path}[/]")
        Dir.create(dirname(download_path), stdout=False)
        self.s3.download(object_key=s3_object_key, download_path=download_path, stdout=False)
        return f"[green]|INFO| File [cyan]{s3_object_key}[/] downloaded to [cyan]{download_path}[/]"

    def delete_files_from_s3(self, files: list | str, warning_msg: bool = True) -> None:
        """
        Deletes existing files in S3 that match the upload file names.

        :param files: List of local files to match for deletion in S3.
        """
        for file in list(dict.fromkeys(files)) if isinstance(files, list) else [files]:
            s3_key = basename(file)
            if s3_key in self.s3_files:
                self.s3.delete(s3_key, warning_msg=warning_msg)

    def is_exists_object(self, download_path: str, obj_key: str) -> bool:
        """
        Checks if the downloaded object exists and optionally verifies its integrity.
        :param download_path: The path where the object is downloaded.
        :param obj_key: The key of the object in the S3 bucket.
        :return: True if the object exists and passes integrity checks, False otherwise.
        """
        if not isfile(download_path):
            return False
        if getsize(download_path) != self.s3.get_size(obj_key):
            return False
        return True

    def _process_results(self, futures: list) -> Any | None:
        """
        Processes the results of futures and handles any exceptions.

        :param futures: A list of Future objects from concurrent executions.
        :return: The result of the first successful future, or None if an error occurs.
        """
        for future in concurrent.futures.as_completed(futures):
            try:
                return future.result()

            except Exception as e:
                print(f'[bold red] Exception occurred: {e}')
                return None
        return None
