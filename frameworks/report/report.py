# -*- coding: utf-8 -*-
import csv
from os.path import dirname, isfile
from csv import reader

import pandas as pd
from host_tools.utils import Dir
from rich import print


class Report:
    def __init__(self):
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option("expand_frame_repr", False)

    @staticmethod
    def total_count(df: pd.DataFrame, column_name: str) -> int:
        return df[column_name].count()

    @staticmethod
    def value_count(df: pd.DataFrame, column_name: str) -> str:
        return df[column_name].value_counts()

    def insert_column(self, path: str, location: str, column_name: str, value: str, delimiter='\t') -> pd.DataFrame:
        df = self.read(path, delimiter=delimiter)
        if column_name not in df.columns:
            df.insert(loc=df.columns.get_loc(location), column=column_name, value=value)
        else:
            print(f"[cyan]|INFO| Column `{column_name}` already exists in `{path}`")
        return df

    def merge(self, reports: list, result_csv_path: str, delimiter='\t') -> str | None:
        merge_reports = [
            self.read(csv_, delimiter)
            for csv_ in reports
            if isfile(csv_) and self.read(csv_, delimiter) is not None
        ]

        if merge_reports:
            df = pd.concat(merge_reports, ignore_index=True)
            df.to_csv(result_csv_path, index=False, sep=delimiter)
            return result_csv_path

        print('[green]|INFO| No files to merge')

    @staticmethod
    def write(file_path: str, mode: str, message: list, delimiter='\t', encoding='utf-8') -> None:
        Dir.create(dirname(file_path), stdout=False)
        with open(file_path, mode, newline='', encoding=encoding) as csv_file:
            writer = csv.writer(csv_file, delimiter=delimiter)
            writer.writerow(message)

    @staticmethod
    def read(csv_file: str, delimiter="\t", **kwargs) -> pd.DataFrame:
        """
        Reads a CSV file into a pandas DataFrame.
        :param csv_file: Path to the CSV file.
        :param delimiter: Delimiter used in the CSV file (default is '\t').
        :return: DataFrame containing the data from the CSV file.
        """
        data = pd.read_csv(csv_file, delimiter=delimiter, **kwargs)
        last_row = data.iloc[-1]

        if last_row.isnull().all() or (last_row.astype(str).str.contains(r"[^\x00-\x7F]", regex=True).any()):
            data = data.iloc[:-1]
            data.to_csv(csv_file)

        return data

    @staticmethod
    def read_via_csv(csv_file: str, delimiter: str = "\t") -> list:
        with open(csv_file, 'r') as csvfile:
            return [row for row in reader(csvfile, delimiter=delimiter)]

    @staticmethod
    def save_csv(df: pd.DataFrame, csv_path: str, delimiter="\t") -> str:
        df.to_csv(csv_path, index=False, sep=delimiter)
        return csv_path
