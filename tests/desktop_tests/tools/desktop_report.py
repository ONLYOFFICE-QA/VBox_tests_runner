# -*- coding: utf-8 -*-
from os.path import isfile
from os.path import dirname

from host_tools.utils import Dir
from rich import print

from host_tools import File
from frameworks.report import Report
from telegram import Telegram


class DesktopReport:
    def __init__(self, report_path: str):
        self.path = report_path
        self.dir = dirname(self.path)
        self.report = Report()
        Dir.create(self.dir, stdout=False)

    def write(self, version: str, vm_name: str, exit_code: str) -> None:
        self._write_titles() if not isfile(self.path) else ...
        self._writer(mode='a', message=["", vm_name, version, "", exit_code])

    def get_total_count(self, column_name: str) -> int:
        return self.report.total_count(self.report.read(self.path), column_name)

    def all_is_passed(self) -> bool:
        df = self.report.read(self.path)
        return df['Exit_code'].eq('Passed').all()

    def get_full(self, version: str) -> str:
        File.delete(self.path, stdout=False) if isfile(self.path) else ...
        self.report.merge(
            File.get_paths(self.dir, name_include=f"{version}", extension='csv'),
            self.path
        )
        return self.path

    def insert_vm_name(self, vm_name: str) -> None:
        self.report.save_csv(
            self.report.insert_column(self.path, location='Version', column_name='Vm_name', value=vm_name),
            self.path
        )

    def column_is_empty(self, column_name: str) -> bool:
        if not self.report.read(self.path)[column_name].count() or not isfile(self.path):
            return True
        return False

    def exists(self) -> bool:
        return isfile(self.path)

    def send_to_tg(self, data):
        if not isfile(self.path):
            return print(f"[red]|ERROR| Report for sending to telegram not exists: {self.path}")

        update_info = f"{data.update_from} -> " if data.update_from else ""
        result_status = "All tests passed" if self.all_is_passed() else "Some tests have errors"

        caption = (
            f"{data.title} desktop editor tests completed on version: `{update_info}{data.version}`\n\n"
            f"Package: `{self._get_package(data=data)}`\n"
            f"Result: `{result_status}`\n\n"
            f"Number of tested Os: `{self.get_total_count('Exit_code')}`"
        )

        Telegram(token=data.tg_token, chat_id=data.tg_chat_id).send_document(self.path, caption=caption)

    @staticmethod
    def _get_package(data) -> str:
        if data.snap:
            return "Snap Packages"

        if data.appimage:
            return "AppImages"

        if data.flatpak:
            return "FlatPak"

        return "Default Packages"

    def _writer(self, mode: str, message: list, delimiter='\t', encoding='utf-8'):
        self.report.write(self.path, mode, message, delimiter, encoding)

    def _write_titles(self):
        self._writer(mode='w', message=['Os', 'Vm_name', 'Version', 'Package_name', 'Exit_code'])
