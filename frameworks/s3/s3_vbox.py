# -*- coding: utf-8 -*-
import concurrent.futures
from os import cpu_count
from os.path import basename, join
from typing import Any

from rich.console import Console

from host_tools import File
from host_tools.utils import Dir
from s3wrapper import S3Wrapper


from .config import Config


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
        self.s3_files = self.s3.get_files()
        self.console = Console()

    def upload_from_dir(self, upload_dir: str, delete_exists: bool = False) -> None:
        """
        Uploads all .zip files from the specified directory to S3.

        :param upload_dir: The directory containing .zip files to upload.
        :param delete_exists: Whether to delete files from S3 that already exist before uploading.
        """
        upload_files = File.get_paths(upload_dir, extension='zip')

        if delete_exists:
            self.delete_files_from_s3(files=upload_files)

        with self.console.status('[cyan]Uploading files...') as status:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.cores) as executor:
                futures = [
                    executor.submit(self.upload_file, upload_file, basename(upload_file))
                    for upload_file in upload_files
                ]
                status.update(self._process_results(futures))

    def download(self, download_dir: str = None, download_files: list = None) -> None:
        """
        Downloads specified files or all available files from S3 to a local directory.

        :param download_dir: The local directory to download files to. Uses default if not provided.
        :param download_files: A list of specific files to download. Downloads all if not specified.
        """
        Dir.create(download_dir, stdout=False)
        s3_files = [file for file in self.s3_files if file in download_files] if download_files else self.s3_files

        with self.console.status('[cyan]Downloading files...') as status:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.cores) as executor:
                futures = [
                    executor.submit(
                        self.download_file,
                        s3_file,
                        join(download_dir or self.config.download_dir, basename(s3_file)))
                    for s3_file in s3_files
                ]
                status.update(self._process_results(futures))

    def upload_file(self, upload_file: str, object_key: str) -> str:
        """
        Uploads a single file to S3.

        :param upload_file: Local path of the file to upload.
        :param object_key: S3 object key under which to store the file.
        :return: A success message.
        """
        self.s3.upload(file_path=upload_file, object_key=object_key)
        return f'[green]|INFO| File [cyan]{upload_file}[/] to [cyan]{self.config.bucket_name}/{object_key}[/] uploaded'

    def download_file(self, s3_object_key: str, download_path: str) -> str:
        """
        Downloads a single file from S3.

        :param s3_object_key: S3 key of the object to download.
        :param download_path: Local path to save the downloaded file.
        :return: A success message.
        """
        self.s3.download(object_key=s3_object_key, download_path=download_path)
        return f"[green]|INFO| File [cyan]{s3_object_key}[/] downloaded to [cyan]{download_path}[/]"

    def delete_files_from_s3(self, files: list) -> None:
        """
        Deletes existing files in S3 that match the upload file names.

        :param files: List of local files to match for deletion in S3.
        """
        for file in files:
            s3_key = basename(file)
            if s3_key in self.s3_files:
                self.s3.delete(s3_key)

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
                self.console.print(f'[bold red] Exception occurred: {e}')
                return None

        return None
